#!/usr/bin/env python3
"""The status bar's glyphs (docs/ui.md "Status bar"): one 14 px tall, filled, iOS-like set.

Every mark is drawn here in 8x supersampled PIL shapes (no SVG) at a common ink height of GLYPH_H px, in pixel
coordinates, and placed in its stock canvas (tools/statusbar.py sets the right group's boxes to the canvases): centred, or at
the canvas's left (volume) or right (Bluetooth and the codec tags, at the 47 px box's right edge like stock). The right group is spaced by shape, not by box
(tools/statusbar.py RGAP): Wi-Fi and the camera fill their canvas's width, and the moon, SyncLink and the sync arrows carry 3, 2 and 1 px
of empty canvas on the left, so a mark with a full left side sits further from its left neighbour than the Wi-Fi fan does.
Unlit parts (Wi-Fi bands, Bluetooth off) are DIM grey. The codec tags are bold text (Inter Bold) at CODEC_CAP px
capitals; Line Out is a GLYPH_H px amber pill with black bold "LO". The battery is tools/battery_art.py.

Used by tools/mod_icons.py --generate (the committed PNGs in assets/icons/png).
"""
import math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOLD = os.path.join(ROOT, 'assets', 'fonts', 'Inter-Bold-m1plus.ttf')
CAP = 0.727                     # Inter's capital height per em
GLYPH_H, SS = 14, 8
ON, DIM = (255, 255, 255, 255), (0x5A, 0x5A, 0x5A, 255)
AMBER, BLACK = (0xFF, 0xD6, 0x0A, 255), (0, 0, 0, 255)
CODEC_CAP, LO_CAP = 10, 9
CODECS = {'bar_sbc': 'SBC', 'bar_aac': 'AAC', 'bar_aptx': 'aptX', 'bar_aptxhd': 'aptX HD', 'bar_ldac': 'LDAC'}

class _C:
    """A w x GLYPH_H px drawing in pixel coordinates, supersampled. Straight edges sit on whole pixels so they stay sharp."""
    def __init__(self, w):
        from PIL import Image, ImageDraw
        self.w = w; self.im = Image.new('RGBA', (w * SS, GLYPH_H * SS), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.im)
    def P(self, pts): return [(x * SS, y * SS) for x, y in pts]
    def poly(self, pts, col): self.d.polygon(self.P(pts), fill=col)
    def rrect(self, x0, y0, x1, y1, r, col): self.d.rounded_rectangle((x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1), radius=r * SS, fill=col)
    def circle(self, cx, cy, r, col): self.d.ellipse(((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS), fill=col)
    def line(self, pts, w, col):      # round caps and joins
        self.d.line(self.P(pts), fill=col, width=round(w * SS), joint='curve')
        for x, y in pts: self.circle(x, y, w / 2, col)
    def arc(self, cx, cy, r, a0, a1, w, col):   # degrees, 0 = up, clockwise
        n = 40; pts = [(cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a))) for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]
        self.line(pts, w, col)
    def band(self, cx, cy, r0, r1, half, col):   # a ring sector r0..r1 over +-half degrees about straight up, ends cut along the radius
        n = 40; ang = [math.radians(-half + 2 * half * i / n) for i in range(n + 1)]
        self.poly([(cx + r1 * math.sin(a), cy - r1 * math.cos(a)) for a in ang] + [(cx + r0 * math.sin(a), cy - r0 * math.cos(a)) for a in reversed(ang)], col)
    def soft_poly(self, pts, r, col):    # a polygon grown by r, so its corners are rounded by r
        self.poly(pts, col); self.line(pts + [pts[0]], 2 * r, col)
    def done(self): return self.im.reduce(SS)

def play():
    c = _C(12); c.soft_poly([(2, 2), (10, 7), (2, 12)], 1.0, ON); return c.done()

def pause():
    c = _C(10); c.rrect(1, 1, 4, 13, 1.2, ON); c.rrect(6, 1, 9, 13, 1.2, ON); return c.done()

