#!/usr/bin/env python3
"""out/preview/batthist.png: Settings > Battery (the Battery History row) and its page, Battery History (patch/bhpage.c, docs/modules/batthist.md "History page"): the switch off (the page as it was), on with nothing complete yet (the empty note) and
on with a day of fake data (the whole page, with the Since Last Charge card). Drawn from the built tree's own ui/m1plus_battery.bin, strings and font; the three bitmaps (the Since Last Charge card, the two charts) are tools/batthist_model.py's, the pixels test/pod/batthist.py
checks the payload against. Approximate (PIL, not AWTK).

Usage: uv run python -I tools/preview/preview_batthist.py WORKDIR [OUT.png]     (en_US; default out/preview/batthist.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import awtk_ui, build, batthist_model as HM, preview_icons as PI, preview_settings as PS, pod_pages as P, pod_settings as ST

RAW, W, NAV, SCREEN = PI.RAW, PS.W, PS.NAV, PS.SCREEN
HEAD = 1800000000 // 900 + 3 + 4 * 24     # 2027-01-16 08:45 UTC
GREY = (0x8A,) * 3
GAP, CHG = 2, 1
SINCE_CHARGE = (3 * 3600 + 53 * 60, 2 * 3600 + 12 * 60, 31 * 3600 + 20 * 60)   # the mock's run since the last charge, which is longer than the day: sc_play, sc_on, sc_total
UNPLUG = (21, 25, 100)   # when the charger was removed (local hour, minute) and the gauge then


def fake_day():
    """A day like the mock: a long discharge down to the red, a charge to 100 %, a discharge with some use (tuples of struct bh_bucket)."""
    b = []
    for i in range(96):
        if i < 3: b.append((255, GAP, 0, 0, 0, 0, 0, 0)); continue
        if i < 30: lev, fl = 58 - (i - 3), 0
        elif i < 52: lev, fl = min(100, 31 + (i - 30) * 4), CHG
        else: lev, fl = 100 - (i - 52) * 2 // 3, 0
        on = (40 if i % 9 in (0, 1) else 0) + (25 if i in (88, 89, 90, 91, 92) else 0)
        play = 80 if i % 7 in (2, 3) and i < 30 else (90 if 60 <= i < 66 else 0)
        play = min(play, 112 - on)
        cov = min(113, on + play + (20 if i < 85 else 0))
        drop = 0 if fl else (1 if i % 5 == 0 else 0)
        b.append((lev, fl, on, play, cov, drop if on > play else 0, drop if play >= on else 0, 1 if i % 4 == 0 and not fl else 0))
    return b


def totals(b):
    t = dict(t_on=0, t_play=0, t_idle=0, d_on=0, d_play=0, d_idle=0, act_on=0, act_play=0)
    for k in b:
        if k[1] & GAP: continue
        t['act_on'] += k[2] * 8; t['act_play'] += k[3] * 8
        if k[1] & CHG: continue
        idle = max(0, k[4] - k[2] - k[3])
        t['t_on'] += k[2] * 8; t['t_play'] += k[3] * 8; t['t_idle'] += idle * 8
        t['d_on'] += k[5]; t['d_play'] += k[6]; t['d_idle'] += k[7]
    return t


def bitmap(model):
    im = Image.new('RGBA', (len(model[0]), len(model)))
    im.putdata([(r, g, b, a) for row in model for a, r, g, b in row])
    return im


def label(s, im, c, y, text, font=None):
    """One of the card's labels (a view child with its own style) at the item's y."""
    px, al = int(PS.style(c, 'font_size')), PS.style(c, 'text_align_h')
    x = c.x + (c.w if al == 'right' else 0)
    s.text(im, x, y + c.y + c.h / 2, text, px, PS.rgb(PS.style(c, 'text_color')), 'r' if al == 'right' else 'l', font)


def hist_items(s, im, d, c, y, mode, b, tz, h24):
    """The Since Last Charge card or a chart of the page, at y (c: the item from the asset)."""
    n = c.name
    if n == 'pod_hist0':
        play, on, total = SINCE_CHARGE
        im.alpha_composite(bitmap(HM.render_summary(on, play, total)), (ST.CM, y))
        level = b[-1][0]
        texts = {'pod_hs_cap': HM.caption_text(HM.clock_text(UNPLUG[0], UNPLUG[1], h24), UNPLUG[2]), 'pod_hs_dur': HM.dur_text(total), 'pod_hs_left': f'{level}% left',
                 'pod_hs_d0': HM.dur_text(on), 'pod_hs_d1': HM.dur_text(play), 'pod_hs_d2': HM.dur_text(total - on - play)}
        for w in c.children:
            if w.name in texts: label(s, im, w, y, texts[w.name], s.title_face(texts[w.name]) if w.name == 'pod_hs_dur' else None)
            elif w.name.startswith('pod_hs_n'): label(s, im, w, y, s.shown(w))
        return
    lv = n == 'pod_hist1'
    im.alpha_composite(bitmap(HM.render_level(b, HEAD, tz) if lv else HM.render_activity(b, HEAD, tz)), (ST.CM, y))
    axis = ('100%', '50%', '0%') if lv else ('60 min', '30 min', '0')
    py0, ph = (HM.LPY0, HM.LPH) if lv else (HM.APY0, HM.APH)
    for yy, text in zip((py0, py0 + ph // 2, py0 + ph), axis): s.text(im, ST.CM + HM.OFF['BHC_AXIS_X'], y + yy, text, 13, GREY)
    for i, hour in HM.ticks(HEAD, tz):
        s.text(im, ST.CM + HM.tick_x(i), y + (HM.OFF['BHL_TICK_Y'] if lv else HM.OFF['BHA_TICK_Y']), HM.hour_text(hour, h24, 'level' if lv else 'activity'), 13, GREY, 'm')
    if not lv:
        for (x, _), text in zip(((30, 90), (140, 150)), ('Screen On', 'Playing, Screen Off')): s.text(im, ST.CM + x, y + HM.ALEG, text, 14, PS.rgb(ST.GREY))


def battery(s, on):
    """Settings > Battery: the Battery History row with its value and chevron (on: the setting)."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', P.BATTERY_PAGE.key + '.bin'), 'rb').read())
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    end = sum(c.h for c in sv.children)
    im = Image.new('RGBA', (W, NAV + end), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    y = NAV
    for c in sv.children:
        if c.type == 'list_item': PS.draw_row(s, im, d, c, y, {'pod_value1': '100%', 'pod_value2': 'On' if on else 'Off'}, {'pod_switch0': True}, set())
        else: PS.draw_text_item(s, im, c, y, texts={})
        y += c.h
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    lt = root.find('label_title'); tpx = PI.title_px(s.tree)
    s.text(im, lt.x, NAV / 2, s.clip(s.shown(lt), tpx, lt.w), tpx, (255, 255, 255))
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im.convert('RGB')


def page(s, mode, b=None, tz=0, h24=1):
    """The Battery History page in a state: 'off', 'empty' or 'data' (b: the ring). The payload shows the History items of the state; hidden ones are skipped as the layouter does."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', P.BATTHIST_PAGE.key + '.bin'), 'rb').read())
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    show = {'off': set(), 'empty': {'pod_note2'}, 'data': {'pod_sec0', 'pod_hist0', 'pod_sec1', 'pod_hist1', 'pod_sec2', 'pod_hist2', 'pod_sec3', 'pod_row1', 'pod_row2', 'pod_row3', 'pod_note1'}}[mode]
    stats = {}
    if mode == 'data':
        t = totals(b)
        for k, (secs, drop) in enumerate(((t['t_on'], t['d_on']), (t['t_play'], t['d_play']), (t['t_idle'], t['d_idle']))):
            next(w for w in root.walk() if w.name == f'pod_sub{1 + k}').set('text', HM.dur_text(secs))
            stats[1 + k] = HM.stat_text(drop)
    kids = [c for c in sv.children if c.get('visible') != 'false' or c.name in show]
    end = sum(c.h for c in kids)
    im = Image.new('RGBA', (W, NAV + end), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    y = NAV
    for c in kids:
        if c.type == 'list_item':
            PS.draw_row(s, im, d, c, y, {}, {'pod_switch0': mode != 'off'}, set())
            k = int(c.name[7:])
            if k in stats:   # an On Battery row: its kind's mark and the bold white estimate at the right ink edge (draw_row's value is the About row's box)
                mk = next(w for w in c.children if w.name == 'pod_mark')
                d.rounded_rectangle((mk.x, y + mk.y, mk.x + mk.w - 1, y + mk.y + mk.h - 1), HM.SMARK_R, fill=PS.rgb(PS.style(mk, 'bg_color')))
                s.text(im, ST.RIGHT, y + c.h / 2, stats[k], ST.STAT_PX, (255, 255, 255), 'r', s.title_face(stats[k]))
        elif c.name.startswith('pod_hist'): hist_items(s, im, d, c, y, mode, b, tz, h24)
        else: PS.draw_text_item(s, im, c, y, texts={})
        y += c.h
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    lt = root.find('label_title'); tpx = PI.title_px(s.tree)
    s.text(im, lt.x, NAV / 2, s.clip(s.shown(lt), tpx, lt.w), tpx, (255, 255, 255))
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im.convert('RGB')


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'batthist.png')
    s = PI.Side(sys.argv[1], True, 'en_US'); s.mark = lambda *a: None
    b = fake_day()
    shots = [('Settings > Battery (on)', battery(s, True).crop((0, 0, W, SCREEN))), ('Battery History: off', page(s, 'off').crop((0, 0, W, SCREEN))), ('On, nothing complete yet', page(s, 'empty').crop((0, 0, W, SCREEN))), ('On, a day of data', page(s, 'data', b))]
    pad = 12
    hei = max(im.height for _, im in shots) + 44 + pad
    out = Image.new('RGB', (sum(im.width for _, im in shots) + pad * (len(shots) + 1), hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    x = pad
    for title, im in shots:
        d.text((x, 24), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im, (x, 44)); x += im.width + pad
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, optimize=True); print('wrote', out_path, out.size)


if __name__ == '__main__':
    main()
