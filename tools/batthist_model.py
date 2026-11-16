#!/usr/bin/env python3
"""The Battery History page's model (patch/bhpage.c, docs/modules/batthist.md "History page"): the three bitmaps' pixels (the Since Last Charge card, the two charts), the hour ticks and the texts of the page, in Python.

tools/preview/preview_batthist.py draws the page from it and test/pod/batthist.py checks the payload's bitmaps and labels against it. A bucket is the tuple of struct bh_bucket (level, flags, on, play, cov, d_on, d_play, d_idle),
oldest first, 96 of them (patch/batthist.h); `head` is the newest bucket's number (wall seconds / 900). Pixels are (alpha, red, green, blue).
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdefs

OFF = cdefs.defines(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'patch', 'offsets.inc'))
W, R, PX0 = OFF['BHC_W'], OFF['BHC_R'], OFF['BHC_PX0']
LH, LCARD, LPY0, LPH, LPITCH, LBAR = (OFF[k] for k in ('BHL_H', 'BHL_CARD', 'BHL_PY0', 'BHL_PH', 'BHL_PITCH', 'BHL_BAR'))
AH, ACARD, APY0, APH, APITCH, ABAR, ALEG = (OFF[k] for k in ('BHA_H', 'BHA_CARD', 'BHA_PY0', 'BHA_PH', 'BHA_PITCH', 'BHA_BAR', 'BHA_LEGEND_Y'))
SCARD, SPAD, SBAR_Y, SBAR_H, SROW0, SROW_H, SMARK_X, SMARK, SMARK_R = (OFF[k] for k in ('BHS_CARD', 'BHS_PAD', 'BHS_BAR_Y', 'BHS_BAR_H', 'BHS_ROW0_Y', 'BHS_ROW_H', 'BHS_MARK_X', 'BHS_MARK_SIZE', 'BHS_MARK_R'))
SBAR_W = W - 2 * SPAD
BUCKETS, SECS, NONE, F_CHG, F_GAP = 96, 900, 255, 1, 2
CARD, CARD_BLUE, GRID, TICK = 28, 30, 48, 62          # the surface #1C1C1E (blue 2 above its grey), the dotted gridlines, the hour ticks
LEVEL = 216                                           # level bars
ON_RGB, PLAY_RGB, STBY_RGB = (0xE6,) * 3, (0x78, 0x78, 0x7C), (0x3A, 0x3A, 0x3C)   # screen on, playing with the screen off, standby: the bar, the legend marks, the rows' marks
BAND = (0x2A, 0x2A, 0x2C)                             # on external power: a faint band behind the bars (the card a step lighter)
HAIR = 51                                             # the summary's hairlines (#333333)
GREEN, RED = (0x34, 0xC7, 0x59), (0xFF, 0x14, 0x48)   # charging, 20 % or less on battery
LOW = 20
SW_X = (14, 124)                                      # the legend's marks (x in the card; SMARK px squares of radius SMARK_R centred on ALEG)


def valid(b): return not b[1] & F_GAP


def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v


def blank(h, ch):
    """The card (its rounded corners in the alpha) in the top ch rows of an h row bitmap (LCARD / ACARD); the rest is transparent."""
    out = []
    for y in range(h):
        row = []
        for x in range(W):
            if y >= ch:
                row.append((0, 0, 0, 0)); continue
            a = 1.0
            if (x < R or x >= W - R) and (y < R or y >= ch - R):
                dx = x + 0.5 - (R if x < R else W - R)
                dy = y + 0.5 - (R if y < R else ch - R)
                a = clamp(R - math.sqrt(dx * dx + dy * dy) + 0.5, 0, 1)
            row.append((int(a * 255 + 0.5), CARD, CARD, CARD_BLUE))
        out.append(row)
    return out


def rect(im, x, y, w, h, rgb):
    for yy in range(y, y + h):
        for xx in range(x, x + w): im[yy][xx] = (255, *rgb)


def cover(px, py, x0, y0, w, h, r):
    """The coverage (0..1) of the pixel (px, py) by the rounded rectangle x0, y0, w, h of radius r (the circle's edge is antialiased over one pixel)."""
    cx = clamp(px + 0.5, x0 + r, x0 + w - r)
    cy = clamp(py + 0.5, y0 + r, y0 + h - r)
    dx, dy = px + 0.5 - cx, py + 0.5 - cy
    return clamp(r - math.sqrt(dx * dx + dy * dy) + 0.5, 0, 1)


def blend(im, x, y, rgb, a):
    """The colour rgb over the opaque pixel at (x, y) with coverage a."""
    if a <= 0: return
    old = im[y][x]
    im[y][x] = (255, *(int(c * a + o * (1 - a) + 0.5) for c, o in zip(rgb, old[1:])))


def rrect(im, x0, y0, w, h, r, rgb):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w): blend(im, x, y, rgb, cover(x, y, x0, y0, w, h, r))


