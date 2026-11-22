#!/usr/bin/env python3
"""Pod screens at 1:1 device pixels, with sample data and the built wheel asset.

Frames: root, Music, Albums and Now Playing. Text uses the tree's font and the shared
StbFont metrics (preview_icons.Side); colours and geometry follow patch/ipod.c.

  preview_ipod.py WORKDIR [OUT.png]     (unpacked release work tree; venv python; default out/preview/ipod-mock.png)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, cdefs, preview_icons as PI, pod_ui

W, BAR, H = 320, 30, 480
MENU = ['Music', 'Cover Flow', 'Shuffle Songs', 'Now Playing', 'Settings']
MUSIC = ['Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle Songs']
ALBUMS = [('Kind of Blue', (70, 110, 190)), ('Blue in Green', (50, 90, 170)), ('Homogenic', (190, 90, 120)), ('Dummy', (150, 120, 70)),
          ('Kid A', (60, 140, 150)), ('Mezzanine', (110, 90, 130)), ('OK Computer', (110, 130, 150)), ('Pet Sounds', (200, 170, 110))]

class Theme:
    def __init__(self, dark):
        self.dark = dark
        source = open(os.path.join(build.ROOT, 'patch', 'ipod_theme.c')).read().replace('\\\n', ' ')
        macros = dict(re.findall(r'#define (\w+) ([^\n]*)', source))
        literals = source.split('palettes[2] = {', 1)[1].split('};', 1)[0]
        for name, body in macros.items(): literals = literals.replace(name, body)
        words = [int(v, 16) for v in re.findall(r'0x([0-9a-f]+)u', literals)]
        assert len(words) == 34
        colors = [tuple((v >> k) & 255 for k in (0, 8, 16)) for v in words[17 * int(dark):17 * (int(dark) + 1)]]
        self.bg, self.fg, self.sub, self.np, self.body, self.pane, self.line = colors[:7]
        self.header, self.header_rule = colors[7:11], colors[11]
        self.battery_edge, self.battery_empty, self.mode = colors[12], colors[13:16], colors[16]
        self.ring = ((0x25, 0x25, 0x26), (0x1D, 0x1D, 0x1E)) if dark else ((0xF6,) * 3, (0xEE,) * 3)
        self.hub = ((0x36, 0x36, 0x38), (0x2A, 0x2A, 0x2C)) if dark else ((0xEE,) * 3, (0xCF,) * 3)
        self.label = (0xFF,) * 3 if dark else (0x9F, 0xA9, 0xB3)

def vgrad(im, box, top, bot):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = box
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line((x0, y, x1 - 1, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))

def stops(im, box, points):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = box
    for y in range(y0, y1):
        p = (y - y0) * 100 // max(1, y1 - y0 - 1)
        i = next((i for i in range(1, len(points)) if p <= points[i][0]), len(points) - 1)
        a, b = points[i - 1], points[i]; n = max(1, b[0] - a[0]); k = p - a[0]
        rgb = tuple(v + int((w - v) * k / n) for v, w in zip(a[1], b[1]))
        d.line((x0, y, x1 - 1, y), fill=rgb + (255,))

def chevron(im, x, ymid, rgb, h=4):
    d = ImageDraw.Draw(im); d.line((x, ymid - h, x + h, ymid, x, ymid + h), fill=rgb + (255,), width=2)

def save_true(im, path):
    """True colour: a 256 colour median cut turned the battery's greens brown, so the Pod previews are not quantized."""
    im.convert('RGB').save(path, optimize=True)

def hexrgb(h): return ((h >> 16) & 255, (h >> 8) & 255, h & 255)
GREEN = [hexrgb(h) for h in (0xA4D08A, 0xDCF8C7, 0xC9ECB0, 0xA5E07F, 0xA1DE7D, 0x6BAB46, 0x4E932C, 0x539831, 0x5FA53E, 0x539831)]
RED = [hexrgb(h) for h in (0xD17F6B, 0xF0B2A8, 0xE89D90, 0xE87259, 0xE67357, 0xB74124, 0xA3300B, 0xA7340F, 0xB3421C, 0xA73410)]

def battery(im, x, y, th, fill=0.8, red=False):
    """The reference's 24 x 12 battery and 3 x 5 nub: a three-stop empty well, a ten-row fill in two bands inside the 1 px outline."""
    d = ImageDraw.Draw(im)
    stops(im, (x + 1, y + 1, x + 23, y + 11), [(0, th.battery_empty[0]), (50, th.battery_empty[1]), (100, th.battery_empty[2])])
    w = int(22 * fill)
    for i, c in enumerate(RED if red else GREEN):
        if w > 0: d.line((x + 1, y + 1 + i, x + w, y + 1 + i), fill=c + (255,))
    d.rectangle((x, y, x + 23, y + 11), outline=th.battery_edge + (255,)); d.rectangle((x + 24, y + 3, x + 26, y + 7), fill=th.battery_edge + (255,))

