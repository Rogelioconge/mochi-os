#!/usr/bin/env python3
"""The VU Meter page's art (docs/modules/vu.md): the drawing code of the approved mock "A4", shared by the preview (tools/preview/preview_vu.py `design`), the
build (`images()`: the installed pictures; tools/mod_icons.py puts them in the tree, assets/icons/png keeps the generated files) and test/pod/vu.py (the numbers).

The page is PORTRAIT, 320 x 480, fullscreen (no status bar), like Vinyl and Cassette: a brushed aluminium faceplate with two cream needle meters (LEFT above RIGHT) lit
softly from three bulbs above, a small black hood at each pivot, a PEAK lamp, the Vinyl page's close chevron, status line, text lines and round
keys (its 'white' key theme). Nothing under the main scale but "VU". The dial print is Jost (see FONT), drawn at 1x so it stays crisp.

Installed pictures (the page composes them at run time; every one drawn at K x and reduced, deterministic):
  vu_base   320 x 480 RGBA, opaque: faceplate, both dials without needles, hoods, unlit PEAK lamps, dial print, keys at rest (play glyph), chevron. No text labels.
  vu_hood   HOOD_RECT (84 x 18), RGBA: the hood, the same over each dial (HOOD_AT); the page draws it OVER the needle's root.
  vu_lamp   LAMP_RECT (33 x 31), RGBA: the lit PEAK lamp with its glow, the same over each dial (LAMP_AT); drawn over the base while the lamp is on, and the base's rect
            restored to switch it off.
  vu_keys   KEY_SHEET: opaque cells of the key band (as vinyl_keys, same KEY_CELLS / KEY_COLS / BAND_Y), cut from the base in each look: play key with the pause glyph
            (cell 46: shown while playing), play at rest and pressed, previous and next pressed.
The needle is NOT a picture: the page draws it at run time (`draw_needle` is the reference, `needle_rect` / `move_rect` its dirty rectangles).

The needle (geometry the C page ports). Angles `a` run clockwise from straight up, radians: a unit axis u = (sin a, -cos a), its normal n = (cos a, sin a); the pivot
PIVOTS[m] is a pixel corner (page coordinates, below the window: the hood hides the root). For a pixel centre p = (x + .5, y + .5): t = (p - pivot) . u, d = (p - pivot) . n.
  needle   half width hw(t) = HW_ROOT + (HW_TIP - HW_ROOT) * (t - R0) / (R1 - R0); coverage = clamp(hw + .5 - |d|, 0, 1) * clamp(t - R0 + .5, 0, 1) * clamp(R1 - t + .5, 0, 1);
           colour NEEDLE_RGB, composed over the page pixel by coverage.
  shadow   the same shape at (t, d) of the pixel moved by -SHADOW_DX, -SHADOW_DY, blurred by a gaussian of sigma SHADOW_SIGMA: alpha SHADOW_ALPHA / 255 times
           0.5 (erf((hw - d') / (sigma sqrt 2)) + erf((hw + d') / (sigma sqrt 2))) times 0.5 (erf((t' - R0) / (sigma sqrt 2)) + erf((R1 - t') / (sigma sqrt 2))), black, composed before
           the needle. (A C port may use a small table of the erf ramp; the needle is thin, so hw is taken at the middle of the span.)
  clip     every pixel is clipped to the dial's window (WINDOWS[m]); the hood is drawn after the needle.
  dirty    `needle_rect(m, a)`: the bounding box of the needle's four corners, grown by RECT_PAD on every side and by the shadow's offset on the right / bottom, clipped
           to the window. A move is `move_rect(m, a0, a1)`: the union of the two; the page restores that rectangle from vu_base, draws the needle, then the hood and
           the lamp (when lit) over what they touch.
Scale (deflection follows the voltage): `frac(vu) = 10^(vu / 20) / 10^(3 / 20)` of the sweep; the angle is -SWEEP + min(1.03, frac) * 2 SWEEP (SWEEP 46 degrees);
rest (parked, nothing playing) is REST (SWEEP + 2.5 degrees to the left of the scale's start).
"""
import math, os, random, sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (-I drops the script's directory)
import vinyl_art as VA

W, H, K = 320, 480, 3
S = lambda v: int(round(v * K))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'assets', 'vu', 'Jost-Medium-vu.ttf')           # the dial print: Jost (OFL, assets/vu/OFL-Jost.txt), a geometric face like the ones old meters were printed in;
FONT_BOLD = os.path.join(ROOT, 'assets', 'vu', 'Jost-Bold-vu.ttf')        # wght 500 and 700 instances of the variable font, cut to the print's characters; build-time only (not installed)