def mark(im, x, cy, rgb): rrect(im, x, cy - SMARK // 2, SMARK, SMARK, SMARK_R, rgb)


def band(im, b, py0, ph):
    """The faint band behind the bars: each bucket on external power (BH_F_CHG, with data) is its 2.5 px wide slice of the plot (bucket i from PX0 + 5 i // 2 to PX0 + 5 (i + 1) // 2), the plot's height."""
    for i, k in enumerate(b):
        if valid(k) and k[1] & F_CHG: rect(im, tick_x(i), py0, tick_x(i + 1) - tick_x(i), ph, BAND)


def grid(im, py0, ph):
    for y in (py0, py0 + ph // 2, py0 + ph):
        for x in range(PX0, PX0 + 240):
            if (x - PX0) % 4 < 2: im[y][x] = (255, GRID, GRID, GRID)


def offset(head, tz):
    """Seconds the local clock is ahead of UTC, as the payload reads it (modulo a day): tz is the zone's offset at the open bucket."""
    return tz % 86400


def ticks(head, tz):
    """[(boundary i, local hour)] the bucket boundaries 0 .. 95 that fall on a local multiple of six hours (always four of them): boundary i is the start of bucket i of the view."""
    out = []
    for i in range(BUCKETS):
        tod = ((head - (BUCKETS - 1) + i) * SECS + offset(head, tz)) % 86400
        if tod % 21600 == 0: out.append((i, tod // 3600))
    return out


def tick_x(i): return PX0 + 5 * i // 2


def level_bars(b):
    """48 entries, the half-hour bars: None (no data), or (level, charging): the later bucket's level, else the earlier's; charging when either bucket saw the charger."""
    out = []
    for j in range(48):
        pair = [k for k in (b[2 * j], b[2 * j + 1]) if valid(k)]
        lev = [k[0] for k in pair if k[0] <= 100]
        out.append((lev[-1], any(k[1] & F_CHG for k in pair)) if lev else None)
    return out


def level_color(level, chg): return GREEN if chg else RED if level <= LOW else (LEVEL,) * 3


def render_level(b, head, tz):
    im = blank(LH, LCARD)
    grid(im, LPY0, LPH)
    for i, _ in ticks(head, tz):
        for y in range(LPY0 + LPH + 3, LPY0 + LPH + 6): im[y][tick_x(i)] = (255, TICK, TICK, TICK)
    for j, bar in enumerate(level_bars(b)):
        if not bar: continue
        h = (bar[0] * LPH + 50) // 100
        rect(im, PX0 + LPITCH * j, LPY0 + LPH - h, LBAR, h, level_color(*bar))
    return im


def activity_bars(b):
    """24 entries (seconds screen on, seconds playing with the screen off) per hour of four buckets, charging included."""
    return [(sum(k[2] * 8 for k in b[4 * m:4 * m + 4] if valid(k)), sum(k[3] * 8 for k in b[4 * m:4 * m + 4] if valid(k))) for m in range(24)]


def render_activity(b, head, tz):
    im = blank(AH, ACARD)
    band(im, b, APY0, APH)
    grid(im, APY0, APH)
    for i, _ in ticks(head, tz):
        for y in range(APY0 + APH + 3, APY0 + APH + 6): im[y][tick_x(i)] = (255, TICK, TICK, TICK)
    for m, (on, play) in enumerate(activity_bars(b)):
        hon = (on * APH + 1800) // 3600
        hpl = (play * APH + 1800) // 3600
        hpl = min(hpl, APH - hon)
        x = PX0 + APITCH * m
        rect(im, x, APY0 + APH - hon, ABAR, hon, ON_RGB)
        rect(im, x, APY0 + APH - hon - hpl, ABAR, hpl, PLAY_RGB)
    mark(im, SW_X[0], ALEG, ON_RGB)
    mark(im, SW_X[1], ALEG, PLAY_RGB)
    return im


def bar_edges(on, play, total):
    """The stacked bar's two inner edges in pixels from its left: screen on up to the first, playing with the screen off up to the second, standby after it (all of it standby, as the track, with no time). The seconds are halved
    until the total is under 2**20 (the payload's integer arithmetic)."""
    on = min(on, total)
    play = min(play, total - on)
    while total > 0xFFFFF: total, on, play = total >> 1, on >> 1, play >> 1
    if not total: return 0, 0
    return (SBAR_W * on + total // 2) // total, (SBAR_W * (on + play) + total // 2) // total


def render_summary(on, play, total):
    """The Since Last Charge card's bitmap (BHC_W x SCARD): the card, the stacked bar (rounded ends) of screen on / playing with the screen off / standby, the marks of the three rows and the hairlines between them. on and play are seconds,
    total all the seconds on battery (standby is the rest)."""
    im = blank(SCARD, SCARD)
    e1, e2 = bar_edges(on, play, total)
    for y in range(SBAR_Y, SBAR_Y + SBAR_H):
        for x in range(SPAD, SPAD + SBAR_W):
            a = cover(x, y, SPAD, SBAR_Y, SBAR_W, SBAR_H, SBAR_H // 2)
            blend(im, x, y, ON_RGB if x - SPAD < e1 else PLAY_RGB if x - SPAD < e2 else STBY_RGB, a)
    for k, rgb in enumerate((ON_RGB, PLAY_RGB, STBY_RGB)):
        cy = SROW0 + SROW_H * k + SROW_H // 2
        mark(im, SMARK_X, cy, rgb)
        if k: rect(im, SPAD, SROW0 + SROW_H * k, SBAR_W, 1, (HAIR,) * 3)
    return im


def hour_text(hour, h24, chart):
    """A tick's label: the level chart's "18:00" / "6 PM", the activity chart's "18" / "6 PM"."""
    if h24: return f'{hour:02d}:00' if chart == 'level' else f'{hour:02d}'
    return f'{hour % 12 or 12} {"AM" if hour < 12 else "PM"}'


def clock_text(hour, minute, h24):
    """A local time of day: 24-Hour Time or 12-hour (patch/datetime.c dt_text)."""
    return f'{hour:02d}:{minute:02d}' if h24 else f'{hour % 12 or 12}:{minute:02d} {"AM" if hour < 12 else "PM"}'


def dur_text(secs, tr=None):
    """"4 h 18 min", "2 h", "45 min": rounded to the minute (the tables' %dh %dm, %dh, %dm)."""
    t = tr or {}
    m = (secs + 30) // 60
    if m >= 60 and m % 60: return t.get('%dh %dm', '%d h %d min') % (m // 60, m % 60)
    if m >= 60: return t.get('%dh', '%d h') % (m // 60)
    return t.get('%dm', '%d min') % m


def caption_text(unplug_clock, level):
    """The Since Last Charge caption: "Unplugged at 21:25, 100%", without the level when the gauge then is unknown (BH_NONE)."""
    return f'Unplugged at {unplug_clock}, {level}%' if level <= 100 else f'Unplugged at {unplug_clock}'


def stat_text(d): return f'~{d}%'


def state(b):
    """'data' when a closed bucket (not the open one) has data, else 'empty'."""
    return 'data' if any(valid(k) for k in b[:BUCKETS - 1]) else 'empty'


def axis_activity_texts(): return ('60 min', '30 min', '0')
