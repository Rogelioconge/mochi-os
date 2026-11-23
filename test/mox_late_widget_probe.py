#!/usr/bin/env python3
"""Offline unit and mutation tests. Native MIPS executes separately on Mac."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mox_late_widget_probe as probe  # noqa: E402


def mocked_exec(blob, *, first_ok, second_ok, items, backend):
    assert first_ok and second_ok
    assert items == backend.items
    backend.call('lookup_root', 0, 0, 0, 0)
    backend.call('lookup_slide', 0, 0, 0, 0)
    backend.call('setup_root', probe.em.HOME + 0x100, 0, 0, 0)
    backend.call('item_count', 0, 0, 0, 0)
    count = (items + 5) // 6
    backend.call('set_page_count', probe.em.SLIDE, count, 0, 0)
    for i in range(count):
        ptr = backend.call('create_page', probe.em.HOME + 0x100, 0, 0, 320)
        backend.call('populate_page', ptr, i, items, 0)
    backend.call('set_page_index', probe.em.SLIDE, 0, 0, 0)
    return {'returned': '0x0'}


def main():
    # The injected callback preserves the MIPS-facing function signature;
    # the actual MIPS control flow is checked by the separate runtime probe.
    for items, pages in ((5, 1), (7, 2)):
        model = probe.AWTKGridModel(items)
        assert probe.late_restore(b'', model, executor=mocked_exec) == 'reconstructed'
        assert len(model.pages) == pages and model.valid()
        assert probe.late_restore(b'', model, executor=mocked_exec) == 'already_ready'
        assert model.run_count == 1
        print('OK: widget model creates', pages, 'page(s), no duplicate runs')
    bad = probe.AWTKGridModel(7, fail_create_at=1)
    assert probe.late_restore(b'', bad, executor=mocked_exec) == 'blocked'
    assert bad.failure is not None
    assert probe.late_restore(b'', bad, executor=mocked_exec) == 'blocked'
    assert bad.run_count == 1
    print('OK: partial creation fails closed and is not retried')
    bad = probe.AWTKGridModel(7)
    bad.pages = [{'ptr': 0x30010000, 'filled': False}]
    assert probe.late_restore(b'', bad, executor=mocked_exec) == 'blocked'
    assert bad.run_count == 0
    print('OK: partial existing grid prevents MIPS execution')
    for kw in ({'root': False}, {'slide': False}):
        bad = probe.AWTKGridModel(7, **kw)
        assert probe.late_restore(b'', bad, executor=mocked_exec) == 'blocked'
        assert bad.run_count == 0
    print('OK: missing root/slide blocks before builder')
    for kw in ({'items': -1}, {'items': 49}):
        try:
            probe.AWTKGridModel(**kw)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid page capacity accepted')
    print('OK: invalid item counts fail closed')
    zero = probe.AWTKGridModel(0)
    assert probe.late_restore(b'', zero, executor=mocked_exec) == 'blocked'
    assert zero.failure and 'incomplete' in zero.failure
    print('OK: empty result cannot be accepted as successful')
    fake = probe.AWTKGridModel(7)
    try:
        fake.call('create_page', 0, 0, 0, 320)
    except ValueError:
        pass
    else:
        raise AssertionError('Incorrect parent pointer accepted')
    print('OK: wrong widget parent rejected')
    print('MOX: 8/8 stateful offline checks OK; cutover still blocked')


if __name__ == '__main__':
    main()
