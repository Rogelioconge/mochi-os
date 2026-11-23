#!/usr/bin/env python3
"""Build MOX OS's own Home AWTK resource, separate from the regular M1+ Music menu.

The stock Shanling launcher is NOT replaced in this sprint. Only the entry
window uses mox_home.bin; its original menu remains m1plus_menu.bin.

Run from tools/build.py *after* mod_icons has added the menu's row images:
    mod_mox_native.py WORKDIR WORKDIR
"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awtk_ui
from pod_ui import UI_MODE, UI_MTIME

UI = Path(awtk_ui.RAW) / 'ui'
SOURCE = 'm1plus_menu.bin'
NATIVE = 'mox_home.bin'
NAME = 'mox_home_page'
ROW_COUNT = 26


def added_rels(stock_rootfs=None, *args):
    """Declare the new rootfs file to the firmware repacker."""
    return [f'release/assets/default/raw/ui/{NATIVE}']


def transform(data):
    root = awtk_ui.parse(data)
    if awtk_ui.serialize(root) != data or (root.type, root.name) != ('window', 'm1plus_menu_page'):
        raise ValueError('Not a canonical compiled m1plus_menu window')
    nav, lv, sv = (root.find(n) for n in ('navigationbar_view', 'pod_listview', 'pod_scrollview'))
    if not nav or not lv or not sv or len([w for w in root.walk() if w.name.startswith('pod_row')]) != ROW_COUNT:
        raise ValueError('Incomplete entry menu: navigation or rows are missing')
    if not all(root.find(n) for n in ('pod_minibar', 'pod_pins', 'pod_daily', 'pod_shelf')):
        raise ValueError('The new Home must retain the mini-player and library modules')
    for i in range(ROW_COUNT):
        row = root.find(f'pod_row{i}')
        if row is None or len(row.children) < 2 or row.children[0].name != f'mox_card{i}' or row.children[1].name != 'pod_icon':
            raise ValueError(f'MOX card/icon pair {i} is missing: run mod_icons first')
    # Unlike the normal menu, MOX is an explicit Home entry resource. Its
    # navbar is initially hidden, then the existing home_menu_opened() checks
    # the full tree and adjusts list geometry before accepting the window.
    root.set('name', NAME)
    nav.set('visible', 'false')
    nav.set('sensitive', 'false')
    built = awtk_ui.serialize(root)
    if awtk_ui.serialize(awtk_ui.parse(built)) != built:
        raise AssertionError('MOX Home AWTK resource did not round-trip')
    return built


def apply(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() != output.resolve():
        raise ValueError('Expected an in-place build step on the temporary build tree')
    src = source / UI / SOURCE
    dst = source / UI / NATIVE
    if not src.is_file():
        raise FileNotFoundError(src)
    built = transform(src.read_bytes())
    if dst.exists():
        if dst.read_bytes() != built:
            raise ValueError('MOX Home resource already exists with different content')
        print('MOX native Home: existing identical resource verified')
        return
    dst.write_bytes(built)
    os.chmod(dst, UI_MODE)
    os.utime(dst, (UI_MTIME, UI_MTIME))
    print(f'MOX native Home: {NATIVE} generated, {len(built)} bytes (stock Home untouched)')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: mod_mox_native.py WORKDIR WORKDIR')
    apply(sys.argv[1], sys.argv[2])
