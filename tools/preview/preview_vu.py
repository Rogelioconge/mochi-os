#!/usr/bin/env python3
"""out/preview/vu-final.png (+ vu-final@2x.png): the chosen VU Meter Mode design (docs/modules/vu.md), playing and paused, drawn by tools/vu_art.py `design` (the code
the build's pictures use: the installed base, hood and lamp pictures with the needle drawn over them as the page does). The track's text is the tree's own font
(preview_icons.Side, StbFont); the dial print is the committed Inter subset (vu_art.FONT). Sample data; the page itself is not built yet.

  preview_vu.py [WORKDIR [OUT.png]]   (unpacked release work tree, only its font is read; default out/preview/vu-final.png)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, paths, preview_icons as PI, vu_art

J = dict(title='Midnight City', artist='M83', len=243, pos=200, fmt='FLAC', vol=42, clock='21:07', vu=(-2.4, 1.3), peak=(False, True))
FRAMES = [('Playing', dict(J, playing=True)), ('Paused', dict(J, playing=False, peak=(False, False)))]


def main():
    work = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else next(p for p in (os.path.join(paths.WORK, 'mod-release'), os.path.join(paths.MAIN, 'work', 'mod-release')) if os.path.isdir(p))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'vu-final.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True); base = os.path.splitext(out)[0]
    imgs = vu_art.images()
    frames = [(t, vu_art.compose(f, imgs)) for t, f in FRAMES]
    for (t, im), (_, f) in zip(frames, FRAMES): vu_art.text(s, im, f)
    for k, name in ((1, out), (2, base + '@2x.png')):
        pad, lab, W, H = 12 * k, 22, vu_art.W, vu_art.H
        sheet = Image.new('RGB', (pad + len(frames) * (W * k + pad), pad + lab + H * k + pad), (0x1A,) * 3); d = ImageDraw.Draw(sheet)
        for i, (t, im) in enumerate(frames):
            x = pad + i * (W * k + pad)
            d.text((x, pad), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste((im.resize((W * k, H * k), Image.NEAREST) if k > 1 else im).convert('RGB'), (x, pad + lab))
        sheet.save(name, optimize=True); print('wrote', name, sheet.size)


if __name__ == '__main__':
    main()
