#!/usr/bin/env python3
"""One battery design for the status bar and the lock screen (docs/modules/battery.md).

The app swaps one image between three states and feeds a progress bar the level, drawn UNDER the
image (stock child order). The battery reads as one solid grey body with the level in white (iOS-like):
the progress bar draws the level in white over the body's interior (`fill`, inset 1 px; the grey under it
is a view of its own, tools/statusbar.py battery_parts), and the image is only the 1 px rim that rounds the
body's corners, and the nub:

  normal    EMPTY grey rim and nub
  charging  green #34C759 rim and nub + a green bolt right of the nub (the body's middle is the percentage's)
  low       red #FF3B30 rim and nub + a red sliver at the level's left end (the app's low icon, capacity 0)

The image has no pixel outside the body, the nub and the bolt, so it sits on any background (the lock screen's wallpaper).

  STATUS  36 x 14 canvas, body 26 x 14 (radius 4), nub 1.6 x 5, the bolt in the last `tail` 8 px (6 x 10),
          fill (pgbar_battery) 24 x 12 at (1, 1)   bar_power/charge/lowpower
          the lock screen's screens_battery/charge/lowbattery are the same three pictures (tools/mod_lockscreen.py)

Output is a plain zlib RGBA PNG (the bytes do not depend on an image library's version; supersampling is integer box
reduction). Used by mod_battery.py and mod_lockscreen.py.
"""
import struct, zlib

EMPTY = '#5A5A5A'                  # the body under the level (tools/status_art.py DIM)
EMPTY_PCT = '#8E8E93'              # the same while the percentage shows in it: light enough for the black digits
WHITE, GREY, CHARGE, LOW = (255, 255, 255), (0x5A, 0x5A, 0x5A), (0x34, 0xC7, 0x59), (0xFF, 0x3B, 0x30)
SS = 8
SLIVER = 3                         # the low picture's red level, px

class Spec:
    def __init__(self, canvas, body, nub, radius, fill, bolt, tail):
        self.canvas, self.body, self.nub, self.radius, self.fill, self.bolt, self.tail = canvas, body, nub, radius, fill, bolt, tail

STATUS = Spec((36, 14), (0, 0, 26, 14), (26.4, 4.5, 1.6, 5), 4, (1, 1, 24, 12), (30, 2, 6, 10), 8)   # tail: the px right of the nub's end (the bolt's)
STATES = {'normal': (GREY, False), 'charge': (CHARGE, True), 'low': (LOW, False)}

BOLT = ((0.62, 0.0), (0.0, 0.58), (0.42, 0.58), (0.30, 1.0), (1.0, 0.38), (0.55, 0.38))   # unit box, y down

def mask(spec, bolt):
    """-> (rim + nub, bolt or None) as L masks at 1x."""
    from PIL import Image, ImageDraw
    w, h = spec.canvas; s = SS
    S = lambda *v: [round(x * s) for x in v]
    m = Image.new('L', (w * s, h * s), 0); d = ImageDraw.Draw(m)
    bx, by, bw, bh = spec.body
    d.rounded_rectangle(S(bx, by, bx + bw - 1 / s, by + bh - 1 / s), radius=spec.radius * s, fill=255)
    fx, fy, fw, fh = spec.fill
    d.rounded_rectangle(S(fx, fy, fx + fw - 1 / s, fy + fh - 1 / s), radius=(spec.radius - 1) * s, fill=0)   # the progress bar shows
    # through; the rim covers the bar's square corners, so the level's ends are rounded too
    nx, ny, nw, nh = spec.nub
    d.rounded_rectangle(S(nx, ny, nx + nw - 1 / s, ny + nh - 1 / s), radius=nw / 2 * s, fill=255)
    d.rectangle(S(nx, ny, nx + nw / 2, ny + nh - 1 / s), fill=255)         # square on the body's side
    if bolt:
        ox, oy, ow, oh = spec.bolt
        core = Image.new('L', m.size, 0); ImageDraw.Draw(core).polygon([tuple(S(ox + u * ow, oy + v * oh)) for u, v in BOLT], fill=255)
        return m.reduce(s), core.reduce(s)
    return m.reduce(s), None

def render(spec, state):
    from PIL import Image
    rgb, bolt = STATES[state]
    rim, bolt_m = mask(spec, bolt)
    w, h = spec.canvas
    im = Image.new('RGBA', (w, h), rgb + (0,)); im.putalpha(rim)
    if state == 'low':
        fx, fy, fw, fh = spec.fill
        from PIL import ImageDraw
        m = Image.new('L', (w * SS, h * SS), 0)          # the fill's rounded shape, its left SLIVER px
        ImageDraw.Draw(m).rounded_rectangle((fx * SS, fy * SS, (fx + fw) * SS - 1, (fy + fh) * SS - 1), radius=(spec.radius - 1) * SS, fill=255)
        ImageDraw.Draw(m).rectangle(((fx + SLIVER) * SS, 0, w * SS, h * SS), fill=0)
        s = Image.new('RGBA', (w, h), rgb + (255,)); s.putalpha(m.reduce(SS)); im.alpha_composite(s)
    if bolt:
        g = Image.new('RGBA', (w, h), rgb + (255,)); g.putalpha(bolt_m); im.alpha_composite(g)
    return im

def png(spec, state):
    im = render(spec, state); w, h = im.size
    raw = b''.join(b'\0' + im.crop((0, y, w, y + 1)).tobytes() for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
