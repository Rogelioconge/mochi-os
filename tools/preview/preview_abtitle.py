#!/usr/bin/env python3
"""Mock-up of a two-line album title on the album page (docs/modules/album-page.md): the 22 px title wraps at a space (a character only without a usable space) into at most two
lines (m1_wrap2), the second cut with an ellipsis; a two-line title moves the artist, the year line, Shuffle + Play and the rows down by one O['AH_TITLE_LH'] line. A PIL approximation laid out
from the AH_* numbers (patch/offsets.inc). Sample data.

  preview_abtitle.py WORKDIR OUTDIR

WORKDIR is a built tree. Writes abtitle-sheet.png to OUTDIR: the album page and a playlist's header (preview_songs.py), each with a short and a long title.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview_icons as PI, preview_songs as PS

TITLE_PX, ARTIST_PX, META_PX = 22, 18, 15


def page(s, title, artist, meta, tracks, two, rgb):
    O = PI.offsets()
    im = Image.new('RGBA', (320, 450), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    for y in range(450): d.line((0, y, 319, y), fill=tuple(int(c * .3) for c in rgb) + (255,))
    im.alpha_composite(PI.rounded(PI.sample_cover(rgb, O['AH_ART']), O['AH_CORNER']), (O['AH_ART_X'], O['AH_ART_Y']))
    lines = PS.wrap2(s, title, TITLE_PX, O['AH_TEXT_W']) if two else [s.clip(title, TITLE_PX, O['AH_TEXT_W'])]
    dy = (len(lines) - 1) * O['AH_TITLE_LH']
    for i, t in enumerate(lines): s.text(im, 160, O['AH_TITLE_Y'] + i * O['AH_TITLE_LH'] + O['AH_TITLE_H'] / 2, t, TITLE_PX, anchor='m')
    s.text(im, 160, O['AH_ARTIST_Y'] + dy + O['AH_ARTIST_H'] / 2, s.clip(artist, ARTIST_PX, O['AH_TEXT_W']), ARTIST_PX, (0xAA,) * 3, anchor='m')
    s.text(im, 160, O['AH_META_Y'] + dy + O['AH_META_H'] / 2, meta, META_PX, (0x9C,) * 3, anchor='m')
    PS.play_header(s, im, O['AH_BTN_Y'] + dy + 2)
    row = O['AB_ROW_H']; x = O['AB_NUM_X'] + O['ROW_NUM_W']
    for i, t in enumerate(tracks):
        y = O['AH_HDR_H'] + dy + i * row
        if y >= 450: break
        d.rectangle((0, y + row - 1, 309, y + row - 1), fill=(0x3A, 0x3A, 0x3E))
        s.text(im, x, y + O['AB_NUM_Y'] + O['AB_TEXT_H'] / 2, str(i + 1), O['AB_NUM_PX'], (0xAA,) * 3, 'r')
        s.text(im, x + O['AB_NUM_GAP'], y + O['AB_TEXT_Y'] + O['AB_TEXT_H'] / 2, s.clip(t, 20, 269 - x - O['AB_NUM_GAP']), 20)
        s.text(im, 278, y + row / 2 - 4, '···', 24, (0x8C,) * 3)
    PS.glass(s, im, 'ah_nav_back', 7, 44); PS.glass(s, im, 'ah_nav_play', 260, 60); PS.glass(s, im, 'pod_nav_more', 214)
    return im


def label(im, text):
    out = Image.new('RGBA', (im.width, im.height + 24), (0x2A, 0x2A, 0x2A, 255)); out.alpha_composite(im, (0, 24))
    ImageDraw.Draw(out).text((6, 6), text, fill=(255, 255, 255))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('outdir')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True); os.makedirs(a.outdir, exist_ok=True)
    long_t = 'The Rise and Fall of Ziggy Stardust and the Spiders from Mars'
    tracks = ['Five Years', 'Soul Love', 'Moonage Daydream', 'Starman']
    pl = lambda t: PS.page(s, title=t, head=True, search=False, direct=True)
    shots = (('Album: short title (unchanged)', page(s, 'Kind of Blue', 'Miles Davis', '1959 · 5 tracks', ['So What', 'Freddie Freeloader', 'Blue in Green'], True, (40, 60, 105))),
             ('Album: long title, two lines', page(s, long_t, 'David Bowie', '1972 · 11 tracks', tracks, True, (120, 70, 40))),
             ('Playlist: short name (unchanged)', pl('Late Night')),
             ('Playlist: long name, two lines', pl('Late Night Drive: Songs for the Long Way Home')))
    sheet = Image.new('RGBA', (len(shots) * 330 + 10, 474 + 10), (0x2A, 0x2A, 0x2A, 255))
    for i, (t, im) in enumerate(shots): sheet.alpha_composite(label(im, t), (5 + i * 330, 5))
    sheet.convert('RGB').save(os.path.join(a.outdir, 'abtitle-sheet.png'))
    print('wrote abtitle-sheet.png to', a.outdir)


if __name__ == '__main__':
    main()
