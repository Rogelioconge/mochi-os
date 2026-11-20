#!/usr/bin/env python3
"""Preview of a multi-disc album (docs/modules/album-page.md "Layout"): out/preview/album-discs.png is the album page's list with its "Disc N" headings (AB_DISC_H bands, the
grey AB_DISC_PX line AB_DISC_Y down at AB_NUM_X) and numbers from 1 on each disc, at the top of the list and around the second heading, in English, Chinese and Japanese.
Rows at the payload's own numbers (patch/offsets.inc AH_* AB_*), drawn with the built font and the tree's strings tables. Approximate, not AWTK; sample data.

  uv run python -I tools/preview/preview_discs.py WORKDIR [OUT.png]     (WORKDIR: a built tree, e.g. out/dev/<tag>/tree)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import preview_icons as PI, pod_i18n

O = PI.offsets()
NUM, HEAD = (0xAA, 0xAA, 0xAA), (0xAA, 0xAA, 0xAA)   # label_row_num and label_row_disc: SUB_RGB
DISCS = [(1, ['Intro', 'Speak to Me', 'Breathe', 'On the Run', 'Time']), (2, ['Money', 'Us and Them', 'Any Colour You Like', 'Brain Damage', 'Eclipse'])]


def page(s, scroll):
    """The list from the header's foot (patch/albumpage.c ab_row_y / ab_head_y): each disc's heading band, then its rows, under the 30 px status bar."""
    row, hdr, win, dh = O['AB_ROW_H'], O['AH_HDR_H'], O['AH_WIN_H'], O['AB_DISC_H']
    im = Image.new('RGBA', (320, 30 + win), (0x24, 0x24, 0x28, 255))
    d = ImageDraw.Draw(im)
    y = 30 + hdr - scroll
    for disc, names in DISCS:
        s.text(im, O['AB_NUM_X'], y + O['AB_DISC_Y'] + O['AB_TEXT_H'] / 2, s.strings['Disc %d'].replace('%d', str(disc)), O['AB_DISC_PX'], HEAD)
        y += dh
        for i, name in enumerate(names):
            d.rectangle((0, y + row - 1, 309, y + row - 1), fill=(0x3A, 0x3A, 0x3E))
            s.text(im, O['AB_NUM_X'] + O['ROW_NUM_W'], y + O['AB_NUM_Y'] + O['AB_TEXT_H'] / 2, str(i + 1), O['AB_NUM_PX'], NUM, 'r')
            s.text(im, O['AB_NUM_X'] + O['ROW_NUM_W'] + O['AB_NUM_GAP'], y + O['AB_TEXT_Y'] + O['AB_TEXT_H'] / 2, name, 20)
            y += row
    d.rectangle((0, 0, 319, 29), fill=(0, 0, 0))
    return im


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    tree = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(HERE)), 'out', 'preview', 'album-discs.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    hdr, row, dh = O['AH_HDR_H'], O['AB_ROW_H'], O['AB_DISC_H']
    second = hdr + dh + len(DISCS[0][1]) * row   # the second heading's top: show it a third of the way down
    cases = [(loc, sc) for loc in ('en_US', 'zh_CN', 'ja_JP') for sc in (hdr - 40, second - 160)]
    sheet = Image.new('RGBA', (3 * 330, 2 * 490), (0, 0, 0, 255))
    for j, (loc, sc) in enumerate(cases):
        sheet.alpha_composite(page(PI.Side(tree, True, loc), sc), ((j // 2) * 330 + 5, (j % 2) * 490 + 5))
    sheet.convert('RGB').save(out)
    assert all(pod_i18n.TEXT['Disc %d'][loc] for loc in pod_i18n.LOCALES)
    print(out)


if __name__ == '__main__': main()
