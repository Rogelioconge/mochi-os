#!/usr/bin/env python3
"""The battery icon of the status bar and the pull-down (asset-only, no binary patch).

Stock firmware looks up the widgets "img_battery" (icon: bar_power / bar_charge / bar_lowpower) and
"pgbar_battery" (an AWTK progress_bar used as the icon's fill) in ui/system_bar.bin and calls
progress_bar_set_value(pgbar_battery, capacity) on every refresh (demo: dropdown_showface; the
system bar has a twin at 0x545168). So pgbar_battery becomes the horizontal 24x12 interior of a 26x14
body (white level on grey), drawn under the image (stock child order), and the three state images the
body's 1 px rim and nub (grey; red with a sliver at 0; while charging patch/battery.c shows a green level and a bolt over it;
tools/battery_art.py, shared with the lock screen). The Battery Percentage's number is tools/statusbar.py battery_parts. Applied to the status bar and to the
pull-down's own bar.

Usage: mod_battery.py STOCK_WORKDIR OUT_WORKDIR
  (STOCK_WORKDIR is what fwtool.py unpack produced; OUT_WORKDIR is cloned from it and modified.)
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, battery_art
from modlib import clone_workdir, edit_ui, write_keep_mode

UI = 'rootfs/release/assets/default/raw/ui/system_bar.bin'
DROPDOWN = 'rootfs/release/assets/default/raw/ui/dialog/dropdown_dialog.bin'
IMAGES = 'rootfs/release/assets/default/raw/images/xx/{name}.png'
ICON_W, ICON_H = battery_art.STATUS.canvas          # 28 x 14: the body and the nub (the lock screen uses the same pictures)
# the state images the app swaps between; the stock 14x20 files, pinned
STATE = {'bar_power': 'normal', 'bar_charge': 'charge', 'bar_lowpower': 'low'}
STOCK_ICONS = {'bar_power': 'fc28dc349da0', 'bar_charge': 'fceb7082b5cc', 'bar_lowpower': '1b2410d4038f'}

def icon_gauge(root):
    """img_battery -> the 26x14 rim and nub ending at the stock icon's right edge, vertically centred in the
    30 px bar; pgbar_battery -> its 24x12 interior, horizontal, white on the body's grey, no text.
    Returns the icon's x."""
    pg, img = root.find('pgbar_battery'), root.find('img_battery')
    assert (pg.x, pg.y, pg.w, pg.h) == (296, 8, 14, 17) and (img.x, img.y, img.w, img.h) == (296, 5, 14, 20), 'not the stock battery'
    assert pg.get('vertical') == 'true' and pg.get('show_text') == 'false' and img.get('image') == 'bar_power'
    img.x, img.y, img.w, img.h = img.x + img.w - ICON_W, (30 + 1 - ICON_H) // 2, ICON_W, ICON_H   # 282, 8: the nub ends at 310, as stock
    img.set('draw_type', 'default')                                      # 1:1
    fx, fy, fw, fh = battery_art.STATUS.fill
    pg.x, pg.y, pg.w, pg.h = img.x + fx, img.y + fy, fw, fh              # 283, 9, 24 x 12
    pg.set('vertical', 'false')
    for k, v in (('border_width', '0'), ('round_radius', '0'), ('bg_color', battery_art.EMPTY), ('fg_color', '#FFFFFF')):
        pg.set(f'style:normal:{k}', v)
    return img.x

def apply_icon_files(out):
    """The three state images and the pull-down's own battery."""
    done = []
    for name, state in STATE.items():
        p = os.path.join(out, IMAGES.format(name=name))
        old = open(p, 'rb').read()
        assert hashlib.sha256(old).hexdigest()[:12] == STOCK_ICONS[name], f'{p}: not the stock icon'
        new = battery_art.png(battery_art.STATUS, state); write_keep_mode(p, new); done.append((p, len(old), len(new)))
    p = os.path.join(out, DROPDOWN)
    def edit(root):
        right = root.find('view_bar_right'); assert right is not None
        x = icon_gauge(root); right.x = x - 4 - right.w
    o, n, _ = edit_ui(p, edit); done.append((p, len(o), len(n)))
    return done

def apply(root):
    right = root.find('view_bar_right')
    assert right is not None, 'unexpected system_bar layout'
    x = icon_gauge(root)
    right.x = x - 4 - right.w       # keep the right-aligned Bluetooth/SyncLink/Wi-Fi group clear of the icon
    return root

def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    stock_dir, out = sys.argv[1:]
    clone_workdir(stock_dir, out)
    stock, new, root = edit_ui(os.path.join(out, UI), apply)
    print(f'{UI} {len(stock)} -> {len(new)} bytes')
    for p, o, n in apply_icon_files(out): print(f'{os.path.relpath(p, out)} {o} -> {n} bytes')
    awtk_ui.dump(root.find('view_bar_right')); awtk_ui.dump(root.find('pgbar_battery')); awtk_ui.dump(root.find('img_battery'))

if __name__ == '__main__': main()