def speaker(level):
    """bar_vol0..4: the speaker (a box and a flared cone, as macOS draws it) with 0..3 waves; 4 = muted (an x)."""
    c = _C({0: 10, 4: 19}.get(level, 22))
    c.rrect(0, 4, 6, 10, 1.5, ON); c.soft_poly([(5, 5), (8.5, 1.5), (8.5, 12.5), (5, 9)], 1.0, ON)   # box and cone
    if level == 4:
        c.line([(13, 4.5), (18, 9.5)], 1.6, ON); c.line([(13, 9.5), (18, 4.5)], 1.6, ON)
    else:
        for r, a in ((3.4, 52), (6.9, 44), (10.4, 36))[:level]: c.arc(10.5, 7, r, 90 - a, 90 + a, 1.5, ON)
    return c.done()

def wifi(level):
    """bar_wifi0..4: three bands (the wedge, the middle, the outer); stock's levels 1 / 2 / 3-4 light one / two / three."""
    c = _C(16); cx, cy, half = 8, 13.75, 38                     # the apex; the bands are cut along the radius
    lit = lambda n: ON if level >= n else DIM
    r, R = 1.5, 5.0                                             # the wedge: a sector with corners rounded by r
    tip = (cx, cy - r / math.sin(math.radians(half)))
    cut = half - math.degrees(math.asin(r / (R - r)))
    c.soft_poly([tip] + [(cx + (R - r) * math.sin(math.radians(-cut + 2 * cut * i / 12)), cy - (R - r) * math.cos(math.radians(-cut + 2 * cut * i / 12))) for i in range(13)], r, lit(1))
    c.band(cx, cy, 6.4, 9.1, half, lit(2))
    c.band(cx, cy, 10.3, 13.0, half, lit(3))
    return c.done()

def bluetooth(on):
    c = _C(10); col = ON if on else DIM
    c.line([(1.0, 3.5), (9.0, 10.2), (5, 13), (5, 1), (9.0, 3.8), (1.0, 10.5)], 2.0, col); return c.done()

def synclink(on):
    """bar_synclink / bar_synclinkcon: stock's mark, two hooks locked into an S, as one bold line."""
    c = _C(14); col = ON if on else DIM; r = 3.875
    semi = lambda cx, cy, side: [(cx + side * r * math.sin(math.radians(180 * i / 16)), cy - r * math.cos(math.radians(180 * i / 16))) for i in range(17)]   # top to bottom round one side
    c.line([(13, 1)] + semi(1 + r, 1 + r, -1) + [(8.5, 1 + 2 * r)], 2.0, col)      # the upper hook: open to the right
    c.line([(5.5, 13 - 2 * r)] + semi(13 - r, 13 - r, 1) + [(1, 13)], 2.0, col)    # the lower hook: open to the left
    return c.done()

def plug():
    c = _C(12); c.rrect(3, 0, 5, 5, 0.9, ON); c.rrect(7, 0, 9, 5, 0.9, ON)
    c.rrect(1, 4, 11, 10, 3.0, ON); c.rrect(5, 9, 7, 14, 0.9, ON); return c.done()

def moon():
    from PIL import Image, ImageDraw
    c = _C(14); m = Image.new('L', c.im.size, 0); d = ImageDraw.Draw(m)
    k = SS; d.ellipse((0, 0, 14 * k - 1, 14 * k - 1), fill=255); d.ellipse((3.4 * k, -3.6 * k, 16.6 * k, 9.6 * k), fill=0)
    c.im.paste(Image.new('RGBA', c.im.size, ON), (0, 0), m); return c.done()

def sync():
    c = _C(15); cx, cy, r = 7.5, 7, 5.1
    c.arc(cx, cy, r, 300, 420, 1.9, ON); c.arc(cx, cy, r, 120, 240, 1.9, ON)
    c.poly([(cx + 6.8, 1.2), (cx + 7.5, 6.3), (cx + 2.6, 4.7)], ON)      # the upper arc's head
    c.poly([(cx - 6.8, 12.8), (cx - 7.5, 7.7), (cx - 2.6, 9.3)], ON)     # the lower arc's head
    return c.done()