# ---- the page's layout (framebuffer px) -------------------------------------------------------------------------------------------------------------
NAMES = ('vu_base', 'vu_hood', 'vu_lamp', 'vu_keys')
BOXES = ((12, 26, 308, 180), (12, 188, 308, 342))                        # the recessed frames: meter 0 (LEFT, above), meter 1 (RIGHT)
FRAME_R, FRAME_DEPTH = 9, 5                                              # their corner radius; the frame's width: the window is inside it
WINDOWS = tuple((b[0] + FRAME_DEPTH, b[1] + FRAME_DEPTH, b[2] - FRAME_DEPTH, b[3] - FRAME_DEPTH) for b in BOXES)   # the dials (286 x 144): what a needle is clipped to
DIAL_W, DIAL_H = 286, 144
CX, CY = DIAL_W // 2, DIAL_H + 36                                        # a dial's pivot, in the dial's own pixels (the pivot is 36 px below the window)
PIVOTS = tuple((w[0] + CX, w[1] + CY) for w in WINDOWS)                  # page coordinates: (160, 211) and (160, 373)
SCALE_R = 139                                                            # the scale's arc radius from the pivot
R0, R1 = 20, SCALE_R + 12                                                # the radius range the needle is drawn over (151: 12 px past the scale)
HW_ROOT, HW_TIP = 1.1, 0.5                                               # the needle's half widths: 2.2 px at the root, 1.0 px at the tip
NEEDLE_RGB = (0x16, 0x13, 0x10)
SHADOW_DX, SHADOW_DY, SHADOW_SIGMA, SHADOW_ALPHA = 4, 5, 1.6, 120
RECT_PAD = 6                                                             # what the shadow's blur and the edge's antialiasing reach beyond the needle's corners
SWEEP = math.radians(46)                                                 # the scale's half sweep
REST = -SWEEP - math.radians(2.5)                                        # the needle's rest (parked) angle
VU_MIN, VU_MAX = -20, 3
HOOD_RECT = (118, 157, 202, 175)                                         # vu_hood on meter 0 (the hood's box inside the window); meter 1's is 162 px lower
LAMP_RECT = (270, 144, 303, 175)                                         # vu_lamp on meter 0; the lamp's centre is (286, 160)
LAMP_C = (DIAL_W - 17, DIAL_H - 15)                                      # the lamp's centre in the dial's pixels
METER_DY = BOXES[1][1] - BOXES[0][1]                                     # 162: meter 1 sits this far below meter 0
HOOD_AT = tuple((HOOD_RECT[0], HOOD_RECT[1] + m * METER_DY) for m in (0, 1))
LAMP_AT = tuple((LAMP_RECT[0], LAMP_RECT[1] + m * METER_DY) for m in (0, 1))
KEYS, KEY_Y, BAND_Y, KEY_COLS, KEY_CELLS, KEY_SHEET = VA.KEYS, VA.KEY_Y, VA.BAND_Y, VA.KEY_COLS, VA.KEY_CELLS, VA.KEY_SHEET   # the Vinyl page's, unchanged
CHEVRON, CLOSE_RECT = VA.CHEVRON, VA.CLOSE_RECT
# the text: AWTK labels (px, line middle y, x, width, rgb), as the Vinyl page's, the title and artist lower than its (the dials take the middle of the page)
TEXT = {
    'title':  dict(x=16, y=367, px=22, rgb=(0x1A, 0x1A, 0x1C), w=288),
    'artist': dict(x=16, y=391, px=15, rgb=(0x3C, 0x3C, 0x40), w=288),
    'times':  dict(x=16, y=449, px=12, rgb=(0x4E, 0x4E, 0x52), w=140),
    'status': dict(x=34, y=12, px=10, rgb=(0x4E, 0x4E, 0x52), w=200),
}

