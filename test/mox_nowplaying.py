#!/usr/bin/env python3
"""Host-only structural checks for Mochi's isolated Now Playing window and theme."""
import ast
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import awtk_style  # noqa: E402
import awtk_ui  # noqa: E402
import mod_icons  # noqa: E402
import mod_mox_nowplaying as mn  # noqa: E402


def rect(widget, dy=0):
    return widget.x, widget.y + dy, widget.w, widget.h


def overlap(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def synthetic_source_theme():
    """Construct a minimal compatible theme without the proprietary firmware files."""
    return awtk_style.serialize(awtk_style.Theme([
        awtk_style.Item('button', style, state, [('icon', awtk_style.T_STRING, 'np_play')])
        for style in sorted(mn.THEME_STYLES)
        for state in mn.BTN_STATES
    ]))


def run():
    data = mn.transform()
    root = awtk_ui.parse(data)
    assert (root.type, root.name, root.w, root.h) == ('window', mn.NAME, 320, 450)
    assert awtk_ui.serialize(root) == data == mn.transform()
    print('OK 1: independent deterministic AWTK window and exact binary round-trip')

    names = [w.name for w in root.walk() if w.name]
    assert len(names) == len(set(names))
    assert all(names.count(name) == 1 for name in mn.REQUIRED)
    print('OK 2: required stock-compatible widget names are unique')

    for widget in root.walk():
        if widget is root:
            continue
        x, y, w, h = rect(widget)
        assert x >= 0 and y >= 0 and x + w <= mn.W and y + h <= mn.H, widget.name
    stack = [root.find(name) for name in ('img_playcover', 'scrlabel_title',
                                         'scrlabel_artist', 'slider_play', 'label_playtime')]
    assert all(a.y + a.h <= b.y for a, b in zip(stack, stack[1:]))
    assert root.find('img_playcover').x * 2 + mn.COVER == mn.W
    print('OK 3: bounds, non-overlapping vertical blocks and centered cover')

    controls = ['btn_return', 'btn_fav', 'btn_more', 'slider_play', *mn.SLOTS]
    boxes = {}
    for name in controls:
        w = root.find(name)
        boxes[name] = rect(w, mn.ROW_Y if name in mn.SLOTS else 0)
        assert w.w >= 44 and w.h >= (30 if name == 'slider_play' else 44)
    assert all(not overlap(boxes[a], boxes[b])
               for i, a in enumerate(controls) for b in controls[i + 1:])
    print('OK 4: tactile targets are sized and do not overlap')

    for name in ('img_playcover', 'scrlabel_title', 'scrlabel_artist',
                 'label_playtime', 'label_playlen'):
        assert root.find(name).get('sensitive') == 'false'
    assert all(w.get('visible') != 'false' for w in root.walk())
    assert root.find('slider_play').type == 'slider'
    assert not any('wave' in w.name.lower() for w in root.walk())
    print('OK 5: decorations do not intercept touch; slider is not a fake waveform')

    used = mn.image_names()
    assert used and used <= set(mod_icons.np_names()), sorted(used - set(mod_icons.np_names()))
    print('OK 6: resource icons come from the existing np_* set')

    for name, expected_style in mn.DYNAMIC_STYLES.items():
        w = root.find(name)
        assert w.get('style') == expected_style
        assert not any(k.endswith(':bg_image') for k, _ in w.props), name
    print('OK 7: play/pause, play-mode and favorite styles are not masked by inline images')

    original = synthetic_source_theme()
    theme_data = mn.transform_theme(original)
    th = awtk_style.parse(theme_data)
    assert awtk_style.serialize(th) == theme_data
    assert len(th.items) == len(mn.THEME_STYLES) * len(mn.BTN_STATES)
    for name in mn.THEME_STYLES:
        assert {item.state for item in th.find(widget='button', style=name)} == set(mn.BTN_STATES)
    print('OK 8: self-contained page-local button theme with all mandatory states')

    # A changed/partial upstream theme must be rejected before packaging.
    broken = awtk_style.Theme(awtk_style.parse(original).items[:-1])
    try:
        mn.transform_theme(awtk_style.serialize(broken))
    except ValueError:
        pass
    else:
        raise AssertionError('Incomplete theme was accepted')
    print('OK 9: missing inherited styles fail safely')

    with tempfile.TemporaryDirectory() as temp:
        parent = Path(temp)
        (parent / mn.UI).mkdir(parents=True)
        (parent / mn.STYLES).mkdir(parents=True)
        (parent / mn.STYLES / mn.SOURCE_THEME).write_bytes(original)
        mn.apply(parent, parent)
        assert (parent / mn.UI / mn.NATIVE).read_bytes() == data
        assert (parent / mn.STYLES / mn.THEME).read_bytes() == theme_data
        mn.apply(parent, parent)
        (parent / mn.STYLES / mn.THEME).write_bytes(b'corrupted')
        try:
            mn.apply(parent, parent)
        except ValueError:
            pass
        else:
            raise AssertionError('Conflicting theme was overwritten')
    print('OK 10: both resources install idempotently; conflicting files are refused')

    assert mn.added_rels() == [
        'release/assets/default/raw/ui/mox_now_playing.bin',
        'release/assets/default/raw/styles/mox_now_playing_page.bin',
    ]
    steps = next(ast.literal_eval(node.value) for node in
                 ast.parse((ROOT / 'tools/build.py').read_text()).body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'STEPS'
                         for t in node.targets))
    modules = [module for module, _ in steps]
    assert modules.count('mod_mox_nowplaying') == 1
    assert modules.index('mod_nowplaying') < modules.index('mod_mox_nowplaying')
    assert modules.index('mod_mox_native') < modules.index('mod_mox_nowplaying')
    assert 'test/mox_nowplaying.py' in (ROOT / 'Makefile').read_text()
    print('OK 11: correctly ordered build stage, test registration and pack allowlist')

    for path in (ROOT / 'patch').iterdir():
        if path.suffix in ('.c', '.h', '.inc', '.S'):
            assert 'mox_now_playing' not in path.read_text(), path
    assert 'mox_now_playing' not in (ROOT / 'tools/mod_nowplaying.py').read_text()
    print('OK 12: no boot/audio payload is changed, window remains unreachable')
    print('MOX Now Playing: 12/12 host structural checks OK; not device validated')


if __name__ == '__main__':
    run()