def camera():
    c = _C(16); c.rrect(0, 3, 16, 14, 2.5, ON); c.rrect(5, 1, 11, 5, 1.4, ON)
    lens = _C(16); lens.circle(8, 8.5, 3.6, ON)
    from PIL import ImageChops
    a = ImageChops.subtract(c.im.getchannel('A'), lens.im.getchannel('A')); c.im.putalpha(a)   # the lens a hole
    c.circle(8, 8.5, 2.1, ON); return c.done()

def _font(cap):
    from PIL import ImageFont
    return ImageFont.truetype(BOLD, round(cap / CAP * SS))

def text(s, col=ON, cap=CODEC_CAP, max_w=None):
    """Bold text, capitals `cap` px tall and centred on GLYPH_H; smaller until it is at most max_w px wide."""
    from PIL import Image, ImageDraw
    while True:
        f = _font(cap); l, t, r, b = f.getbbox(s, anchor='ls')
        if max_w is None or (r - l) / SS <= max_w or cap <= 6: break
        cap -= 0.5
    w = math.ceil((r - l) / SS) + 1; im = Image.new('RGBA', (w * SS, GLYPH_H * SS), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-l, (GLYPH_H + cap) * SS / 2), s, font=f, fill=col, anchor='ls'); return im.reduce(SS)

def lo_pill():
    from PIL import Image, ImageDraw
    f = _font(LO_CAP); l, t, r, b = f.getbbox('LO', anchor='ls')
    w = math.ceil((r - l) / SS) + 7; im = Image.new('RGBA', (w * SS, GLYPH_H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * SS - 1, GLYPH_H * SS - 1), radius=GLYPH_H * SS // 2, fill=AMBER)
    d.text(((w * SS - (r - l)) / 2 - l, (GLYPH_H + LO_CAP) * SS / 2), 'LO', font=f, fill=BLACK, anchor='ls'); return im.reduce(SS)

def place(g, cw, ch, align='c'):
    """g in a cw x ch transparent canvas, vertically centred; align 'l' / 'c' / 'r'."""
    from PIL import Image
    assert g.width <= cw and g.height <= ch, f'{g.size} does not fit {cw} x {ch}'
    x = {'l': 0, 'r': cw - g.width}.get(align, (cw - g.width) // 2)
    c = Image.new('RGBA', (cw, ch), (255, 255, 255, 0)); c.alpha_composite(g, (x, (ch - g.height) // 2)); return c

def ink_crop(im):
    bb = im.getchannel('A').getbbox(); return im.crop((bb[0], 0, bb[2], im.height)) if bb else im

def images():
    """{file name: RGBA image}: every status bar glyph at its stock canvas size."""
    f = {'bar_play': place(play(), 14, 18), 'bar_pause': place(pause(), 14, 18),
         'bar_bt': place(ink_crop(bluetooth(False)), 47, 20, 'r'), 'bar_btcon': place(ink_crop(bluetooth(True)), 47, 20, 'r'),
         'bar_digital': place(plug(), 18, 18),
         'bar_synclink': place(synclink(False), 16, 16, 'r'), 'bar_synclinkcon': place(synclink(True), 16, 16, 'r'),
         'pod_bar_shot': place(camera(), 16, 16), 'pod_bar_sync': place(sync(), 16, 18, 'r'), 'pod_bar_sleep': place(moon(), 17, 16, 'r'),
         'pod_bar_lo': place(lo_pill(), 26, 16)}
    for i in range(5):
        f[f'bar_vol{i}'] = place(speaker(i), 24, 18, 'l'); f[f'bar_wifi{i}'] = place(wifi(i), 16, 16)
    for n, s in CODECS.items(): f[n] = place(ink_crop(text(s, max_w=46)), 47, 18, 'r')
    return f
