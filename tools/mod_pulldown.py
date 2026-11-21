#!/usr/bin/env python3
"""The pull-down control centre: its status bar the real one, its text one step smaller (V2.1gB, docs/ui.md).

ui/dialog/dropdown_dialog.bin (the dialog has no page theme, styles/ has no
dropdown_dialog.bin) carries its own copy of the status bar (view_sysbar) and the tile captions:

  view_sysbar    laid out from the table the real bar (ui/system_bar.bin) uses, tools/statusbar.py: left group
                 at x 10, 4 px spacing, the volume number 16 px middle in 30 px, the clock 104..194 at 18 px, the
                 right group 4 px spacing and clear of the battery; the bar black as the real one
  pod_tile_*,    the eight tiles of ours (Sleep Timer, Settings, Equalizer, Power Off, AirPlay, DLNA, Wi-Fi Transfer, Screenshot: patch/pulldown.c shows them in the slots the saved file names): an
  pod_cap_*      image and a caption in view_switchs, added hidden and insensitive, the caption a copy of label_playset with the tile's text
  label_*        the eight tile captions (Wi-Fi, Bluetooth, Buttons lock, gain, USB mode, output,
                 Playback / System Setting): 71 x 36 boxes (stock 57 x 40) 5 px under the disc, top aligned, word-wrapped,
                 16 px #B0B0B0 (disabled #555555; stock 18 / 16 px white)
  img_*, label_* the tile images 56 x 56 (stock 50) round the stock centres, rows 100 apart as stock: x 21 / 95 / 169 / 243, y 11 / 111; no card under them, the discs sit on the panel
  pod_grabber    an image (drop_grabber: Now Playing's 36 x 5 pill, white at alpha 110, baked) at (142, 328) in the dialog, insensitive
  the dialog     background black at 92 % (PANEL_ALPHA; stock #141414); the status bar copy stays opaque black

pgbar_battery shows no number there (show_text false, stock), the slider and the icons have no text.
The caption boxes are 71 px wide (stock 57) around the new tile's centre (the tiles are 74 px apart, so
3 px stay between neighbours): "Bluetooth" is 60 px at 16, so in 57 AWTK broke it as "Bluetoot/h".
  view_backlight the brightness card: a flat #1C1C1E card, radius 26, 300 x 52 at (10, 265) (stock: a 300 x 50 black pill image at y 266), holding stock's own
                 widgets by stock's names (image0, image1, slider_backlight) laid out as the Display page's brightness card (pod_ui.bright_control): the
                 slider's absolute y 266 .. 316 is stock's, only its x (58 .. 258) and look change
The tool measures what it
sets with the shared text model (awtk_text.StbText: truncated advances + 1 px per glyph) in the
tree's own font, so it must run after the font step:

  - "100" (the widest volume) must fit label_volume (30 px);
  - "12:59 PM" (the widest clock) must fit bar_dclock;
  - every tile caption in English and Simplified Chinese (strings/en_US.bin, zh_CN.bin, the keys
    demo sets @0x4743c8..) must wrap into the 32 px box (lines x font size), greedy word wrap as
    AWTK breaks lines, and no Latin word may be broken inside; the other languages are reported
    (several overflow or break words already in stock).

Usage: mod_pulldown.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statusbar, pod_i18n, awtk_strings
from modlib import clone_workdir, edit_ui
from awtk_text import Ttf, awtk_width
from pod_roles import SURFACE_RGB, SUB_RGB

RAW = 'rootfs/release/assets/default/raw'
DIALOG = 'ui/dialog/dropdown_dialog.bin'
FONT = 'rootfs/release/assets/default/raw/fonts/default.ttf'
STATES = ('normal', 'disable', 'focused')
# old -> new inline font sizes: every caption 16 px (stock 18, disabled and focused 16; main's pull-down uses 16 / 14)
CAPTION_PX = 16
TILE = {18: CAPTION_PX, 16: CAPTION_PX}
CAPTION_RGB, CAPTION_DIS_RGB = SUB_RGB, '#555555'     # secondary text; a disabled tile's caption
PANEL_RGB, PANEL_ALPHA = '#000000', 0.92                # the dialog's background: black at this opacity (stock #141414); the cards and discs are opaque
PANEL_BG = f'{PANEL_RGB}{round(255 * PANEL_ALPHA):02X}'
CARD_X = 10                                             # the brightness card's x
TILE_PX = 56                                            # the tile images: stock 50 x 50, grown round the same centres
COLS_X, ROWS_Y = (21, 95, 169, 243), (11, 111)          # the 56 px tiles' x (stock 24 + 74 k, minus 3) and y in view_switchs (stock rows 14 and 114, 100 apart as now)
CAP_DX, CAP_DY, CAP_H = -7, TILE_PX + 5, 36             # a caption box from its tile: 71 wide centred on it, 5 px under the disc, two rows of 16 px (CAP_MT + 16 + CAP_SPACER + 16)
# AWTK's wrapped label (tools/mod_nowplaying.py, before LYR_DEFAULT_MARGIN) wraps to the box less margin_left / margin_right and draws a row only while it ends inside the box less
# margin_bottom; rows are font + spacer apart (default 2, tools/pod_pins.py). Every margin defaults to 2: the captions set left, right and bottom to 0 and keep the top 2.
CAP_MT, CAP_SPACER, CAP_MARGINS = 2, 2, ('margin_left', 'margin_right', 'margin_bottom')
BL_Y, BL_R = 265, 26                                    # the brightness card's y in the dialog (the slider inside keeps stock's screen y 266 .. 316) and radius; it is ROW_H high, CARD_W wide, at CARD_X
STOCK_BL = ((10, 266, 300, 50), (20, 15, 20, 20), (260, 15, 20, 20), (50, 0, 200, 50))   # stock's view_backlight and its image0, image1, slider_backlight (pinned)
GRAB = ('pod_grabber', 142, 328, 36, 5, 'drop_grabber')    # the grabber, a child of the dialog: name, x, y, w, h, image (the dialog is 340 high); a baked, antialiased copy of Now Playing's pill (mod_icons DROP_GRABBER)
IMGS = ('img_wifiswitch', 'img_btswitch', 'img_keylockswitch', 'img_gainswitch', 'img_usbmode', 'img_outputswitch', 'img_playset', 'img_sysset')   # TILES' images, in the same order
STOCK_X, STOCK_Y = (24, 98, 172, 246), (14, 114)        # where the stock tiles are (pinned)
TILES = ('label_wifi', 'label_bt', 'label_lock', 'label_gain', 'label_usbmode', 'label_outputway',
         'label_playset', 'label_sysset')
# the tile captions' string keys (demo @0x4743c8..0x474b70: widget_set_tr_text on the labels above)
TILE_KEYS = ('wifiset_wifi', 'wifiset_bt', 'system_keylock', 'gain_high', 'gain_low', 'sset_outputway',
             'playset', 'sysset', 'usbmode_audio', 'usbmode_dac', 'usbmode_storge')
# the tiles of ours: (image, caption, the image's picture, the caption's English text), after the stock tile it follows (the places are patch/pulldown.c's: a shown tile takes a slot)
OWN = (('pod_tile_sleep', 'pod_cap_sleep', 'drop_sleep', 'Sleep Timer'), ('pod_tile_settings', 'pod_cap_settings', 'drop_settings', 'Settings'),
       ('pod_tile_eq', 'pod_cap_eq', 'drop_equalizer', 'Equalizer'), ('pod_tile_power', 'pod_cap_power', 'drop_power', 'Power Off'),
       ('pod_tile_airplay', 'pod_cap_airplay', 'drop_airplay', 'AirPlay'), ('pod_tile_dlna', 'pod_cap_dlna', 'drop_dlna', 'DLNA'),
       ('pod_tile_transfer', 'pod_cap_transfer', 'drop_transfer', 'Wi-Fi Transfer'),
       ('pod_tile_shot', 'pod_cap_shot', 'drop_shot', 'Screenshot'))
CAPTION_OWN_PX = {'Screenshot': 15}   # a caption of ours set smaller than CAPTION_PX: the word is 74 px at 16 in the 71 px text width (71 at 15 fits)
MUST_FIT = ('en_US', 'zh_CN')
VOLUME_MAX, CLOCK_MAX = '100', '12:59 PM'
TILE_W = 71                              # caption box width (stock 57)


def check(ok, msg):
    if not ok: raise SystemExit(f'mod_pulldown: {msg}')


def strings(path, keys):
    """key -> text from an AWTK strings/*.bin (a table of NUL-terminated key, value pairs)."""
    d = open(path, 'rb').read(); out = {}
    for k in keys:
        i = d.find(b'\0' + k.encode() + b'\0')
        if i < 0: continue
        j = i + len(k) + 2
        out[k] = d[j:d.index(b'\0', j)].decode('utf-8')
    return out


def wrap(ttf, text, px, width):
    """Lines of a word-wrapped label: break after spaces, before and after CJK characters, and
    inside a word that is wider than the box on its own (AWTK's line breaker does the same)."""
    toks, cur = [], ''
    for ch in text:
        if ch == ' ': toks.append(cur + ' '); cur = ''
        elif ord(ch) >= 0x2e80:
            if cur: toks.append(cur); cur = ''
            toks.append(ch)
        else: cur += ch
    if cur: toks.append(cur)
    lines, line = [], ''
    for t in toks:
        if awtk_width(ttf, (line + t).rstrip(), px) <= width: line += t; continue
        if line.strip(): lines.append(line.rstrip())
        line = ''
        while awtk_width(ttf, t.rstrip(), px) > width:
            k = len(t)
            while k > 1 and awtk_width(ttf, t[:k], px) > width: k -= 1
            lines.append(t[:k]); t = t[k:]
        line = t
    if line.strip(): lines.append(line.rstrip())
    return lines


def split_words(ttf, text, px, width):
    """Latin words wider than the box (AWTK would break them inside)."""
    return [t for t in text.split(' ') if t.isascii() and awtk_width(ttf, t, px) > width]


def caption_rows(n, px):
    """The height n wrapped rows of a caption need from its box's top: the top margin, then rows CAP_SPACER apart (no bottom margin)."""
    return CAP_MT + n * px + (n - 1) * CAP_SPACER


def resize(w, table, states=STATES):
    """Every state that sets a font size gets the table's smaller one; returns {old: new}."""
    done = {}
    for st in states:
        v = w.get(f'style:{st}:font_size')
        if v is None: continue
        check(int(v) in table, f'{w.name}: unexpected {st} font size {v}')
        w.set(f'style:{st}:font_size', str(table[int(v)])); done[int(v)] = table[int(v)]
    check(done, f'{w.name}: no inline font size')
    return done


def add_own(root):
    """Our eight tiles in view_switchs after the stock widgets: the image (56 x 56, the stock tiles' new size, picture of the flat disc style, clickable) and its caption (a copy of label_playset
    with the tile's text), at the first slot and its caption offset; hidden and insensitive. A tile not shown stays so; patch/pulldown.c moves, shows and binds the shown ones."""
    from awtk_ui import Widget
    view, img, cap = root.find('view_switchs'), root.find('img_wifiswitch'), root.find('label_playset')
    check(view is not None and img is not None and cap is not None and cap in view.children and img in view.children, 'view_switchs / the first tile / label_playset missing')
    for name, capname, image, english in OWN:
        tile = Widget('image', img.x, img.y, img.w, img.h, [('name', name), ('draw_type', 'default'), ('image', image), ('clickable', 'true')])
        label = Widget('label', img.x + cap.x - root.find('img_playset').x, img.y + cap.y - root.find('img_playset').y, cap.w, cap.h,
                       [('name', capname)] + [p for p in cap.props if p[0] != 'name'] + [pod_i18n.text_prop(english)])
        for st in STATES:
            if english in CAPTION_OWN_PX and label.get(f'style:{st}:font_size') is not None: label.set(f'style:{st}:font_size', str(CAPTION_OWN_PX[english]))
        for w in (tile, label):
            w.set('visible', 'false'); w.set('sensitive', 'false'); view.children.append(w)


NEW = (GRAB[0],)   # the widgets this step adds besides the tiles of ours


def add_cards(root):
    """The grabber (the dialog's last child): an image of the baked pill, insensitive, so a touch reaches the dialog's own drag handlers as before. The panel's colour is set here too: black at PANEL_ALPHA,
    and the brightness card is restyled."""
    from awtk_ui import Widget
    view = root.find('view_switchs')
    check(view is not None and root.find('view_backlight') in root.children, 'view_switchs / view_backlight missing')
    check(root.get('style:normal:bg_color') == '#141414', 'the dialog\'s stock background is not #141414')
    root.set('style:normal:bg_color', PANEL_BG)
    restyle_backlight(root)
    name, x, y, w, h, image = GRAB
    grab = Widget('image', x, y, w, h, [('name', name), ('draw_type', 'default'), ('image', image), ('sensitive', 'false')])
    root.children.append(grab)


def restyle_backlight(root):
    """view_backlight becomes the brightness card: stock's pill image and corner styles go, the fill is SURFACE_RGB, and the three children (kept by name, with stock's range and value) are laid out
    by the Display page's own code (pod_ui.bright_control), so the two cannot drift."""
    import pod_ui, pod_settings as ST
    bl = root.find('view_backlight')
    kids = [bl.find(n) for n in ('image0', 'image1', 'slider_backlight')]
    check(all(kids) and bl.children == kids and kids[2].type == 'slider', 'view_backlight is not stock\'s (image0, image1, slider_backlight)')
    check(tuple((w.x, w.y, w.w, w.h) for w in [bl] + kids) == STOCK_BL, f'view_backlight\'s stock places are not the pinned ones: {[(w.x, w.y, w.w, w.h) for w in [bl] + kids]}')
    check(bl.get('style:normal:bg_image') == 'backlight_bg' and kids[2].get('max') in (None, '100'), 'view_backlight: unexpected stock look or slider range')
    check((CARD_X, ST.CARD_W, ST.ROW_H) == (10, 300, 52) and BL_Y + pod_ui.BRIGHT_SLIDER_Y == STOCK_BL[0][1] and BL_Y + ST.ROW_H + 8 <= GRAB[2], 'the brightness card is not where this step puts it')
    for key in [k for k, _ in bl.props if k.startswith('style:')]: bl.remove(key)
    for st in STATES:
        bl.set(f'style:{st}:bg_color', SURFACE_RGB); bl.set(f'style:{st}:border_width', '0'); bl.set(f'style:{st}:round_radius', str(BL_R))
    bl.x, bl.y, bl.w, bl.h = CARD_X, BL_Y, ST.CARD_W, ST.ROW_H
    pod_ui.bright_control(kids[0], kids[2], kids[1], 0)


def edit(root, ttf, texts, report):
    shape = [(w.type, w.name, w.x, w.y, w.w, w.h) for w in root.walk()]
    bright = {w.name for w in root.find('view_backlight').walk()}   # (restyled by restyle_backlight)
    sysbar = root.find('view_sysbar')
    check(sysbar is not None and all(sysbar.find(n) is not None for n in statusbar.NAMES), 'unexpected pull-down layout')
    # the pull-down's copy of the status bar is laid out from the real bar's table (tools/statusbar.py): identical
    # positions, sizes and styles, on the real bar's black
    statusbar.apply(sysbar)
    for st in statusbar.STATES: sysbar.set(f'style:{st}:bg_color', statusbar.BAR_BG)
    vol, clock = sysbar.find('label_volume'), sysbar.find('bar_dclock')
    px = int(vol.get('style:normal:font_size')); need = awtk_width(ttf, VOLUME_MAX, px)
    check(need <= vol.w, f'"{VOLUME_MAX}" needs {need} px at {px}, label_volume is {vol.w}')
    cpx = int(clock.get('style:normal:font_size')); cw = awtk_width(ttf, CLOCK_MAX, cpx)
    check(cw <= clock.w, f'"{CLOCK_MAX}" needs {cw} px at {cpx}, the clock box is {clock.w}')
    report.append(f'status bar as the real one (statusbar.py): "{VOLUME_MAX}" {need}/{vol.w} px at {px}, "{CLOCK_MAX}" {cw}/{clock.w} px at {cpx}')
    want = {}   # name -> (x, y, w, h) of every stock tile image and caption after this step
    for i, name in enumerate(TILES):
        w = root.find(name); check(w is not None and w.type == 'label', f'{name} missing')
        img = root.find(IMGS[i]); col, row = i % 4, i // 4
        check(img is not None and (img.x, img.y, img.w, img.h) == (STOCK_X[col], STOCK_Y[row], 50, 50) and (w.x, w.y, w.h) == (img.x - 3, img.y + 54, 40),
              f'{name}: the stock tile / caption places are not the pinned ones ({img and (img.x, img.y, img.w, img.h)}, {(w.x, w.y, w.w, w.h)})')
        spx = int(w.get('style:normal:font_size'))
        check(w.w == 57, f'{name}: unexpected caption width {w.w}')
        img.x, img.y, img.w, img.h = COLS_X[col], ROWS_Y[row], TILE_PX, TILE_PX     # the same centres: the disc grows by 3 px each side
        w.x, w.y, w.w, w.h = img.x + CAP_DX, img.y + CAP_DY, TILE_W, CAP_H          # before measuring: fits() reads w.w and w.h
        want[img.name], want[w.name] = (img.x, img.y, img.w, img.h), (w.x, w.y, w.w, w.h)
        changed = resize(w, TILE)
        for st in STATES:   # secondary text, from the top of the box so a one-line and a two-line caption start at the same height
            w.set(f'style:{st}:text_color', CAPTION_DIS_RGB if st == 'disable' else CAPTION_RGB)
            w.set(f'style:{st}:text_align_v', 'top')
            for m in CAP_MARGINS: w.set(f'style:{st}:{m}', '0')
        tpx = int(w.get('style:normal:font_size'))
        fits = lambda t, px, bw=w.w: caption_rows(len(wrap(ttf, t, px, bw)), px) <= w.h
        for lang in MUST_FIT:
            for k, t in texts[lang].items():
                px = CAPTION_OWN_PX.get(k, tpx)
                check(not split_words(ttf, t, px, w.w), f'{lang} {k} {t!r}: a word is wider than {w.w} px at {px}')
                check(fits(t, px), f'{lang} {k} {t!r} does not fit {w.w}x{w.h} at {px}: {wrap(ttf, t, px, w.w)}')
        if name == TILES[0]:   # the boxes are all the same size: count once
            over = lambda px, bw: sorted(f'{l}:{k}' for l, kv in texts.items() for k, t in kv.items() if not fits(t, px, bw))
            report.append(f'tile captions over {w.h} px: {len(over(spx, 57))} at {spx} px x 57 (stock), {len(over(tpx, w.w))} at {tpx} px x {w.w} '
                          f'(none in {"/".join(MUST_FIT)}); still over: {", ".join(over(tpx, w.w))}')
    report.append(f'tiles {changed}')
    add_own(root)
    add_cards(root)
    after = [(w.type, w.name, w.x, w.y, w.w, w.h) for w in root.walk() if w.name not in (statusbar.LO_WIDGET, statusbar.SYNC_WIDGET, statusbar.SLEEP_WIDGET, statusbar.EQ_WIDGET) and not w.name.startswith(('pod_tile_', 'pod_cap_')) and w.name not in NEW]   # (the Line Out pill, the sync and sleep timer icons and the EQ mark statusbar.apply adds are the new widgets)
    bar_names = {w.name for w in sysbar.walk()}
    moved = [a for a, b in zip(shape, after) if a != b and a[1] not in bar_names and a[1] not in want and a[1] not in bright]   # the bar's own widgets, the eight tiles and their captions (checked below)
    now = {w.name: (w.x, w.y, w.w, w.h) for w in root.walk()}
    check(all(now[n] == g for n, g in want.items()) and len(want) == 16, f'the tiles and captions are not where this step puts them: {[n for n, g in want.items() if now[n] != g]}')
    check(len(shape) == len(after) and not moved, f'widgets moved: {moved}')


def apply(work):
    ttf = Ttf(os.path.join(work, FONT))
    langs = os.path.join(work, RAW, 'strings')
    texts = {f[:-4]: strings(os.path.join(langs, f), TILE_KEYS) for f in sorted(os.listdir(langs)) if f.endswith('.bin')}
    check(all(len(texts[l]) == len(TILE_KEYS) for l in MUST_FIT), 'tile caption strings missing')
    for lang, kv in texts.items():   # the captions of ours (keys of ours: the English text is the key, the table is the language's own; a stock key's text is the stock table's, Sleep Timer's powerm_sleep)
        for _, _, _, english in OWN:
            key = pod_i18n.key_for(english)
            if key is None: kv[english] = english   # a brand (AirPlay, DLNA): the same text in every language, measured as it is
            elif key == english: kv[english] = pod_i18n.TEXT[english][pod_i18n.table_for(lang)]
            else:   # (de_DE, es_ES and pl_PL are 11-string stubs the strings step does not use as a table)
                stock = dict(awtk_strings.load(os.path.join(langs, lang + '.bin'))).get(key)
                if stock is not None: kv[key] = stock
    out = []
    path = os.path.join(work, RAW, DIALOG)
    report = []
    old, new, _ = edit_ui(path, lambda root: edit(root, ttf, texts, report))
    out.append(f'{os.path.relpath(path, work)}: {len(old)} -> {len(new)} bytes')
    out += [f'  {r}' for r in report]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    a = ap.parse_args()
    clone_workdir(a.src, a.out)
    for line in apply(a.out): print('pulldown:', line)


if __name__ == '__main__': main()
