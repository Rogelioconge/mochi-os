#!/usr/bin/env python3
"""MOX test compatibility: exact seven-field inverse and strict integrity checks.

Uses a fixture built from the initial Shanling V2.1 stock Home resource,
modified by mod_theme. Does not touch any installed firmware.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'test'), str(ROOT / 'test' / 'pod')]
import awtk_ui
import mod_mox_home


def get_revert():
    # The navbars module normally runs within the Unicorn test harness.
    # Extract just its pure home normalizer without importing that harness.
    import ast
    src = (ROOT / 'test/pod/navbars.py').read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pre_mox_home')
    code = compile(ast.Module(body=[fn], type_ignores=[]), '<mox-integrity-test>', 'exec')
    ns = {'awtk_ui': awtk_ui}
    exec(code, ns)
    return ns['pre_mox_home']


def sample():
    from mox_home import sample as make_sample
    t = make_sample()
    t.find('home_bottomview').set('style:normal:bg_color', '#000000')
    t.find('home_scrlabel_artist').set('style:normal:text_color', '#AAAAAA')
    t.find('home_sindicator').set('style:normal:selected_fg_color', '#EEEEEE')
    t.find('home_sindicator').set('style:normal:fg_color', '#555555')
    return t


def main():
    revert = get_revert()
    base = awtk_ui.serialize(sample())
    mox = awtk_ui.serialize(mod_mox_home.transform(awtk_ui.parse(base)))
    assert revert(mox) == base
    print('OK: MOX home normalization restores the pre-MOX asset exactly')
    t = awtk_ui.parse(mox)
    t.find('home_scrlabel_artist').set('style:normal:font_size', '17')
    try:
        revert(awtk_ui.serialize(t))
    except AssertionError:
        print('OK: unexpected MOX font change is rejected')
    else:
        raise AssertionError('an unexpected MOX style was accepted')
    t = awtk_ui.parse(mox)
    t.find('home_bottomview').set('style:normal:bg_color', '#FFFFFF')
    try:
        revert(awtk_ui.serialize(t))
    except AssertionError:
        print('OK: unexpected MOX background change is rejected')
    else:
        raise AssertionError('an unexpected MOX background was accepted')
    t = awtk_ui.parse(mox)
    t.find('home_scrlabel_title').x += 1
    assert revert(awtk_ui.serialize(t)) != base
    print('OK: unexpected geometry remains in digest (cannot be hidden)')
    print('MOX integrity compatibility: 4/4 checks OK')


if __name__ == '__main__':
    main()
