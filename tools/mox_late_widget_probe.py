#!/usr/bin/env python3
"""Fail-closed late-rebuild rehearsal using the *real V2.1 MIPS builder*.

Only the builder's machine instructions execute; AWTK calls use a stateful
fake widget graph. No real AWTK, Shanling Home initialization or firmware is
changed. Native cutover remains forbidden regardless of results.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_emulator():
    path = Path(__file__).with_name('mox_builder_emulation.py')
    spec = importlib.util.spec_from_file_location('mox_builder_emulation', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


em = load_emulator()


class AWTKGridModel:
    """Synthetic AWTK tree. Not a copy of the device's implementation."""

    def __init__(self, items, *, root=True, slide=True, fail_create_at=None):
        if not 0 <= items <= 48:
            raise ValueError('Mock item count must fit at most eight pages')
        self.items = items
        self.root = root
        self.slide = slide
        self.fail_create_at = fail_create_at
        self.pages = []
        self.declared_pages = None
        self.page_index_set = False
        self.attempted = False
        self.run_count = 0
        self.log = []
        self.failure = None

    def valid(self):
        expected = (self.items + 5) // 6
        return (0 < expected <= 8 and self.declared_pages == expected
                and len(self.pages) == expected
                and all(page['filled'] for page in self.pages)
                and self.page_index_set)

    def call(self, name, a0, a1, a2, a3):
        self.log.append(name)
        if name == 'lookup_root':
            return em.HOME + 0x100 if self.root else 0
        if name == 'lookup_slide':
            return em.SLIDE if self.slide else 0
        if name == 'setup_root':
            if a0 != em.HOME + 0x100:
                raise ValueError('setup_root received wrong root widget')
            return 0
        if name == 'item_count':
            return self.items
        if name == 'set_page_count':
            if a0 != em.SLIDE or self.declared_pages is not None:
                raise ValueError('duplicate/incorrect page-count assignment')
            self.declared_pages = a1
            return 0
        if name == 'create_page':
            if a0 != em.HOME + 0x100:
                raise ValueError('create_page received wrong root widget')
            if a1 != 0 or a2 != 0 or a3 != 320:
                raise ValueError('unexpected initial geometry')
            if self.fail_create_at is not None and len(self.pages) == self.fail_create_at:
                return 0
            pointer = 0x30010000 + len(self.pages) * 0x1000
            self.pages.append({'ptr': pointer, 'filled': False})
            return pointer
        if name == 'populate_page':
            if not self.pages or a0 != self.pages[-1]['ptr']:
                raise ValueError('populate_page received missing/wrong page')
            if a1 != len(self.pages) - 1 or a2 != self.items:
                raise ValueError('populate_page received wrong item index or count')
            if self.pages[-1]['filled']:
                raise ValueError('populate_page called twice')
            self.pages[-1]['filled'] = True
            return 0
        if name == 'set_page_index':
            if a0 != em.SLIDE or a1 != 0 or self.page_index_set:
                raise ValueError('invalid page-index initialization')
            self.page_index_set = True
            return 0
        raise ValueError('unexpected external callback: ' + name)


def late_restore(blob, model, *, executor=None):
    """Simulate the existing fail-closed C gate, never touching firmware.

    The C contract in patch/mox_grid_rebuild.c remains separate and unlinked.
    This Python gate is a test model, NOT the device's boot code.
    """
    if not model.root or not model.slide:
        return 'blocked'
    if model.pages:
        return 'already_ready' if model.valid() else 'blocked'
    if model.attempted:
        return 'blocked'
    model.attempted = True  # sticky before invoking real MIPS instructions
    model.run_count += 1
    try:
        execution = (executor or em.execute)(blob, first_ok=True, second_ok=True,
                                              items=model.items, backend=model)
        if execution['returned'] != '0x0':
            model.failure = 'stock builder returned ' + execution['returned']
            return 'blocked'
    except Exception as exc:
        model.failure = str(exc)
        return 'blocked'
    if not model.valid():
        model.failure = 'stock MIPS returned success but AWTK graph is incomplete'
        return 'blocked'
    return 'reconstructed'


def check(blob, label, model, expected, *, executor=None):
    result = late_restore(blob, model, executor=executor)
    if result != expected:
        raise AssertionError(f'{label}: expected {expected}, got {result}; '
                             f'calls={model.log}; error={model.failure}')
    return {'scenario': label, 'outcome': result, 'pages': len(model.pages),
            'builder_runs': model.run_count, 'graph_valid': model.valid(),
            'failure': model.failure}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--demo', type=Path,
                    default=ROOT / 'work/check/release/work/mod-release/rootfs/release/bin/demo')
    ap.add_argument('--report', type=Path,
                    default=ROOT / 'out/mox-cutover/late-widget-probe.json')
    args = ap.parse_args()
    if not args.demo.is_file():
        ap.error('MIPS demo is missing; run make test TEST=home')
    data = args.demo.read_bytes()
    contract = em.preflight(data)
    results = []

    for items, label in ((5, 'one_page_late'), (7, 'two_pages_late')):
        model = AWTKGridModel(items)
        results.append(check(data, label, model, 'reconstructed'))
        results.append(check(data, label + '_repeat', model, 'already_ready'))
        if model.run_count != 1:
            raise AssertionError('Repeated MIPS execution would create duplicate pages')
        print('OK:', label, 'created', len(model.pages), 'stateful fake pages; repeat skipped')

    model = AWTKGridModel(7)
    model.declared_pages = 2
    model.pages = [{'ptr': 0x30010000, 'filled': False}]
    results.append(check(data, 'partial_existing_grid', model, 'blocked'))
    if model.run_count:
        raise AssertionError('Unclean pre-existing grid must block execution')
    print('OK: partial widget graph rejected before running MIPS')

    model = AWTKGridModel(7, fail_create_at=1)
    results.append(check(data, 'second_page_failure', model, 'blocked'))
    results.append(check(data, 'failed_recovery_retry', model, 'blocked'))
    if model.run_count != 1:
        raise AssertionError('Partial rebuild was retried')
    print('OK: failed/partial construction does not permit MIPS retry')

    for name, model in [('missing_root', AWTKGridModel(7, root=False)),
                        ('missing_slide', AWTKGridModel(7, slide=False))]:
        results.append(check(data, name, model, 'blocked'))
        if model.run_count:
            raise AssertionError('Unsafe precondition ran the MIPS builder')
        print('OK:', name, 'blocked before calling MIPS')

    model = AWTKGridModel(0)
    results.append(check(data, 'zero_items', model, 'blocked'))
    print('OK: zero-page Home is not accepted even if MIPS returns success')

    report = {
        'binary_sha256': contract['contract']['binary_sha256'],
        'probe_type': 'real MIPS flow with stateful fake AWTK callbacks',
        'scenario_results': results,
        'real_awtk_executed': False,
        'hardware_tested': False,
        'late_recovery_proven': False,
        'native_bypass_authorized': False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('MOX stateful MIPS widget probe:', len(results), 'scenarios OK; AWTK MOCKED')
    print('BLOQUEADO: still no evidence of safe real AWTK late re-entry')
    print('Informe:', args.report)


if __name__ == '__main__':
    main()
