#!/usr/bin/env python3
"""out/preview/battery.png: the status bar's and the lock screen's battery from a built tree,
states empty / half / full / charging / low at 8x, then with the Battery Percentage's number, with the
body's grey, the app's progress-bar fill and the image drawn exactly where the tree's ui files put them.
Also asserts the fill rectangle is the art's interior and the image leaves it clear.

  preview_battery.py TREE OUT.png          (an unpacked work tree of a full-icons build; venv python)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
import awtk_ui, battery_art as B

from awtk_ui import RAW
Z = 8
ANN = ImageFont.load_default(13)

def geometry(tree, ui, img_name, pg_name):
    root = awtk_ui.parse(open(os.path.join(tree, RAW, 'ui', ui), 'rb').read())
    img, pg = root.find(img_name), root.find(pg_name)
    fill = (pg.x - img.x, pg.y - img.y, pg.w, pg.h)
    return root, img, pg, fill

def draw(tree, root, spec, imgs, fill, bg, level, number):
    """Level 0..100 -> the pgbar fill width as AWTK's progress bar draws it (inside its box), over the body's grey (the lighter one with the number)."""
    import preview_theme as PT
    w, h = spec.canvas
    im = Image.new('RGBA', (w, h), bg)
    fx, fy, fw, fh = fill
    charging = os.path.basename(imgs) in ('bar_charge.png', 'screens_charge.png')   # patch/battery.c bp_face: the green level, a bolt, white digits on the darker grey
    img = root.find('img_battery'); grey = next(v for v in root.walk() if v.name.startswith('pod_pct_bg' if number and not charging else 'pod_bat_bg'))
    ImageDraw.Draw(im).rectangle((fx, fy, fx + fw - 1, fy + fh - 1), fill=PT.rgba(grey.get('style:normal:bg_color')))
    green = next(v for v in root.walk() if v.name.startswith('pod_chg_lvl'))
    n = round(fw * level / 100)
    if n: ImageDraw.Draw(im).rectangle((fx, fy, fx + n - 1, fy + fh - 1), fill=PT.rgba(green.get('style:normal:fg_color')) if charging else (255, 255, 255, 255))
    im.alpha_composite(Image.open(imgs).convert('RGBA'))
    small = charging and number and level < 100
    if charging and (small or not number):
        b = next(v for v in root.walk() if v.name.startswith('pod_chg_bolts' if small else 'pod_chg_bolt') and (small or not v.name.startswith('pod_chg_bolts')))
        im.alpha_composite(Image.open(os.path.join(os.path.dirname(imgs), b.get('image') + '.png')).convert('RGBA'), (b.x - img.x, b.y - img.y))
    if number:
        lab = next(v for v in root.walk() if v.type == 'label' and v.name.startswith('pod_pct'))
        if charging:
            lab = awtk_ui.Widget(lab.type, lab.x, lab.y, B.PCT_W_CHG if small else lab.w, lab.h, list(lab.props)); lab.set('style:normal:text_color', '#FFFFFF')
        PT.face_text(im, os.path.join(tree, RAW), lab, str(level), -img.x, -img.y)
    return im

def check_fill(spec, png_path, fill):
    """The fill box must be inside the outline's inner edge, and the image's pixels there empty (transparent)."""
    assert tuple(fill) == tuple(spec.fill), (fill, spec.fill)
    a = Image.open(png_path).convert('RGBA'); fx, fy, fw, fh = fill
    for y in range(fy, fy + fh):
        for x in range(fx, fx + fw):
            assert a.getpixel((x, y))[3] < 255 or png_path.endswith(('lowbattery.png', 'bar_lowpower.png')), (x, y, a.getpixel((x, y)))   # (the rim's antialiased inner corners; the low picture's sliver)

def main():
    tree, out = sys.argv[1:3]
    xx = os.path.join(tree, RAW, 'images/xx')
    sets = [('Status bar (bar_power / bar_charge / bar_lowpower, black bar)', B.STATUS, 'system_bar.bin', 'img_battery', 'pgbar_battery',
             {'normal': 'bar_power', 'charge': 'bar_charge', 'low': 'bar_lowpower'}, (0, 0, 0, 255)),
            ('Lock screen (screens_battery / screens_charge / screens_lowbattery, over the card)', B.STATUS, 'screensaver_page.bin', 'img_battery', 'pgbar_battery',
             {'normal': 'screens_battery', 'charge': 'screens_charge', 'low': 'screens_lowbattery'}, (0x40, 0x3A, 0x38, 255))]
    cols = [('half', 'normal', 50, 0), ('charging 20%', 'charge', 20, 0), ('charging 50%', 'charge', 50, 0), ('charging 90%', 'charge', 90, 0), ('low (0%)', 'low', 0, 0),
            ('87', 'normal', 87, 1), ('charging 8', 'charge', 8, 1), ('charging 63', 'charge', 63, 1), ('charging 88', 'charge', 88, 1), ('charging 100', 'charge', 100, 1), ('5 (low)', 'low', 5, 1)]
    rows = []
    for title, spec, ui, iname, pname, files, bg in sets:
        root, img, pg, fill = geometry(tree, ui, iname, pname)
        assert (img.w, img.h) == spec.canvas, (img.w, img.h, spec.canvas)
        for f in files.values(): check_fill(spec, os.path.join(xx, f + '.png'), fill)
        print(f'{title.split(" (")[0]}: image {img.w}x{img.h} at ({img.x},{img.y}), pgbar fill box {fill} inside the image; checked on all three state images')
        rows.append((title, [(lab, draw(tree, root, spec, os.path.join(xx, files[st] + '.png'), fill, bg, lv, num)) for lab, st, lv, num in cols]))
    cw = B.STATUS.canvas[0] * Z + 20
    sh = Image.new('RGB', (len(cols) * cw + 20, 2 * (B.STATUS.canvas[1] * Z + 70) + 30), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sh)
    d.text((10, 6), 'One battery design, 8x nearest-neighbour; the white fill is the app\'s progress bar drawn under the image.', fill=(255, 255, 255), font=ANN)
    y = 30
    for title, ims in rows:
        d.text((10, y), title, fill=(0xAA,) * 3, font=ANN); y += 22
        for i, (lab, im) in enumerate(ims):
            x = 10 + i * cw
            sh.paste(im.resize((im.width * Z, im.height * Z), Image.NEAREST).convert('RGB'), (x, y))
            d.text((x, y + im.height * Z + 4), lab, fill=(255, 255, 255), font=ANN)
        y += B.STATUS.canvas[1] * Z + 46
    sh.crop((0, 0, sh.width, y)).save(out); print('wrote', out)

if __name__ == '__main__': main()