def play_glyph(im, x, y, pause=False):
    """The 12 x 14 play (a triangle) or pause glyph in the selection's blue, a row at a time down its gradient."""
    d = ImageDraw.Draw(im)
    for r in range(14):
        c = tuple(int(a + (b - a) * r / 14) for a, b in zip((0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2))) + (255,)
        if pause: d.line((x + 1, y + r, x + 4, y + r), fill=c); d.line((x + 7, y + r, x + 10, y + r), fill=c)
        else: d.line((x + 1, y + r, x + (min(r, 13 - r) + 1) * 10 // 7, y + r), fill=c)

def title_bar(s, im, th, title, h=pod_ui.OFFSETS['IP_BAR_H'], right=None, clock=False, width=W, state='playing', pct=0.8):
    stops(im, (0, 0, width, h - 1), list(zip((0, 42, 47, 100), th.header)))
    ImageDraw.Draw(im).line((0, h - 1, width - 1, h - 1), fill=th.header_rule + (255,))
    s.text(im, pod_ui.OFFSETS['IP_TEXT_X'], h / 2, s.clip(title, 16, width - 8 - 27 - 8 - 12 - 6 - 8), 16, th.fg)
    if state: play_glyph(im, width - 8 - 27 - 8 - 12, h // 2 - 7, state == 'paused')
    battery(im, width - 8 - 27, h // 2 - 6, th, pct, pct <= 0.2)

def selection(im, y, h, th, x1=W):
    stops(im, (0, y, x1, y + h), [(0, (62,171,227)), (25, (55,160,224)), (50, (44,151,220)), (75, (33,140,214)), (100, (21,132,211))])
    d = ImageDraw.Draw(im); d.line((0, y, x1 - 1, y), fill=(154, 221, 248, 255)); d.line((0, y + h - 1, x1 - 1, y + h - 1), fill=(21, 79, 129, 255))

def row_y(i, visible=None):
    """Row i's top: the visible rows share the 220 px under the title bar exactly (patch/ipod.c ip_row_y)."""
    o = pod_ui.OFFSETS; visible = visible or o['IP_ROWS']
    return o['IP_BAR_H'] + i * (o['IP_SCREEN_H'] - o['IP_BAR_H']) // visible

def rows(s, im, th, items, sel, x1=W, px=16, chev=True, tag=None, x=8):
    for i, t in enumerate(items):
        y = row_y(i); rh = row_y(i + 1) - y
        fg = th.fg
        if i == sel: selection(im, y, rh, th, x1); fg = (255, 255, 255)
        s.text(im, x, y + rh / 2, s.clip(t, px, x1 - x - 22), px, fg)
        if chev and i == sel: chevron(im, x1 - 14, y + rh // 2, fg)

def cover(rgb, size, r=0):
    c = PI.sample_cover(rgb, size)
    return c

def reflect(im, c, x, y, fade=0.35, hmax=None):
    f = c.transpose(Image.FLIP_TOP_BOTTOM); h = hmax or f.height // 3
    f = f.crop((0, 0, f.width, h)); a = Image.new('L', f.size)
    for yy in range(h): ImageDraw.Draw(a).line((0, yy, f.width, yy), fill=int(255 * fade * (1 - yy / h)))
    f.putalpha(a); im.alpha_composite(f, (x, y))

SHADOW = [int(v) for v in re.search(r'ip_shadow_alpha\[IP_SHADOW_W\] = \{([^}]*)\}', open(os.path.join(build.ROOT, 'patch', 'ipod.c')).read())[1].split(',')]

def shadow_layer():
    """The menu's shadow on the pane's left edge (IP_SHADOW_W columns of black, the alpha table of patch/ipod.c), straight alpha."""
    layer = Image.new('RGBA', (len(SHADOW), 240), (0, 0, 0, 0))
    for x, a in enumerate(SHADOW):
        for y in range(240): layer.putpixel((x, y), (0, 0, 0, a))
    return layer

def screen_main(s, th, sh, clock=True, shadow=True, rgb=(70, 110, 190)):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Pod', width=160)
    rows(s, im, th, MENU, 0, x1=160)
    art = cover(rgb, 264)
    im.alpha_composite(art.crop((52, 12, 212, 252)), (160, 0))   # the pane is flush against the menu: no rule, but the menu's shadow
    if shadow: im.alpha_composite(shadow_layer(), (160, 0))
    return im

def screen_albums(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Albums', clock=True)
    rich_rows(s, im, th, [(a, artist) for (a, _), artist in zip(ALBUMS[:4], ('Miles Davis', 'Miles Davis', 'Björk', 'Portishead'))], 2, True)
    return im

def placeholder(size):
    return Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', 'ipod_placeholder.png')).convert('RGBA').resize((size, size), Image.BOX)

def rich_rows(s, im, th, items, sel, chev=False, covers=None):
    """Cover rows: the IP_TALL_H cover fills its row exactly (flush top and left; four rows share the screen under the title bar), 18 px title over a 16 px subtitle
    8 px right of it. A cover of None is the placeholder."""
    tall = pod_ui.OFFSETS['IP_TALL_H']
    for i, (title, sub) in enumerate(items):
        y = pod_ui.OFFSETS['IP_BAR_H'] + i * tall
        selected = i == sel
        if selected: selection(im, y, tall, th)
        fg = (255, 255, 255) if selected else th.fg
        rgb = (covers or [a[1] for a in ALBUMS])[i]
        im.alpha_composite(placeholder(tall) if rgb is None else cover(rgb, tall), (0, y))
        s.text(im, tall + 8, y + 19, s.clip(title, 18, 236), 18, fg)   # the regular face, as every list row
        if not selected and y + tall < pod_ui.OFFSETS['IP_SCREEN_H']:   # the hairline under the row, from the text to the edge
            ImageDraw.Draw(im).line((tall, y + tall - 1, W - 1, y + tall - 1), fill=th.line + (255,))
        s.text(im, tall + 8, y + 40, s.clip(sub, 16, 236), 16, fg if selected else th.sub)
        if selected and chev: chevron(im, 306, y + tall // 2, fg)

def playing_mark(th):
    """The playing track's speaker as ip_mode_bitmap makes it: the built 28 px white volume-2 glyph reduced to 14 px with a box filter over black (the coverage), mixed from white to the
    title bar glyph's blue, a row at a time down its gradient."""
    g = Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', 'ipod_playing.png')).convert('RGBA')
    cov = Image.alpha_composite(Image.new('RGBA', g.size, (0, 0, 0, 255)), g).convert('L').resize((14, 14), Image.BOX)
    out = Image.new('RGBA', (14, 14), th.bg + (255,))
    for r in range(14):
        ink = tuple(int(a + (b - a) * r / 14) for a, b in zip((0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2)))
        out.paste(Image.new('RGBA', (14, 1), ink + (255,)), (0, r), cov.crop((0, r, 14, r + 1)))
    return out

def plain_rows(s, im, th, items, sel, title):
    """A song list: 30 px text rows, seven visible, no cover."""
    title_bar(s, im, th, title)
    for i, t in enumerate(items[:7]):
        y = row_y(i); rh = row_y(i + 1) - y
        if i == sel: selection(im, y, rh, th)
        s.text(im, 8, y + rh / 2, s.clip(t, 18, 290), 18, (255, 255, 255) if i == sel else th.fg)
        if i == 2 and sel != 2: im.alpha_composite(playing_mark(th), (320 - 8 - 14, y + (rh - 14) // 2))   # the playing track's speaker

def song_rows(s, im, th, items, sel, title):
    """Music > Songs: IP_SONG_ROWS two-line rows (ip_row_y), the title (regular) over the artist IP_SONG_SUB_Y down, a hairline under each."""
    o = pod_ui.OFFSETS; title_bar(s, im, th, title); n = o['IP_SONG_ROWS']
    for i, (t, sub) in enumerate(items[:n]):
        y = row_y(i, n); rh = row_y(i + 1, n) - y
        fg = (255, 255, 255) if i == sel else th.fg
        if i == sel: selection(im, y, rh, th)
        elif y + rh < o['IP_SCREEN_H']: ImageDraw.Draw(im).line((0, y + rh - 1, W - 1, y + rh - 1), fill=th.line + (255,))
        s.text(im, 6, y + 17, s.clip(t, 18, 286), 18, fg)
        s.text(im, 6, y + o['IP_SONG_SUB_Y'] + 10, s.clip(sub, 16, 286), 16, fg if i == sel else th.sub)
        if i == 2 and sel != 2: im.alpha_composite(playing_mark(th), (320 - 6 - 14, y + (rh - 14) // 2))

def screen_songs(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,))
    song_rows(s, im, th, [('So What', 'Miles Davis'), ('Teardrop', 'Massive Attack'), ('25コ目の染色体', 'RADWIMPS'), ('Everything in Its Right Place', 'Radiohead'),
                          ('Paranoid Android', 'Radiohead')], 1, 'Songs')
    return im

def screen_artist(s, th, sh):
    """An artist's albums: the stock All Songs record first with the placeholder cover."""
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Miles Davis')
    rich_rows(s, im, th, [('All Songs', ''), ('Kind of Blue', 'Miles Davis'), ('Sketches of Spain', 'Miles Davis'), ('Bitches Brew', 'Miles Davis')], 0, True,
              [None, (70, 110, 190), (190, 150, 70), (80, 130, 90)])
    return im

def screen_album_songs(s, th, sh):
    """A one-album artist: its songs directly, titled with the album."""
    im = Image.new('RGBA', (W, sh), th.bg + (255,))
    plain_rows(s, im, th, ['Hunter', 'Joga', 'Unravel', 'Bachelorette', 'All Neon Like', '5 Years', 'Immature'], 0, 'Homogenic')
    return im

def screen_music(s, th, sh):
    im = screen_main(s, th, sh); ImageDraw.Draw(im).rectangle((0, 0, 159, sh - 1), fill=th.bg + (255,))
    title_bar(s, im, th, 'Music', width=160)
    rows(s, im, th, MUSIC, 1, x1=160)
    return im

def screen_settings(s, th, sh):
    im = screen_main(s, th, sh)
    ImageDraw.Draw(im).rectangle((0, 0, 159, sh - 1), fill=th.bg + (255,))
    title_bar(s, im, th, 'Settings', width=160)
    for i, (label, value) in enumerate((('Shuffle', 'Off'), ('Repeat', 'Off'), ('Appearance', 'Dark' if th.dark else 'Light'))):
        y = row_y(i); rh = row_y(i + 1) - y; selected = i == 2; fg = (255,)*3 if selected else th.fg
        if selected: selection(im, y, rh, th, 160)
        vw = min(72, s.font.width(value, 16))
        s.text(im, 8, y + rh / 2, s.clip(label, 18, 160 - 8 - 8 - vw - 12), 18, fg)
        s.text(im, 152, y + rh / 2, value, 16, fg if selected else (0x0C, 0x62, 0xD2), 'r')
    return im

def mode_mark(th, name):
    """The play mode mark as ip_mode_bitmap makes it: the built 32 px white glyph (name: shuffle, repeat, repeat1) reduced to 16 px with a box filter over black, whose value is the
    coverage, then mixed from the screen's colour to the mark's."""
    g = Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', f'ipod_mode_{name}.png')).convert('RGBA')
    cov = Image.alpha_composite(Image.new('RGBA', g.size, (0, 0, 0, 255)), g).convert('L').resize((16, 16), Image.BOX)
    out = Image.new('RGBA', (16, 16), th.bg + (255,)); out.paste(Image.new('RGBA', (16, 16), th.mode + (255,)), (0, 0), cov)
    return out

def tilt(art, bg, o):
    """ip_tilt: the square cover turned (near edge IP_NP_ART_W tall, far edge IP_NP_ART_HR, perspective columns), its reflection under it, on the screen colour."""
    A, W, HR, R = o['IP_ART'], o['IP_NP_ART_W'], o['IP_NP_ART_HR'], o['IP_NP_REFLECT']
    src = art.load(); out = Image.new('RGBA', (W, W + R)); d_ = out.load()
    clamp = lambda v: max(0, min(v, (A - 1) << 8))
    def px(sx, sy):
        sx, sy = clamp(sx), clamp(sy); x0, y0, fx, fy = sx >> 8, sy >> 8, sx & 255, sy & 255
        x1, y1 = x0 + (x0 < A - 1), y0 + (y0 < A - 1)
        return tuple((((a * (256 - fx) + b * fx) * (256 - fy) + (c * (256 - fx) + e * fx) * fy) >> 16) for a, b, c, e in zip(src[x0, y0], src[x1, y0], src[x0, y1], src[x1, y1]))
    mix = lambda q, p_, f: tuple(b + ((c - b) * f >> 8) for b, c in zip(q, p_))
    hl, hr = W << 8, HR << 8
    for x in range(W):
        t = ((2 * x + 1) << 11) // W
        u = (t * HR << 12) // (W * 4096 - (W - HR) * t)
        h = hl - (((hl - hr) * t) >> 12); top = (hl - h) // 2; bot = top + h; rl = R * h // W
        sx = (u * A >> 4) - 128
        for y in range(W + R):
            py = (y << 8) + 128; cov = max(0, min((y + 1) << 8, bot) - max(y << 8, top)); d = max(py - bot, 0); c = tuple(bg)
            if cov < 256 and (y + 1) << 8 > bot and d < rl: c = mix(bg, px(sx, (h - d) * A * 256 // h - 128), 77 * (rl - d) // rl)
            if cov > 0: c = mix(c, px(sx, (py - top) * A * 256 // h - 128), cov)
            d_[x, y] = c + (255,)
    return out

def screen_now(s, th, sh, shuffle=False, cjk=False, mode='time'):
    """mode: 'time' the progress bar, 'volume' the volume bar (ip.vol_until), 'scrub' the scrubber's knob (ip.scrub)."""
    o = pod_ui.OFFSETS
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Now Playing')
    side = o["IP_ART"]
    # A synthetic textured sleeve, turned and reflected as ip_tilt makes the picture (same integer steps).
    art = Image.new('RGB', (side, side)); p = art.load()
    for y in range(side):
        for x in range(side): p[x, y] = (30 + x * 170 // side, 40 + y * 150 // side, 110 + (x + y) * 80 // (2 * side))
    ImageDraw.Draw(art).rectangle((16, 18, 134, 48), fill=(228, 220, 183))
    ImageDraw.Draw(art).ellipse((26, 60, 124, 140), fill=(30, 46, 69))
    im.alpha_composite(tilt(art, th.bg, o), (o['IP_NP_ART_X'], o['IP_NP_ART_Y']))
    if shuffle: im.alpha_composite(mode_mark(th, shuffle if isinstance(shuffle, str) else 'shuffle'), (o['IP_MODE_X'], o['IP_MODE_Y']))
    tx = o['IP_NP_TEXT_X']; title, artist, album = ('麦芽糖', '周杰伦', '11月的萧邦') if cjk else ('Yellow', 'Coldplay', 'Parachutes')
    tf = s.title_face(title); s.text(im, tx, o['IP_NP_TITLE_Y'] + 12, s.clip(title, 18, W - tx - 8, tf), 18, th.fg, font=tf)   # ly_title_face: bold when the face has it all
    s.text(im, tx, o['IP_NP_ARTIST_Y'] + 11, s.clip(artist, 16, W - tx - 8), 16, th.np)
    s.text(im, tx, o['IP_NP_ALBUM_Y'] + 11, s.clip(album, 16, W - tx - 8), 16, th.np)
    s.text(im, tx, o['IP_NP_PLACE_Y'] + 10, '1 / 12', 14, th.np)
    py, bh, tx0, tw, gap = o['IP_NP_BAR_Y'], o['IP_NP_BAR_H'], o['IP_NP_TRACK_X'], o['IP_NP_TRACK_W'], o['IP_NP_TIME_GAP']
    knob = int(tw * 0.34); fw = int(tw * 0.62) if mode == 'volume' else 0 if mode == 'scrub' else knob   # the scrubber's track is empty (ip_np_strip kind 1)
    for i in range(bh):   # ip_bar_row
        bar_row(im, py + i, i, tx0, tw, fw, 255, th.bg)
    for i in range(o['IP_NP_BAR_REFLECT'] - 1):   # one clear row, then the mirror from 22 %
        bar_row(im, py + bh + 1 + i, bh - 1 - i, tx0, tw, fw, (o['IP_NP_BAR_REFLECT'] - 1 - i) * 56 // (o['IP_NP_BAR_REFLECT'] - 1), th.bg)
    if mode == 'shuffle':   # ip_shuf_strip: the shuffle slider in the bar's place (the bar drawn above is painted over here)
        ImageDraw.Draw(im).rectangle((0, py - 6, W - 1, py + bh + o['IP_NP_BAR_REFLECT'] + 2), fill=th.bg + (255,))
        shuffle_strip(s, im, th, o, 1)
        return im
    if mode == 'volume':   # ip_speaker: quiet before the bar, loud after it, no times
        speaker(im, tx0 - gap - o['IP_SPK_W'], py + bh // 2, 0, th.fg, o); speaker(im, tx0 + tw + gap, py + bh // 2, 2, th.fg, o)
        return im
    if mode == 'scrub': diamond(im, tx0 + knob, py + bh // 2, o['IP_NP_KNOB'], th.bg, o['IP_NP_BAR_REFLECT'])
    s.text(im, tx0 - gap, py - 1 + 11, '1:47', 16, th.fg, 'r'); s.text(im, tx0 + tw + gap, py - 1 + 11, '-3:25', 16, th.fg)   # ip_text_edge: box y BAR_Y - 1, 22 tall, middle
    return im

def speaker(im, x, y, waves, ink, o):
    """patch/ipod.c ip_speaker: a 3 x 6 body, a 4 column cone, `waves` arcs 3 px apart."""
    d = ImageDraw.Draw(im); f = lambda x0, y0, w, h: d.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=ink)
    f(x, y - 3, 3, 6)
    for i in range(4): f(x + 3 + i, y - 4 - i, 1, 8 + 2 * i)
    for i in range(waves):
        h = 6 + 4 * i; X = o['IP_SPK_W'] + x
        f(X + 2 + 3 * i, y - h // 2 + 1, 1, h - 2); f(X + 1 + 3 * i, y - h // 2, 1, 1); f(X + 1 + 3 * i, y + h // 2 - 1, 1, 1)

def diamond(im, x, y, k, bg, refl):
    """patch/ipod.c ip_diamond: k rows each side in the bar's blue of each row (rim outline), then its reflection mirrored as the bar's, alpha (n - 1 - r) * 56 / (n - 1)."""
    mix = lambda a, b, t: tuple(p + (q - p) * t // 256 for p, q in zip(a, b))
    bh = len(NP_BLUE)
    def row(yy, dy, alpha):
        w = k - abs(dy)
        if w < 0: return
        fill = hexrgb(NP_BLUE[min(max(dy + bh // 2, 0), bh - 1)]); rim = mix(fill, (0x7a, 0x96, 0xb8), 77)
        fill, rim = mix(bg, fill, alpha), mix(bg, rim, alpha)
        for xx in range(x - w, x + w + 1): im.putpixel((xx, yy), (rim if w <= 1 or xx in (x - w, x + w) else fill) + (255,))
    for dy in range(-k, k + 1): row(y + dy, dy, 255)
    top = y - bh // 2
    for r in range(refl - 1): row(top + bh + 1 + r, bh - 1 - r - bh // 2, (refl - 1 - r) * 56 // (refl - 1))

NP_BLUE = (0x7e97d7, 0x87abff, 0x769efa, 0x6e9cf6, 0x6c9df4, 0x6ba1f8, 0x66a3ff, 0x3d89eb, 0x3698f9, 0x33a3ff, 0x37b0ff, 0x42b4fd, 0x5cbbff, 0x5c9ed0)
NP_GREY = (0xe1, 0xfb, 0xff, 0xfa, 0xf6, 0xf4, 0xf0, 0xe8, 0xe3, 0xe5, 0xee, 0xf2, 0xed, 0xc5)

def bar_row(im, y, i, x0, tw, fw, alpha, bg):
    """patch/ipod.c ip_bar_row: the fill (a darker rim on its left, a dark then a light column where it ends), then the sunken grey track; alpha mixes into bg."""
    mix = lambda a, b, t: tuple(p + (q - p) * t // 256 for p, q in zip(a, b))
    fill = hexrgb(NP_BLUE[i]); track = (NP_GREY[i],) * 3
    rim, glint = mix(fill, (0x7a, 0x96, 0xb8), 77), mix(fill, (0xd0,) * 3, 102)
    fill, track, rim, glint = (mix(bg, c, alpha) for c in (fill, track, rim, glint))
    for x in range(tw):
        c = fill if x < fw else track
        if 0 < i < len(NP_BLUE) - 1 and fw > 0:
            if x == 0 or (fw >= 3 and x == fw - 2): c = rim
            elif fw >= 3 and x == fw - 1: c = glint
        im.putpixel((x0 + x, y), c + (255,))

def shuffle_strip(s, im, th, o, cur, thumb=None):
    """patch/ipod.c ip_shuf_strip: the shuffle mark IP_SHUF_ICON px where the elapsed time was, then one rail over the track (faint rim, corners cut two rows deep, a groove
    shaded under the top, no dividers) and the thumb, a raised panel in the bar's gloss (no outline, soft sides) with its own rim over the chosen third (`thumb`: its slot position mid-glide). Names fixed, the chosen one blue."""
    py, bh, tx0, tw, gap, ic = o['IP_NP_BAR_Y'], o['IP_NP_BAR_H'], o['IP_NP_TRACK_X'], o['IP_NP_TRACK_W'], o['IP_NP_TIME_GAP'], o['IP_SHUF_ICON']
    y = py + bh // 2; h = o['IP_SHUF_H']; top = y - h // 2
    icon_x = tx0 - gap - ic; tx0, tw = o['IP_SHUF_X'], o['IP_SHUF_W']; slot = tw // 3
    g = Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', 'ipod_shuffle_big.png')).convert('RGBA')   # ip_mode_bitmap(4): coverage over black, tinted
    cov = Image.alpha_composite(Image.new('RGBA', g.size, (0, 0, 0, 255)), g).convert('L')
    mk = Image.new('RGBA', (ic, ic), th.bg + (255,)); mk.paste(Image.new('RGBA', (ic, ic), th.mode + (255,)), (0, 0), cov)
    im.alpha_composite(mk, (icon_x, y - ic // 2))
    mix = lambda a, b, t: tuple(p + (q - p) * t // 256 for p, q in zip(a, b))
    lerp = lambda a, b, k, n: tuple(p + (q - p) * k // n for p, q in zip(a, b))
    rim = mix(th.bg, (0x9a,) * 3, 140); d = ImageDraw.Draw(im)
    for r in range(h):
        inn = 2 if r in (0, h - 1) else 1 if r in (1, h - 2) else 0
        d.line((tx0 + inn, top + r, tx0 + tw - inn - 1, top + r), fill=rim + (255,))
        if 0 < r < h - 1:
            c = {1: (0xc8,) * 3, 2: (0xd6,) * 3, 3: (0xe0,) * 3}.get(r) or lerp((0xe6,) * 3, (0xf2,) * 3, r - 4, h - 6)
            d.line((tx0 + inn + 1, top + r, tx0 + tw - inn - 2, top + r), fill=c + (255,))
    x = tx0 + int((cur if thumb is None else thumb) * slot)
    for r in range(h):   # the rail's full height, over its rim, with its cut corners
        inn = 2 if r in (0, h - 1) else 1 if r in (1, h - 2) else 0
        i = r * len(NP_GREY) // h  # the progress bar's gloss, row for row: its track's greys tinted with a little of its fill's blue
        face = mix((NP_GREY[i],) * 3, hexrgb(NP_BLUE[i]), 24)
        d.line((x + inn, top + r, x + slot - inn - 1, top + r), fill=mix(face, (0xa9, 0xb1, 0xbc), 128) + (255,))
        d.line((x + inn + 1, top + r, x + slot - inn - 2, top + r), fill=face + (255,))
    for i, t in enumerate(('Off', 'Songs', 'Albums')):
        s.text(im, tx0 + i * slot + slot // 2, py - 1 - o['IP_SHUF_TEXT_UP'] + 11, t, 14, (0x0C, 0x62, 0xD2) if i == cur else th.np, 'm')

def screen_lyrics(s, th, sh, cjk=False, top=0):
    """patch/ipod.c ip_lyr_paint (the iPod's lyrics view): the song in the title bar; a small cover, the album (14) and the bold artist (18) beside it; the wrapped lines
    (15 px, IP_LY_LINE apart) under it; the whole page scrolled `top` lines; a thin scroll bar at the right edge. The lines are made-up sample text."""
    o = pod_ui.OFFSETS
    im = Image.new('RGBA', (W, sh), th.bg + (255,))
    side = o["IP_ART"]
    art = Image.new('RGB', (side, side)); p = art.load()
    for y in range(side):
        for x in range(side): p[x, y] = (30 + x * 170 // side, 40 + y * 150 // side, 110 + (x + y) * 80 // (2 * side))
    ImageDraw.Draw(art).rectangle((16, 18, 134, 48), fill=(228, 220, 183))
    ImageDraw.Draw(art).ellipse((26, 60, 124, 140), fill=(30, 46, 69))
    title, artist, album = ('麦芽糖', '周杰伦', '11月的萧邦') if cjk else ('Yellow', 'Coldplay', 'Parachutes')
    lines = (['清晨的风吹过安静的街道', '窗外的树影慢慢地摇晃', '我们走过长长的小路', '天空是一片淡淡的蓝', '', '远处的灯光一盏一盏亮起',
              '城市在夜色里轻轻呼吸', '这是一段示例的歌词文字'] if cjk else
             ['A quiet line about the morning light', 'that falls across the kitchen floor', '', 'Another verse that runs a little longer than the screen is wide, so it wraps',
              'onto a second row at a space', 'and keeps going down the page', 'past the bottom edge', 'where the wheel scrolls it'])
    LINE, X, Wd = o['IP_LY_LINE'], o['IP_LY_X'], o['IP_LY_W']
    rows = []
    for ln in lines:   # ip_lyr_layout: the most words that fit
        if not ln: rows.append(''); continue
        words, cur = ln.split(' '), ''
        for w_ in words:
            t = (cur + ' ' + w_) if cur else w_
            if s.font.width(t, 15) <= Wd or not cur: cur = t
            else: rows.append(cur); cur = w_
        rows.append(cur)
    y0 = o['IP_LY_ART_Y'] - top * LINE
    im.paste(art.resize((o['IP_LY_ART'],) * 2, Image.BILINEAR), (o['IP_LY_ART_X'], y0))
    tx = o['IP_LY_TEXT_X']
    s.text(im, tx, y0 + o['IP_LY_ALBUM_DY'] + 10, s.clip(album, 14, W - tx - 12), 14, th.np)
    af = s.title_face(artist); s.text(im, tx, y0 + o['IP_LY_ARTIST_DY'] + 12, s.clip(artist, 18, W - tx - 12, af), 18, th.fg, font=af)
    for i, r in enumerate(rows):
        y = y0 + o['IP_LY_ART'] + o['IP_LY_GAP'] + i * LINE
        if r and o['IP_BAR_H'] - LINE < y < sh: s.text(im, X, y + LINE / 2, r, 14, th.np)
    room = sh - o['IP_BAR_H'] - 4; content = o['IP_LY_ART'] + o['IP_LY_GAP'] + len(rows) * LINE + o['IP_LY_GAP'] // 2; vis = sh - o['IP_LY_ART_Y']
    mx = max(0, -(-(content - vis) // LINE))
    if mx:
        mix = lambda a, b, t: tuple(p + (q - p) * t // 256 for p, q in zip(a, b))
        h = max(12, room * vis // (vis + mx * LINE)); ty = o['IP_BAR_H'] + 2 + (room - h) * min(top, mx) // mx; sx = W - o['IP_LY_SB_W'] - 2
        d = ImageDraw.Draw(im)
        d.rectangle((sx, o['IP_BAR_H'] + 2, sx + o['IP_LY_SB_W'] - 1, o['IP_BAR_H'] + 1 + room), fill=mix(th.bg, th.fg, 24) + (255,))
        d.rectangle((sx, ty, sx + o['IP_LY_SB_W'] - 1, ty + h - 1), fill=mix(th.bg, th.fg, 110) + (255,))
    title_bar(s, im, th, title)
    return im

def screen_cf(s, th, sh):
    """An approximation of the Cover Flow screen (patch/ipod_cf.c; the real renderer is the host-built one of test/coverflow.py): the IPCF_* numbers place an IPCF_ART px centre cover at
    IPCF_TOP under the bar, trapezoid side covers at IPCF_X1 / IPCF_XS, the reflection IPCF_REFLECT rows, the two caption lines at IPCF_CAP_Y."""
    o = pod_ui.OFFSETS
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); art, top, y0 = o['IPCF_ART'], o['IPCF_TOP'], o['IPCF_FRAME_Y']
    for k in (-3, -2, -1, 3, 2, 1, 0):
        rgb = ALBUMS[(k + 3) % len(ALBUMS)][1]
        if k == 0:
            c = cover(rgb, art); x, y = (W - art) // 2, y0 + top; im.alpha_composite(c, (x, y)); reflect(im, c, x, y + art, 0.4, o['IPCF_REFLECT'])
        else:
            n = abs(k); h = int(art * (0.80 - 0.07 * (n - 1))); w = int(art * 0.30)
            sq = cover(rgb, art).resize((w, h), Image.LANCZOS)
            dst = sq.transform((w, h), Image.QUAD, (0, -6, 0, h + 6, w, h, w, 0) if k < 0 else (0, 0, 0, h, w, h + 6, w, -6), Image.BICUBIC)
            cx = W // 2 + (1 if k > 0 else -1) * (o['IPCF_X1'] + (n - 1) * o['IPCF_XS'])
            x = cx - w // 2; y = y0 + top + (art - h) // 2
            im.alpha_composite(dst, (x, y)); reflect(im, dst, x, y + h, 0.25, o['IPCF_REFLECT'] * 2 // 3)
    s.text(im, W // 2, o['IPCF_CAP_Y'] + o['IPCF_CAP_H'] / 2, 'Kind of Blue', 18, th.fg, 'm')
    s.text(im, W // 2, o['IPCF_CAP_Y'] + o['IPCF_CAP_H'] * 1.5, 'Miles Davis', 18, th.fg, 'm')
    title_bar(s, im, th, 'Cover Flow')
    return im

def wheel(s, th, region_h, diam):
    """The click wheel on the body colour: ring + hub drawn at 4x and reduced, labels at 1x."""
    k = 4; im = Image.new('RGBA', (W * k, region_h * k), th.body + (255,))
    d = ImageDraw.Draw(im); cx, cy, r = W * k // 2, region_h * k // 2, diam * k // 2
    ring = Image.new('RGBA', im.size, (0, 0, 0, 0))
    for y in range(cy - r, cy + r):   # vertical gradient clipped to the disc
        t = (y - (cy - r)) / (2 * r)
        ImageDraw.Draw(ring).line((0, y, im.width, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(*th.ring)) + (255,))
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    d.ellipse((cx - r - k, cy - r - k, cx + r + k, cy + r + k), fill=((0, 0, 0) if th.dark else (0xA8, 0xAB, 0xB0)) + (255,))
    im.paste(ring, (0, 0), m)
    hr = int(r * 0.41); hub = Image.new('RGBA', im.size, (0, 0, 0, 0))
    for y in range(cy - hr, cy + hr):
        t = (y - (cy - hr)) / (2 * hr)
        ImageDraw.Draw(hub).line((0, y, im.width, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(*th.hub)) + (255,))
    hm = Image.new('L', im.size, 0); ImageDraw.Draw(hm).ellipse((cx - hr, cy - hr, cx + hr, cy + hr), fill=255)
    d.ellipse((cx - hr - k, cy - hr - k, cx + hr + k, cy + hr + k), fill=((0x40,) * 3 if th.dark else (0xB0,) * 3) + (255,))
    im.paste(hub, (0, 0), hm)
    # glyphs on the ring, drawn at 4x
    lab = th.label + (255,); rm = int((r + hr) / 2); g = 5 * k
    for sx in (-1, 1):   # |<<  and  >>|: two triangles pointing along sx, then the bar
        x = cx + sx * rm
        for xc in (x - sx * 3 * k, x + sx * 3 * k - sx * 6 * k * 0):
            d.polygon([(xc - sx * 3 * k, cy - g), (xc - sx * 3 * k, cy + g), (xc + sx * 3 * k, cy)], fill=lab)
        bx = x + sx * 8 * k
        d.rectangle((min(bx, bx + sx * 2 * k), cy - g, max(bx, bx + sx * 2 * k), cy + g), fill=lab)
    by = cy + rm   # play / pause
    d.polygon([(cx - 8 * k, by - 5 * k), (cx - 8 * k, by + 5 * k), (cx - 1 * k, by)], fill=lab)
    d.rectangle((cx + 2 * k, by - 5 * k, cx + 4 * k, by + 5 * k), fill=lab); d.rectangle((cx + 6 * k, by - 5 * k, cx + 8 * k, by + 5 * k), fill=lab)
    out = im.resize((W, region_h), Image.LANCZOS)
    s.text(out, W // 2, region_h / 2 - rm / k, 'MENU', 14, th.label, 'm')
    return out

def frame(s, th, screen, sh, bar=False):
    """bar=False: a fullscreen window (like the lock screen, screensaver_page) over the stock status bar."""
    top = BAR if bar else 0
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    if bar: PI.status_bar(s, im)
    im.alpha_composite(screen, (0, top))
    ImageDraw.Draw(im).rectangle((0, top + sh, W - 1, H - 1), fill=th.body + (255,))
    im.alpha_composite(s.img('ipod_wheel_dark' if th.dark else 'ipod_wheel'), (50, 250))
    return im

def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'ipod-mock.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True)
    frames = []
    for dark in (False, True):
        th = Theme(dark); name = 'Dark' if dark else 'Light'
        pages = [('Main menu', screen_main(s, th, 240)), ('Music', screen_music(s, th, 240)),
                 ('Settings', screen_settings(s, th, 240)), ('Albums', screen_albums(s, th, 240)),
                 ('Songs', screen_songs(s, th, 240)), ('Now Playing', screen_now(s, th, 240, "repeat1" if dark else "shuffle", dark)), ("Cover Flow", screen_cf(s, th, 240))]
        frames += [(f'{name}: {label}', frame(s, th, page, 240)) for label, page in pages]
    pad, lab, cols = 12, 22, 7
    sheet = Image.new('RGB', (pad + cols * (W + pad), 2 * (lab + H + pad) + pad), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(frames):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (lab + H + pad)
        d.text((x, y - 2), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
    save_true(sheet, out); print('wrote', out, sheet.size)
    # Now Playing's three bars side by side (light): progress, volume (a wheel turn), scrubber (the centre).
    th = Theme(False); modes = [screen_now(s, th, 240, 'shuffle', mode=md).convert('RGB') for md in ('time', 'volume', 'scrub', 'shuffle')]
    modes += [screen_lyrics(s, th, 240).convert('RGB'), screen_lyrics(s, th, 240, cjk=True).convert('RGB')]
    strip = Image.new('RGB', (len(modes) * W + (len(modes) - 1) * pad, 240), (0x2A,) * 3)
    for i, im in enumerate(modes): strip.paste(im, (i * (W + pad), 0))
    save_true(strip, os.path.splitext(out)[0] + '-np-modes.png')
    # The shuffle slider's choices and the thumb mid-glide (Off -> Songs), the bar's row only.
    o = pod_ui.OFFSETS; rows = []
    for cur, thumb in ((0, None), (1, 0.5), (1, None), (2, None)):
        im = Image.new('RGBA', (W, 240), th.bg + (255,)); shuffle_strip(s, im, th, o, cur, thumb)
        rows.append(im.crop((0, o['IP_NP_BAR_Y'] - 14, W, o['IP_NP_BAR_Y'] + 30)).convert('RGB'))
    strip = Image.new('RGB', (W, len(rows) * 44 + (len(rows) - 1) * 4), (0x2A,) * 3)
    for i, im in enumerate(rows): strip.paste(im, (0, i * 48))
    save_true(strip, os.path.splitext(out)[0] + '-shuffle.png')
    # The same smoothstep slide and half-width clipping / split as ipod_render.c and ipod.c ip_paint_split.
    duration = cdefs.defines(os.path.join(build.ROOT, 'patch', 'ipod_render.c'), ['SLIDE_MS'])['SLIDE_MS']
    th = Theme(False)
    stem = os.path.splitext(out)[0]
    music, main_, now = screen_music(s, th, 240), screen_main(s, th, 240), screen_now(s, th, 240, "shuffle")
    main_ns = screen_main(s, th, 240, shadow=False)   # the halves of a split move apart: the shadow goes with the menu half
    def travel_at(ms, span):
        p = ms * 1024 // duration; return span * ((p * p // 1024) * (3072 - 2 * p) // 1024) // 1024
    def push_half(ms):   # Main -> Music: the menu half slides, the pane stays
        t = travel_at(ms, 160); page = main_.copy(); left = Image.new('RGBA', (160, 240), th.bg + (255,))
        left.alpha_composite(main_.crop((0, 0, 160, 240)), (-t, 0)); left.alpha_composite(music.crop((0, 0, 160, 240)), (160 - t, 0)); page.paste(left, (0, 0)); return page
    def split_open(ms):   # Main -> Now Playing: Now Playing stays, the menu half goes left and the pane right
        t = travel_at(ms, 160); page = now.copy()
        page.paste(main_ns.crop((160, 0, 320, 240)), (160 + t, 0)); page.paste(main_ns.crop((0, 0, 160, 240)), (-t, 0)); page.alpha_composite(shadow_layer(), (160 - t, 0)); return page
    def split_close(ms):   # Now Playing -> Main: the halves come back in over it
        t = travel_at(ms, 160); page = now.copy()
        page.paste(main_ns.crop((160, 0, 320, 240)), (160 + (160 - t), 0)); page.paste(main_ns.crop((0, 0, 160, 240)), (-(160 - t), 0)); page.alpha_composite(shadow_layer(), (t, 0)); return page
    def full_push(ms):   # Music -> Albums: 320 px
        t = travel_at(ms, 320); page = Image.new('RGBA', (W, 240), th.bg + (255,)); page.paste(music, (-t, 0)); page.paste(screen_albums(s, th, 240), (320 - t, 0)); return page
    steps = [0, duration // 4, duration // 2, duration * 3 // 4, duration]
    rows_ = [('Main > Music: the menu half slides (the pane stays)', push_half), ('Main > Now Playing: the split open', split_open),
             ('Now Playing > Main: the split closes', split_close), ('Music > Albums: the whole width', full_push)]
    strip = Image.new('RGB', (pad + 5 * (W + pad), len(rows_) * (240 + lab + pad) + pad), (42,) * 3)
    sd = ImageDraw.Draw(strip); animation = []
    for r, (label, fn) in enumerate(rows_):
        for i, ms in enumerate(steps):
            x, y = pad + i * (W + pad), pad + r * (240 + lab + pad)
            strip.paste(fn(ms).convert('RGB'), (x, y + lab)); sd.text((x, y), f'{label}  {ms} ms' if i == 0 else f'{ms} ms', fill=(210,) * 3)
    save_true(strip, stem + '-transitions.png')
    for fn in (split_open, push_half):
        animation += [frame(s, th, fn(ms), 240).convert('RGB') for ms in range(0, duration + 1, 40)]
    animation[0].save(stem + '-transition.gif', save_all=True, append_images=animation[1:], duration=40, loop=0)
    # The cover pane: a cover pans linearly for 7.5 s, the next fades in 6 s after it began over 1.5 s (smoothstep), both panning; whole-pixel windows of one scaled cover each.
    r_, x0 = pod_ui.OFFSETS['IP_PANE_R'], 40
    pan_, hold_, fade_ = (pod_ui.OFFSETS[k] for k in ('IP_PANE_PAN_MS', 'IP_PANE_HOLD_MS', 'IP_PANE_FADE_MS'))
    a_art, b_art = cover((70, 110, 190), 264), cover((190, 90, 120), 264)
    def window(art, pos):
        """The pane's 160 x 240 window at pos / 256 px: each pixel the linear mix of its source column and the next (a bilinear sample on an exact row), as ip_pane_frame."""
        return art.transform((160, 240), Image.AFFINE, (1, 0, x0 + pos / 256, 0, 1, 12), Image.BILINEAR)
    def pane_at(ms):
        pa = r_ * 256 * ms // pan_; pb = r_ * 256 - r_ * 256 * max(0, ms - hold_) // pan_   # 1/256 px, as ip_pane_pos
        wa = window(a_art, pa)
        if ms < hold_: return wa
        wb = window(b_art, pb); p = min(1023, (ms - hold_) * 1024 // fade_)
        return Image.blend(wa, wb, ((p * p // 1024) * (3072 - 2 * p) // 1024) / 1024)
    times = [0, 3000, 6000, 6375, 6750, 7125, 7500]
    pstrip = Image.new('RGB', (pad + len(times) * (W + pad), 240 + lab + 2 * pad), (42,) * 3); pd = ImageDraw.Draw(pstrip)
    for i, ms in enumerate(times):
        page = main_ns.copy(); page.paste(pane_at(ms), (160, 0)); page.alpha_composite(shadow_layer(), (160, 0)); x = pad + i * (W + pad)
        pstrip.paste(page.convert('RGB'), (x, pad + lab)); pd.text((x, pad), f'{ms / 1000:.2f} s', fill=(210,) * 3)
    save_true(pstrip, stem + '-pane.png')
    # The pan itself: 40 ms frames (3 s of it) as a GIF, and six consecutive frames of a detail, 6 x, each a fraction of a pixel on from the last.
    pan_frames = [frame(s, th, (lambda pg: (pg.paste(pane_at(ms), (160, 0)), pg.alpha_composite(shadow_layer(), (160, 0)), pg)[2])(main_ns.copy()), 240).convert('RGB') for ms in range(0, 3000, 40)]
    pan_frames[0].save(stem + '-pan.gif', save_all=True, append_images=pan_frames[1:], duration=40, loop=0)
    strip6 = Image.new('RGB', (6 * 8 + 6 * 360, 360 + 20), (42,) * 3)
    for i in range(6):
        win = pane_at(1000 + 40 * i).crop((14, 100, 74, 160)).resize((360, 360), Image.NEAREST)
        strip6.paste(win.convert('RGB'), (8 + i * 368, 10))
    save_true(strip6, stem + '-pan-frames.png')
    # The menu's shadow on a light cover and on the plain pane, 10 x: darkest at x 160, gone by x 170.
    edge = Image.new('RGB', (2 * 500 + 30, 600 + 20), (42,) * 3)
    for i, rgb in enumerate(((235, 220, 175), None)):
        page = screen_main(s, th, 240, rgb=rgb or (0, 0, 0))
        if rgb is None: page.paste(Image.new('RGBA', (160, 240), (0xF2, 0xF3, 0xF5, 255)), (160, 0)); page.alpha_composite(shadow_layer(), (160, 0))
        edge.paste(page.crop((140, 60, 190, 120)).resize((500, 600), Image.NEAREST).convert('RGB'), (10 + i * 510, 10))
    save_true(edge, stem + '-edge.png')
    # The reference's palette beside ours: title bar, selection, battery, Now Playing bar (the numbers of iPlayr's colour sets).
    ref = Image.new('RGBA', (W, 120), (255, 255, 255, 255))
    stops(ref, (0, 0, W, 25), list(zip((0, 42, 47, 100), [hexrgb(h) for h in (0xFDFDFD, 0xE7E7E7, 0xD8D8D8, 0xABABAB)])))
    stops(ref, (0, 40, W, 67), [(0, hexrgb(0x3EABE3)), (25, hexrgb(0x37A0E0)), (50, hexrgb(0x2C97DC)), (75, hexrgb(0x218CD6)), (100, hexrgb(0x1584D3))])
    battery(ref, 8, 6, th); battery(ref, 50, 6, th, 0.15, True); play_glyph(ref, 100, 5)
    for i in range(14): ImageDraw.Draw(ref).line((8, 80 + i, 8 + 150, 80 + i), fill=hexrgb(0x3698F9) + (255,))
    sheet2 = Image.new('RGB', (W, 240), (42,) * 3)
    ours = screen_main(s, th, 240).crop((0, 0, 160, 120)); sheet2.paste(ours.convert('RGB'), (0, 0)); sheet2.paste(ref.crop((0, 0, W, 120)).convert('RGB'), (0, 120))
    save_true(sheet2, stem + '-palette.png')
    # The battery at 100, 60 and 20 % (the title bar's right end, in both appearances' screen), 6 x.
    cells = []
    for pct in (1.0, 0.6, 0.2):
        bar = Image.new('RGBA', (70, pod_ui.OFFSETS['IP_BAR_H']), th.bg + (255,)); title_bar(s, bar, th, '', width=70, state='playing', pct=pct); cells.append(bar.resize((420, 6 * pod_ui.OFFSETS['IP_BAR_H']), Image.NEAREST))
    levels = Image.new('RGB', (3 * 420 + 4 * 8, 160), (42,) * 3)
    for i, c in enumerate(cells): levels.paste(c.convert('RGB'), (8 + i * 428, 8))
    save_true(levels, stem + '-battery.png')
    # An artist's albums (All Songs first, placeholder covers) and a one-album artist's song list, with the wheel.
    pair = Image.new('RGB', (pad + 2 * (W + pad), 240 + lab + 2 * pad), (42,) * 3); pdr = ImageDraw.Draw(pair)
    for i, (label, page) in enumerate((('Artist: All Songs first', screen_artist(s, th, 240)), ('One-album artist: its songs', screen_album_songs(s, th, 240)))):
        pair.paste(page.convert('RGB'), (pad + i * (W + pad), pad + lab)); pdr.text((pad + i * (W + pad), pad), label, fill=(210,) * 3)
    save_true(pair, stem + '-artists.png')
    # The three play mode marks on Now Playing's top right, light and dark appearance's screen alike, 6 x.
    marks = Image.new('RGB', (3 * 8 + 3 * 6 * 80, 6 * 32 + 16), (42,) * 3)
    for i, name in enumerate(('shuffle', 'repeat', 'repeat1')):
        crop = screen_now(s, th, 240, name).crop((240, 24, 320, 56)).resize((480, 192), Image.NEAREST)
        marks.paste(crop.convert('RGB'), (8 + i * 488, 8))
    save_true(marks, stem + '-marks.png')

if __name__ == '__main__':
    main()
