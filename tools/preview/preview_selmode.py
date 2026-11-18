#!/usr/bin/env python3
"""Mock-up of one select mode for every page (docs/modules/songs.md "Select"): the album page's select mode, design "A+" (the x where Back was, "N Selected" / "Select Items",
Select All / Deselect All at the right, the 64 px bar in the page's tone with a fade above it and translucent pills).
The album rows (marks in the 30 px column, numbers and titles shifted) are the page's own already. Approximate, not AWTK; sample data.

  preview_selmode.py WORKDIR OUT.png [--lang CODE]
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview_icons as PI
import preview_songs as PS
from preview_rowmenu import TRACKS, TONE

O = PI.offsets()
ROW, NAV, W = O['AB_ROW_H'], PS.NAV, PS.W


def rows(s, im, marked, scroll, playing=2):
    """The album page's tracks in select mode (patch/albumpage.c ab_paint): the mark in the 30 px column, number and title shifted by SG_SEL_COL, no "..."."""
    d = ImageDraw.Draw(im)
    on, off = s.img('selected'), s.img('unselect')
    sh = O['SG_SEL_COL']
    tx = O['AB_NUM_X'] + O['ROW_NUM_W'] + O['AB_NUM_GAP'] + sh
    for i in range(len(TRACKS)):
        y = O['AH_HDR_H'] + i * ROW - scroll
        if y + ROW < 0 or y > im.height: continue
        d.rectangle((0, y + ROW - 1, 309, y + ROW - 1), fill=(0x55, 0x3A, 0x40))
        mk = on if i in marked else off
        im.alpha_composite(mk, (O['LIST_ART_X'] + (sh - 6 - mk.width) // 2, y + (ROW - mk.height) // 2))
        if i == playing: im.alpha_composite(s.img('ah_wave'), (O['AB_NUM_X'] + sh + O['ROW_NUM_W'] - O['AB_WAVE'], y + O['AB_WAVE_Y']))
        else: s.text(im, O['AB_NUM_X'] + sh + O['ROW_NUM_W'], y + O['AB_NUM_Y'] + O['AB_TEXT_H'] / 2, str(i + 1), O['AB_NUM_PX'], (0xAA, 0xAA, 0xAA), 'r')
        s.text(im, tx, y + O['AB_TEXT_Y'] + O['AB_TEXT_H'] / 2, s.clip(TRACKS[i], 20, O['AB_ROW_W'] - tx - 10), 20)


def glass(s, im, name, x, w):
    g = s.img(name); im.alpha_composite(g, (x + (w - g.width) // 2, (NAV - g.height) // 2))


DIM = 0.35   # a disabled glyph / label (nothing marked)


def faded(g, k):
    a = g.getchannel('A').point(lambda v: int(v * k)); g = g.copy(); g.putalpha(a); return g


def title_text(s, n, count):
    return 'Select Items' if n == 0 else s.strings.get('%d Selected', '%d Selected').replace('%d', str(n))


def rows_hl(s, im, marked, scroll):
    """rows() plus a faint fill on the marked rows."""
    for i in marked:
        y = O['AH_HDR_H'] + i * ROW - scroll
        top, bot = max(0, y), min(im.height, y + ROW - 1)
        if bot > top: im.alpha_composite(Image.new('RGBA', (310, bot - top), (255, 255, 255, 0x12)), (0, top))
    rows(s, im, marked, scroll)


def album_bar(s, marked, scroll=300):
    """Polished A: the Songs chrome, but "Select Items" with nothing marked, "Deselect All" once all are, the bar in the page's tone (a fade above it, translucent pills) so the
    tinted page does not end in a black slab, the pills dim while nothing is marked, the marked rows lit faintly."""
    im = Image.new('RGBA', (W, O['AH_WIN_H']), TONE + (255,))
    rows_hl(s, im, marked, scroll)
    glass(s, im, 'ah_nav_close', 7, 44)
    s.text(im, O['NAV_TITLE_X'], 25, title_text(s, len(marked), len(TRACKS)), PI.title_px(s.tree))
    sa = 'Deselect All' if len(marked) == len(TRACKS) else PS.tr(s, 'Select All')   # (a new string: English only in the mock)
    s.text(im, W - 12 - s.font.width(sa, 18), 25, sa, 18)
    win, bar, fade = im.height, PS.BAR_H, 24
    base = tuple(c * 3 // 4 for c in TONE)
    for k in range(fade): im.alpha_composite(Image.new('RGBA', (W, 1), base + (255 * k // fade,)), (0, win - bar - fade + k))
    ImageDraw.Draw(im).rectangle((0, win - bar, W - 1, win - 1), fill=base)
    py = win - bar + (bar - PS.PILL_H) // 2
    on = bool(marked)
    for x, label, g in ((O['SG_PILL_X0'], 'Add to Playlist', 'sg_listplus'), (O['SG_BAR_PILL_X1'], 'Delete', 'sg_trash')):
        pill = Image.new('RGBA', (O['SG_BAR_PILL_W'], PS.PILL_H), (0, 0, 0, 0))
        mask = Image.new('L', pill.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pill.width - 1, pill.height - 1), radius=PS.PILL_R, fill=255)
        im.paste(Image.alpha_composite(Image.new('RGBA', pill.size, base + (255,)), Image.new('RGBA', pill.size, (255, 255, 255, 0x1E))), (x, py), mask)
        lab = PS.tr(s, label); tw = s.font.width(lab, 18); gl = s.img(g); gx = x + (O['SG_BAR_PILL_W'] - (PS.GLYPH + PS.GAP + tw)) // 2
        im.alpha_composite(gl if on else faded(gl, DIM), (gx, py + (PS.PILL_H - gl.height) // 2))
        rgb = (0xFF, 0x6B, 0x6B) if label == 'Delete' else (0xFF, 0xFF, 0xFF)
        s.text(im, gx + PS.GLYPH + PS.GAP, py + PS.PILL_H / 2, lab, 18, rgb if on else tuple(int(c * DIM + b * (1 - DIM)) for c, b in zip(rgb, base)))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    _, heads, _ = PS.build_items()
    two, every = {1, 3}, set(range(len(TRACKS)))
    panels = [              ('A+ : nothing marked (pills dim)', album_bar(s, set())),
              ('A+ : 2 marked', album_bar(s, two)),
              ('A+ : all marked (Deselect All)', album_bar(s, every))]
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, 450 + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (title, im) in enumerate(panels):
        x = pad + i * (W + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    PI.save_compact(sheet, a.out)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
