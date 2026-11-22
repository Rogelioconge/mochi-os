#!/usr/bin/env python3
"""The Pod's Cover Flow album card at 1:1 device pixels: the settled card (before: the 6 px side shadow and the darker edge;
now: neither) and the 3D flip turning the card's own picture, text included. The frames come from the host build of
patch/coverflow.c (test/coverflow.py); the card's face is painted as patch/ipod.c ip_paint_card_body paints it, in the
tree's font.

  preview_ipod_card.py WORKDIR [OUT.png]     (unpacked release work tree; venv python; default out/preview/ipod-card.png)
"""
import ctypes, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'test'))
from PIL import Image, ImageDraw
import build, preview_icons as PI, pod_ui, preview_ipod as P
import coverflow as host   # test/coverflow.py: the host build and its cfg_t

O = pod_ui.OFFSETS
W, SH = 320, 240
CX, CY, CW, CH, HDR, ROWS = (O[k] for k in ('IPCF_CARD_X', 'IPCF_CARD_Y', 'IPCF_CARD_W', 'IPCF_CARD_H', 'IPCF_CARD_HDR', 'IPCF_CARD_ROWS'))
FY, FH = O['IPCF_FRAME_Y'], O['IPCF_FRAME_H']
TRACKS = ['So What', 'Freddie Freeloader', 'Blue in Green', 'All Blues', 'Flamenco Sketches', 'So What (Alt)', 'Blue in Green (Alt)']


def awtk(v):
    """An AWTK colour word (r | g << 8 | b << 16, as patch/ipod.c writes them) as an RGB tuple."""
    return (v & 255, v >> 8 & 255, v >> 16 & 255)


def stops(colors, at, y, h):
    """patch/ipod.c ip_stops."""
    p = y * 100 // (h - 1) if h > 1 else 0
    i = 1
    while i < len(colors) and p > at[i]: i += 1
    if i >= len(colors): return colors[-1]
    a, b, n = colors[i - 1], colors[i], at[i] - at[i - 1] + 1
    k = p - at[i - 1]
    return tuple(a[j] + (b[j] - a[j]) * k // (n - 1 if n > 1 else 1) for j in range(3))


def face(s, edge):
    """The card alone (CW x CH), as ip_paint_card_body: header, edge, white rows, the selection on row 1."""
    im = Image.new('RGBA', (CW, CH), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    ly, lh = HDR + 1, CH - HDR - 1
    d.rectangle((0, 0, CW - 1, HDR), fill=awtk(0xb8976b)); d.rectangle((0, ly, CW - 1, CH - 1), fill=awtk(edge))
    d.rectangle((1, ly, CW - 2, CH - 1), fill=(255, 255, 255))
    hdr_c = [awtk(v) for v in (0xe4ae5a, 0xebbc6d, 0xf6d196)]
    d.line((1, 1, CW - 2, 1), fill=awtk(0xe8bb74))
    for i in range(2, HDR): d.line((1, i, CW - 2, i), fill=stops(hdr_c, (0, 45, 100), i - 2, HDR - 2))
    d.line((1, HDR, CW - 2, HDR), fill=awtk(0xbc9252))
    s.text(im, 10, 4 + 21 / 2, 'Kind of Blue', 18, (255, 255, 255))
    s.text(im, 10, 24 + 17 / 2, 'Miles Davis', 16, (255, 255, 255))
    sel_c = [awtk(v) for v in (0xe3ab3e, 0xe0a037, 0xdc972c, 0xd68c21, 0xd38415)]
    for i, t in enumerate(TRACKS[:ROWS]):
        y = ly + i * lh // ROWS; h = ly + (i + 1) * lh // ROWS - y
        if i == 1:
            for r in range(h):
                c = awtk(0xf8dd9a) if r == 0 else awtk(0x814f15) if r == h - 1 else stops(sel_c, (0, 25, 50, 75, 100), r, h)
                d.line((1, y + r, CW - 2, y + r), fill=c)
        s.text(im, 10, y + h / 2, t, 18, (255, 255, 255) if i == 1 else (0, 0, 0))
    return im


def flip_frame(lib, texs, u, face_img):
    """The 3D flip frame at u (0 .. 256) as ipod_cf.c draw_flip_frame asks for it: the face as its texture."""
    cfg = host.CFG(320, FH, 160, O['IPCF_TOP'], O['IPCF_ART'], O['IPCF_EYE'], O['IPCF_X1'], O['IPCF_XS'], O['IPCF_Z1'], O['IPCF_ZS'],
                   O['IPCF_REFLECT'], 0, O['IPCF_TURN'], O['IPCF_TAIL'], O['IPCF_BG'], 0, O['IPCF_SPREAD'], O['IPCF_DECK_Z'], 0)
    buf = (ctypes.c_uint * (320 * FH))()
    ring = (ctypes.c_void_p * host.RING)(*[ctypes.cast(t, ctypes.c_void_p) for t in texs])
    raw = face_img.convert('RGBA').tobytes()   # r, g, b, a bytes: the little-endian word r | g << 8 | b << 16 | a << 24
    fbuf = (ctypes.c_uint * (CW * CH)).from_buffer_copy(raw)
    lib.coverflow_flip(ctypes.byref(cfg), buf, 320, u, ring, CY - FY, CW, CH, HDR, ROWS, 1, 160, 1, ctypes.cast(fbuf, ctypes.c_void_p))
    im = Image.new('RGBA', (320, FH)); im.putdata([(v & 255, v >> 8 & 255, v >> 16 & 255, 255) for v in buf])
    return im


def old_shadow(frame):
    """The settled card's former 6 px shadow either side (the removed coverflow_flip u == 256 pass)."""
    px = frame.load(); x0, x1 = 160 - CW // 2, 160 + CW // 2
    for y in range(max(0, CY - FY), min(FH, CY - FY + CH)):
        for i, k in enumerate((196, 212, 226, 238, 246, 252)):
            for x in (x0 - 1 - i, x1 + i):
                if 0 <= x < 320: r, g, b, a = px[x, y]; px[x, y] = (r * k >> 8, g * k >> 8, b * k >> 8, 255)


def screen(s, th, frame, card=None):
    im = Image.new('RGBA', (W, SH), th.bg + (255,)); im.alpha_composite(frame, (0, FY))
    if card is not None: im.alpha_composite(card, (CX, CY))
    P.title_bar(s, im, th, 'Cover Flow')
    return im


def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'ipod-card.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True); th = P.Theme(False)
    with tempfile.TemporaryDirectory() as tmp:
        lib = host.build(tmp)
        texs = [host.texture(rgb) for _, rgb in P.ALBUMS[:host.RING]]
        new, old = face(s, 0xd4cec8), face(s, 0xbeb4a8)
        rest = flip_frame(lib, texs, 256, new)
        before = rest.copy(); old_shadow(before)
        shots = [('Before: shadow + darker edge', screen(s, th, before, old)), ('Now: settled card', screen(s, th, rest, new))]
        shots += [(f'Flip u={u}', screen(s, th, flip_frame(lib, texs, u, new))) for u in (150, 190, 230)]
    pad, lab = 12, 22
    sheet = Image.new('RGB', (pad + len(shots) * (W + pad), SH + lab + 2 * pad), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(shots):
        x = pad + i * (W + pad)
        d.text((x, pad - 2), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    P.save_true(sheet, out); print('wrote', out, sheet.size)


if __name__ == '__main__':
    main()