FACE = (0xC6, 0xC4, 0xBF)
WINDOW_BG = FACE                                                         # the page window's own background (the view hides it)
FACE_AMP = 0.085
MARKS = [(-20, '20'), (-10, '10'), (-7, '7'), (-5, '5'), (-3, '3'), (-2, '2'), (-1, '1'), (0, '0'), (1, '1'), (2, '2'), (3, '3')]
MINOR = [-15, -8, -6, -4, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
# the dial: cream paper lit by three bulbs above (soft pools), lightened toward the bottom; ink, red zone, a small black hood
DIAL = dict(hot=(0xF4, 0xEF, 0xE2), edge=(0xDA, 0xCB, 0xA6), ink=(0x1E, 0x1A, 0x14), red=(0xC2, 0x26, 0x1C), bulbs=(0xFF, 0xD4, 0x7C), pool=(105, 70), vig=55,
            paper=6, frame=(0x1C, 0x1C, 0x1E), hood=(0x1A, 0x1A, 0x1C), glass=20)


def label_box(name):
    """(x, y, w, h) of a text label: the line's middle at TEXT y (text_align_v middle), px + 4 high (as vinyl_art.label_box)."""
    t = TEXT[name]; h = t['px'] + 4
    return (t['x'], t['y'] - h // 2, t['w'], h)


def frac(vu):
    """A VU meter's deflection follows the voltage: 0 VU sits at 71 % of the sweep (the fraction of the full sweep, 1 at +3 VU)."""
    return 10 ** (vu / 20) / 10 ** (3 / 20)


def angle(vu):
    """The needle's angle (radians from straight up) for a level in VU; None (nothing playing): REST. Over +3 VU the needle stops 3 % past the end."""
    return REST if vu is None else -SWEEP + min(1.03, frac(vu)) * 2 * SWEEP


# ---- small image helpers (3x) -----------------------------------------------------------------------------------------------------------------------
def scale(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)


def shift(m, dx, dy):
    """m moved by (dx, dy) without ImageChops.offset's wrap-around."""
    out = Image.new(m.mode, m.size, 0); out.paste(m, (int(dx), int(dy))); return out


def rr(size, box, r):
    m = Image.new('L', size, 0); ImageDraw.Draw(m).rounded_rectangle(box, r, fill=255); return m


def fill(im, m, rgb, a=255):
    layer = Image.new('RGBA', im.size, tuple(rgb) + (0,)); layer.putalpha(m.point(lambda v: v * a // 255)); im.alpha_composite(layer)


def noise(w, h, seed):
    r = random.Random(seed); return Image.frombytes('L', (w, h), bytes(r.randrange(256) for _ in range(w * h)))


def brushed(size, base, amp, seed, top=1.10, bottom=0.90):
    """Brushed metal: horizontal streaks at two widths, a top-lit vertical falloff."""
    w, h = size
    a = noise(w // 60 + 2, h, seed).resize(size, Image.BICUBIC)
    b = noise(w // 9 + 2, h, seed + 1).resize(size, Image.BICUBIC)
    n = Image.blend(a, b, 0.4)
    im = ImageOps.colorize(n, scale(base, 1 - amp), scale(base, 1 + amp), mid=base)
    g = Image.linear_gradient('L').resize(size)   # 0 top .. 255 bottom
    lit = ImageOps.colorize(g, scale((255, 255, 255), min(1, top - 0.0)), (int(255 * bottom / top),) * 3)
    return ImageChops.multiply(im, lit).convert('RGBA')


def radial(size, cx, cy, r, inner, outer):
    g = Image.radial_gradient('L').resize((2 * r, 2 * r), Image.BICUBIC)
    c = Image.new('L', size, 255); c.paste(g, (cx - r, cy - r))
    return ImageOps.colorize(c, inner, outer)


def recess(im, box, r, frame, depth=5):
    """A window let into the faceplate: a lit lower lip, a dark frame, and the inner box (3x) the dial fills."""
    x0, y0, x1, y1 = [S(v) for v in box]; size = im.size
    fill(im, shift(rr(size, (x0, y0, x1, y1), S(r)), 0, K), (255, 255, 255), 70)      # the lip below catches the light
    fill(im, shift(rr(size, (x0, y0, x1, y1), S(r)), 0, -K), (0, 0, 0), 110)          # the edge above is in shade
    m = rr(size, (x0, y0, x1, y1), S(r))
    g = Image.linear_gradient('L').resize(size)
    layer = ImageOps.colorize(g, scale(frame, 0.55), scale(frame, 1.5)).convert('RGBA'); layer.putalpha(m); im.alpha_composite(layer)
    return (x0 + S(depth), y0 + S(depth), x1 - S(depth), y1 - S(depth))


def inner_shadow(size, r, dy, blur, a):
    """Alpha of the shade the frame throws on what lies under the glass (strongest along the top)."""
    w, h = size; pad = S(12)
    m = Image.new('L', (w + 2 * pad, h + 2 * pad), 255); ImageDraw.Draw(m).rounded_rectangle((pad, pad, pad + w, pad + h), r, fill=0)
    m = shift(m.filter(ImageFilter.GaussianBlur(blur)), 0, dy).crop((pad, pad, pad + w, pad + h))
    return m.point(lambda v: v * a // 255)


def glass(dial, a=16):
    """The window's glass: a soft diagonal reflection and a faint glow across the top."""
    w, h = dial.size
    band = Image.new('L', (w, h), 0); d = ImageDraw.Draw(band)
    d.polygon([(w * 0.04, 0), (w * 0.46, 0), (w * 0.20, h), (-w * 0.22, h)], fill=255)
    d.polygon([(w * 0.52, 0), (w * 0.60, 0), (w * 0.34, h), (w * 0.26, h)], fill=150)
    band = band.filter(ImageFilter.GaussianBlur(S(5)))
    fade = Image.linear_gradient('L').resize((w, h)).point(lambda v: 255 - v * 200 // 255)
    fill(dial, ImageChops.multiply(band, fade), (255, 255, 255), a)


# ---- the dial (3x) ------------------------------------------------------------------------------------------------------------------------------------
def pt(a, r):
    """A point on the dial at angle a, radius r from the pivot, in the dial's own 1x pixels."""
    return (CX + r * math.sin(a), CY - r * math.cos(a))


def dial3(C=DIAL):
    """One dial at 3x (RGBA, rounded corners): paper, bulbs, scale ticks and red zone, the unlit lamp, the hood, the frame's shade and the glass. No needle,
    no print (the numerals and letters are put on at 1x, `print_dial`)."""
    w, h = S(DIAL_W), S(DIAL_H); size = (w, h); cx, cy = S(CX), S(CY); R = S(SCALE_R)
    g = noise(w // 2, h // 2, 11).resize(size, Image.BILINEAR).point(lambda v: 128 + (v - 128) * C['paper'] // 128)
    dial = ImageOps.colorize(Image.linear_gradient('L').resize(size), C['hot'], C['edge']).convert('RGBA')
    pools = Image.new('L', size, 0)   # three bulbs behind the frame: soft warm pools at the top
    for fx, rx, ry, a in ((0.20, 66, 58, 235), (0.52, 74, 66, 255), (0.83, 62, 54, 215)):
        spot = ImageOps.invert(Image.radial_gradient('L')).resize((S(2 * rx), S(2 * ry)), Image.BICUBIC).point(lambda v: max(0, v - 36) * a // 219)
        lay = Image.new('L', size, 0); lay.paste(spot, (int(w * fx) - S(rx), -S(ry * 0.72))); pools = ImageChops.lighter(pools, lay)
    pools = pools.filter(ImageFilter.GaussianBlur(S(5)))
    pa, pc = C['pool']
    fill(dial, pools, C['bulbs'], pa); fill(dial, pools.point(lambda v: max(0, v - 110) * 255 // 145), (255, 253, 244), pc)
    vig = ImageOps.invert(radial(size, cx, int(h * 0.42), int(w * 0.72), (255, 255, 255), (0, 0, 0)).convert('L'))
    fill(dial, vig.point(lambda v: max(0, v - 120) * 255 // 135), (0x5A, 0x4A, 0x30), C['vig'])
    dial = ImageChops.overlay(dial.convert('RGB'), Image.merge('RGB', (g, g, g))).convert('RGBA')
    d = ImageDraw.Draw(dial)
    P = lambda a, r: (cx + r * math.sin(a), cy - r * math.cos(a))
    arc = lambda a, b, r, c, wd: d.arc((cx - r, cy - r, cx + r, cy + r), math.degrees(a) - 90, math.degrees(b) - 90, fill=c, width=wd)
    ink, red = C['ink'], C['red']
    a_lo, a_0, a_hi = angle(VU_MIN), angle(0), angle(VU_MAX)
    arc(a_lo, a_0, R, ink, S(1.1)); arc(a_0, a_hi, R + S(5), red, S(6))
    for v, _ in MARKS:
        a = angle(v)
        d.line(P(a, R - S(0.5)) + P(a, R + S(9)), fill=red if v >= 0 else ink, width=S(1.4 if v in (-20, -10, 0, 3) else 1.0))
    for v in MINOR: a = angle(v); d.line(P(a, R) + P(a, R + S(5)), fill=red if v > 0 else ink, width=S(0.7))
    # the peak lamp (unlit; vu_lamp is the lit one)
    lx, ly = S(LAMP_C[0]), S(LAMP_C[1])
    d.ellipse((lx - S(4.2), ly - S(4.2), lx + S(4.2), ly + S(4.2)), fill=(0x20, 0x1C, 0x1A))
    d.ellipse((lx - S(3.2), ly - S(3.2), lx + S(3.2), ly + S(3.2)), fill=(0x5A, 0x16, 0x12))
    d.ellipse((lx - S(1.9), ly - S(2.2), lx - S(0.1), ly - S(0.6)), fill=(0x9A, 0x4A, 0x40))
    # the hood over the pivot: black plastic, a lit top edge (42 px half width: it still covers the parked needle where it crosses the window's bottom edge, 40.7 px from the middle)
    hw, hh = S(42), S(18)
    hr = (hw * hw + hh * hh) / (2 * hh)   # a segment of a circle (radius 58 px: the chord is the window's bottom edge), not half an ellipse
    hood = Image.new('L', size, 0); ImageDraw.Draw(hood).ellipse((cx - hr, h - hh, cx + hr, h - hh + 2 * hr), fill=255)
    fill(dial, shift(hood.filter(ImageFilter.GaussianBlur(S(3))), 0, S(-2)), (0, 0, 0), 120)
    layer = ImageOps.colorize(Image.linear_gradient('L').resize(size).crop((0, 0, w, h)), scale(C['hood'], 2.6), C['hood'], blackpoint=int(255 * (1 - hh / h)), whitepoint=255).convert('RGBA')
    layer.putalpha(hood); dial.alpha_composite(layer)
    fill(dial, ImageChops.subtract(hood, shift(hood, 0, S(1))), (255, 255, 255), 55)
    # under glass
    fill(dial, inner_shadow(size, S(5), S(5), S(6), 255), (0, 0, 0), 150)
    glass(dial, C['glass'])
    dial.putalpha(rr(size, (0, 0, w - 1, h - 1), S(5)))
    return dial, hood


_CACHE = {}
def dial_parts():
    """(the dial at 3x, its hood's mask at 3x), made once."""
    if 'dial' not in _CACHE: _CACHE['dial'] = dial3()
    return _CACHE['dial']


def lamp3():
    """The lit PEAK lamp over the dial's size at 3x, on transparent: a red glow and the lit lamp (opaque discs over the unlit ones)."""
    size = (S(DIAL_W), S(DIAL_H)); lx, ly = S(LAMP_C[0]), S(LAMP_C[1])
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    glow = Image.new('L', size, 0); ImageDraw.Draw(glow).ellipse((lx - S(7), ly - S(7), lx + S(7), ly + S(7)), fill=255)
    fill(out, glow.filter(ImageFilter.GaussianBlur(S(5))), (0xFF, 0x30, 0x18), 200)
    d = ImageDraw.Draw(out)
    d.ellipse((lx - S(4.2), ly - S(4.2), lx + S(4.2), ly + S(4.2)), fill=(0x20, 0x1C, 0x1A, 255))
    d.ellipse((lx - S(3.2), ly - S(3.2), lx + S(3.2), ly + S(3.2)), fill=(0xFF, 0x42, 0x24, 255))
    d.ellipse((lx - S(1.9), ly - S(2.2), lx - S(0.1), ly - S(0.6)), fill=(0xFF, 0xD8, 0xC8, 255))
    return out


# ---- the dial print, at 1x in Jost -----------------------------------------------------------------------------------------------------
_FONTS = {}
def font(bold=False):
    from stb_raster import StbFont
    p = FONT_BOLD if bold else FONT
    if p not in _FONTS: _FONTS[p] = StbFont(p)
    return _FONTS[p]


def put(im, x, y, text, px, rgb, anchor='mm', bold=False):
    """The print: text in FONT / FONT_BOLD (integer px, unhinted stb_truetype like AWTK), its ink centred on (x, y) ('mm'), or its right / left edge at x ('rm' / 'lm')."""
    f = font(bold); m, ox, oy, _ = f.mask(text, px); bb = m.getbbox()
    cx, cy = (bb[0] + bb[2]) / 2 - ox, (bb[1] + bb[3]) / 2 - oy
    ax = {'mm': cx, 'rm': bb[2] - ox, 'lm': bb[0] - ox}[anchor]
    f.draw(im, int(round(x - ax)), int(round(y - cy)), text, px, tuple(rgb) + (255,))


def print_dial(im, m, C=DIAL):
    """The numerals, '-', '+', VU, LEFT / RIGHT and PEAK of meter m onto the 1x page `im`."""
    ox, oy = WINDOWS[m][0], WINDOWS[m][1]
    ink, red = C['ink'], C['red']
    at = lambda a, r: (ox + CX + r * math.sin(a), oy + CY - r * math.cos(a))
    for v, t in MARKS:
        big = v in (-20, -10, 0, 3)
        x, y = at(angle(v), SCALE_R + 18); put(im, x, y, t, 15 if big else 12, red if v > 0 else ink, bold=big)
    x, y = at(angle(VU_MIN) - math.radians(7), SCALE_R + 15); put(im, x, y, '–', 15, ink)
    x, y = at(angle(VU_MAX) + math.radians(6.5), SCALE_R + 15); put(im, x, y, '+', 15, red)
    put(im, ox + CX, oy + DIAL_H - 47, 'VU', 26, ink, bold=True)
    put(im, ox + 13, oy + DIAL_H - 13, ('LEFT', 'RIGHT')[m], 12, ink, 'lm', bold=True)
    put(im, ox + LAMP_C[0] - 9, oy + LAMP_C[1] + 0.5, 'PEAK', 11, ink, 'rm', bold=True)


# ---- the page ----------------------------------------------------------------------------------------------------------------------------------------
def faceplate3():
    """The faceplate with both dials at 3x (no keys)."""
    if 'plate' not in _CACHE:
        im = brushed((S(W), S(H)), FACE, FACE_AMP, 3)
        dial, _ = dial_parts()
        for b in BOXES:
            win = recess(im, b, FRAME_R, DIAL['frame'], FRAME_DEPTH); im.alpha_composite(dial, win[:2])
        _CACHE['plate'] = im
    return _CACHE['plate'].copy()


def base_frame(pause=False, pressed=None):
    """The page's background at 1x RGBA with the keys in one look: vu_base is (play glyph, nothing pressed); the key cells are crops of the others."""
    im = faceplate3()
    VA.use('white')
    try:
        VA.transport(im, pause, pressed)
        out = im.resize((W, H), Image.LANCZOS); VA.chevron(out)
    finally: VA.use('graphite')
    for m in (0, 1): print_dial(out, m)
    return out


def keys_image():
    """vu_keys: KEY_CELLS cut from the band of the base in each look."""
    sheet = Image.new('RGBA', KEY_SHEET, (0, 0, 0, 255)); y0, y1 = BAND_Y
    for (name, state), sx in KEY_CELLS.items():
        im = base_frame(pause=bool(state & 1) if name == 'play' else False, pressed=name if state & 2 else None)
        x0, x1 = KEY_COLS[name]; sheet.paste(im.crop((x0, y0, x1, y1)), (sx, 0))
    return sheet


def hood_image():
    """vu_hood: the hood's pixels of the finished dial (meter 0's base), alpha its antialiased mask (made a little firmer, so the needle's root does not show through the edge)."""
    base = base_frame().crop(HOOD_RECT); _, hood = dial_parts()
    wx, wy = WINDOWS[0][0], WINDOWS[0][1]
    mask = hood.resize((DIAL_W, DIAL_H), Image.BOX).crop((HOOD_RECT[0] - wx, HOOD_RECT[1] - wy, HOOD_RECT[2] - wx, HOOD_RECT[3] - wy))
    base.putalpha(mask.point(lambda v: min(255, v * 3 // 2))); return base


def lamp_image():
    """vu_lamp: the lit lamp and its glow, reduced with premultiplied alpha, LAMP_RECT of meter 0's window."""
    wx, wy = WINDOWS[0][0], WINDOWS[0][1]
    r = tuple(S(v) for v in (LAMP_RECT[0] - wx, LAMP_RECT[1] - wy, LAMP_RECT[2] - wx, LAMP_RECT[3] - wy))
    return lamp3().crop(r).convert('RGBa').resize((LAMP_RECT[2] - LAMP_RECT[0], LAMP_RECT[3] - LAMP_RECT[1]), Image.LANCZOS).convert('RGBA')


def images():
    """name -> PIL image of every installed VU picture (RGBA: the device's decoder gives 32 bit pixels for every picture the payload loads)."""
    return {'vu_base': base_frame(), 'vu_hood': hood_image(), 'vu_lamp': lamp_image(), 'vu_keys': keys_image()}


# ---- the needle: the reference renderer -------------------------------------------------------------------------------------------------------------
def _hw(t): return HW_ROOT + (HW_TIP - HW_ROOT) * (t - R0) / (R1 - R0)


def needle_rect(m, a):
    """The dirty rectangle (x0, y0, x1, y1 exclusive, page px) of meter m's needle at angle a: its corners' box grown by RECT_PAD, the shadow's offset on the right and
    bottom, clipped to the window."""
    px, py = PIVOTS[m]; ux, uy = math.sin(a), -math.cos(a); nx, ny = math.cos(a), math.sin(a)
    xs, ys = [], []
    for r, hw in ((R0, HW_ROOT), (R1, HW_TIP)):
        for s in (-1, 1): xs.append(px + r * ux + s * hw * nx); ys.append(py + r * uy + s * hw * ny)
    wx0, wy0, wx1, wy1 = WINDOWS[m]
    return (max(wx0, int(math.floor(min(xs))) - RECT_PAD), max(wy0, int(math.floor(min(ys))) - RECT_PAD),
            min(wx1, int(math.ceil(max(xs))) + RECT_PAD + SHADOW_DX), min(wy1, int(math.ceil(max(ys))) + RECT_PAD + SHADOW_DY))


def move_rect(m, a0, a1):
    """The dirty rectangle of the needle moving from a0 to a1: the union of the two."""
    r0, r1 = needle_rect(m, a0), needle_rect(m, a1)
    return (min(r0[0], r1[0]), min(r0[1], r1[1]), max(r0[2], r1[2]), max(r0[3], r1[3]))


def draw_needle(im, m, a, rect=None):
    """Meter m's needle and its shadow at angle a, over the 1x RGBA page `im`, inside `rect` (default needle_rect) and the window."""
    px, py = PIVOTS[m]; ux, uy = math.sin(a), -math.cos(a); nx, ny = math.cos(a), math.sin(a)
    x0, y0, x1, y1 = rect or needle_rect(m, a)
    s2 = SHADOW_SIGMA * math.sqrt(2)
    clamp = lambda v: 0.0 if v < 0 else (1.0 if v > 1 else v)
    pix = im.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            dx, dy = x + 0.5 - px, y + 0.5 - py
            c = pix[x, y]; r, g, b = c[0], c[1], c[2]
            sx, sy = dx - SHADOW_DX, dy - SHADOW_DY            # the shadow: the needle's shape moved, blurred (a gaussian across, an erf ramp at both ends)
            t, d = sx * ux + sy * uy, sx * nx + sy * ny
            if R0 - 4 * s2 < t < R1 + 4 * s2:
                hw = _hw(min(max(t, R0), R1))
                al = (0.25 * (math.erf((hw - d) / s2) + math.erf((hw + d) / s2)) * (math.erf((t - R0) / s2) + math.erf((R1 - t) / s2))) * SHADOW_ALPHA / 255
                if al > 0.002: r, g, b = r * (1 - al), g * (1 - al), b * (1 - al)
            t, d = dx * ux + dy * uy, dx * nx + dy * ny
            cov = clamp(_hw(t) + 0.5 - abs(d)) * clamp(t - R0 + 0.5) * clamp(R1 - t + 0.5) if R0 - 1 < t < R1 + 1 else 0
            if cov > 0: r, g, b = r + (NEEDLE_RGB[0] - r) * cov, g + (NEEDLE_RGB[1] - g) * cov, b + (NEEDLE_RGB[2] - b) * cov
            pix[x, y] = (int(r + 0.5), int(g + 0.5), int(b + 0.5), c[3])


def compose(f, imgs=None):
    """The page at the state f (1x RGBA, no text): the base; the pause glyph while playing; for each meter the lit lamp (f['peak']), the needle (f['vu'], None parked) and the hood."""
    imgs = imgs or images()
    im = imgs['vu_base'].copy()
    if f['playing']:
        x0 = KEY_COLS['play'][0]; im.paste(imgs['vu_keys'].crop((KEY_CELLS[('play', 1)], 0, KEY_CELLS[('play', 1)] + KEY_COLS['play'][1] - x0, BAND_Y[1] - BAND_Y[0])), (x0, BAND_Y[0]))
    for m in (0, 1):
        if f['peak'][m]: im.alpha_composite(imgs['vu_lamp'], LAMP_AT[m])
        draw_needle(im, m, angle(f['vu'][m] if f['playing'] else None))
        im.alpha_composite(imgs['vu_hood'], HOOD_AT[m])
    return im


def text(s, out, f):
    """The page's four lines as the AWTK labels draw them (an hscroll_label that does not scroll: cut with an ellipsis to its width). s: preview_icons.Side."""
    from tape_art import times_text
    t = TEXT['title']; face = s.title_face(f['title']); title = s.clip(f['title'], t['px'], t['w'], face)
    s.text(out, t['x'], t['y'], title, t['px'], t['rgb'], font=face)   # drawn once: the lyrics face (Inter Bold) for a Latin / Greek / Cyrillic title, else the default font (patch/lyrics.c ly_title_face)
    for name, value in (('artist', f['artist']), ('times', times_text(f['pos'], f['len'])), ('status', VA.status_text(f['vol'], f['fmt'], f['clock']))):
        t = TEXT[name]; s.text(out, t['x'], t['y'], s.clip(value, t['px'], t['w']), t['px'], t['rgb'])


def design(s, f):
    """The whole page at the state f (title, artist, pos, len, fmt, vol, clock, playing, vu, peak): what the page shows. s: preview_icons.Side."""
    out = compose(f); text(s, out, f); return out


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    import png_pack
    for n, im in images().items(): open(os.path.join(out, n + '.png'), 'wb').write(png_pack.pack(im)); print(n, im.size)
