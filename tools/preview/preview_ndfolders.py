#!/usr/bin/env python3
"""Mock-up of the Subsonic Folders browser (patch/ndfolders.c, docs/modules/subsonic.md "Folders"): the Subsonic root with its new Folders row, then the folder levels drawn as the local Folders page
(tools/preview/preview_folders.py, patch/folders.c: the glass navbar, the large title, the Play / Shuffle pills when the level holds songs, 52 px rows painted by the page, the 40 px covers
of its --covers look) with three differences: the root level is an A-Z index (section letters and the rail, as the Artists page), a directory row shows its coverArt picture when the entry has one
(else the folder glyph), a song row carries the source rows' marks (downloaded disc, download ring, DSD tag; patch/libsrc.c ls_marks_draw) before its "..." (the track sheet); the navbar is Back and Now Playing only. Names are the Navidrome demo server's
(getMusicFolders / getIndexes / getMusicDirectory); the covers are stand-in swatches. Approximate, not AWTK.

  preview_ndfolders.py WORKDIR OUTDIR

WORKDIR is a built tree (work/mod-release). Writes nd-folders-*.png (320 x 450) and nd-folders-sheet.png to OUTDIR: the Subsonic root, the Folders index, an artist level, an album level, the album
scrolled, the loading frame.
"""
import argparse, os, sys, json, zlib
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview_icons as PI, preview_songs as PS, preview_folders as PF, preview_ndroot as PN
import mod_icons, pod_ui

O, F = PS.O, PF.F
W, WIN, NAV = PS.W, PS.WIN, PS.NAV
ROW_H, TEXT_X, TEXT_END, ICON_X, ICON, GAP = PF.ROW_H, F['FO_TEXT_X'], F['FO_TEXT_END'], F['FO_ICON_X'], F['FO_ICON'], 6   # GAP: LS_MK_GAP
INSET = O['SG_RAIL_INSET']
PROBE = '/tmp/nd-folders-probe'   # the saved responses (the sample data below is their names)

# The demo server's names, from the saved responses: getIndexes (an artist: name, whether the entry has a coverArt), the artist directory, the album directory (title, seconds).
INDEXES = [('#', [('2 Mello', 1)]), ('B', [('Back On Earth', 1), ('Binaerpilot', 1), ('Brad Sucks', 1), ('Brock Berrigan', 1)]), ('C', [('Carter Vail', 1), ('Chillhop Music', 1), ('CrumbSnatchers', 1)]),
           ('D', [('Deflone', 0), ('Diablo Swing Orchestra', 1)]), ('F', [('Forget the Whale', 1), ('Front 242', 1)]), ('J', [('Jahzzar', 1)]), ('K', [('The Knife', 1), ('Konstentyn', 0)]),
           ('M', [('Maya Filipič', 1)]), ('N', [('Natasha Beller', 0), ('The New Deal', 1), ('Nine Inch Nails', 1)]), ('P', [('Philanthrope', 1), ('The Polish Ambassador', 1), ('pornophonique', 1)]),
           ('T', [('Tony Petersen', 1)]), ('U', [('Ugress', 1)]), ('V', [('Various Artists', 0), ('VOODOOCUTS', 1)])]
SONGS = ['Intro', 'Public Chrono Announcement (Jay-Z vs. Chrono Trigger Mashup)', 'An Encore in Time (Jay-Z vs. Chrono Trigger Mashup)', 'Ignorant Scene (Jay-Z vs. Chrono Trigger Mashup)',
         'What More Can I Sing (Jay-Z vs. Chrono Trigger Mashup)', 'Masamune Problems (Jay-Z vs. Chrono Trigger Mashup)', 'Say Hello to the Black Omen (Jay-Z vs. Chrono Trigger Mashup)',
         'Dirt in the Palace (Jay-Z vs. Chrono Trigger Mashup)', 'Wind Cry (Orchestra - Jay-Z vs. Chrono Trigger Mashup)', 'Marle, Lucca, Schala (Jay-Z vs. Chrono Trigger Mashup)',
         "Gato's In Love (Jay-Z vs. Chrono Trigger Mashup)", 'Outro']
MARKS = {1: ('done',), 3: (('ring', 5),), 4: ('dsd',), 8: ('done', 'dsd')}   # song index -> marks (the downloaded disc, a ring at step 5 of 12, the DSD tag; the demo server has no DSD: an example)


def check_probe():
    """The names above are the saved responses' (a cheap guard that the sample stays the real data when the probe files are there)."""
    p = os.path.join(PROBE, 'getIndexes.json')
    if not os.path.exists(p): return
    ix = json.load(open(p))['subsonic-response']['indexes']['index']
    assert [(i['name'], [(a['name'], 'coverArt' in a) for a in i['artist']]) for i in ix] == [(l, [(n, bool(c)) for n, c in v]) for l, v in INDEXES], 'INDEXES drifted from getIndexes.json'
    d = json.load(open(os.path.join(PROBE, 'dir-album.json')))['subsonic-response']['directory']['child']
    assert [c['title'] for c in d] == SONGS, 'SONGS drifted from dir-album.json'


def swatch_rgb(name):
    """A stand-in cover colour per name (stable)."""
    h = zlib.crc32(name.encode())
    return tuple(0x2A + (h >> s & 0x3F) for s in (0, 8, 16))


def atlas():
    return Image.open(os.path.join(mod_icons.PNG, 'pc_atlas.png')).convert('RGBA')


def marks_w(marks):
    w = 0
    for m in marks: w += (GAP if w else 0) + {'done': O['PA_BADGE_PX'], 'ring': O['PA_DL_PX'], 'dsd': O['PA_DSD_W']}[m if isinstance(m, str) else m[0]]
    return w


def draw_marks(im, at, marks, x, ymid):
    """patch/libsrc.c ls_marks_draw: the disc, the ring (step k), the DSD tag, LS_MK_GAP apart, from x, in a PA_DSD_H high cell centred on ymid."""
    top = ymid - O['PA_DSD_H'] // 2
    for m in marks:
        if m == 'done':
            im.alpha_composite(at.crop((O['PA_BADGE_X'], O['PA_DOTS_Y'], O['PA_BADGE_X'] + 12, O['PA_DOTS_Y'] + 12)), (x, top + 1)); x += 12 + GAP
        elif m == 'dsd':
            im.alpha_composite(at.crop((O['PA_DSD_X'], O['PA_DSD_Y'], O['PA_DSD_X'] + O['PA_DSD_W'], O['PA_DSD_Y'] + O['PA_DSD_H'])), (x, top)); x += O['PA_DSD_W'] + GAP
        else:
            n = O['PA_DL_PX']
            for k in (m[1], O['PA_DL_STOP']):   # the step, the stop square over it (a running download)
                cx, cy = O['PA_DL_X'] + k % O['PA_DL_COLS'] * n, O['PA_DL_Y'] + k // O['PA_DL_COLS'] * n
                im.alpha_composite(at.crop((cx, cy, cx + n, cy + n)), (x, ymid - n // 2))
            x += n + GAP


def content(s, title, items, index=False):
    """The list as one tall image. items: ('hdr', letter) | ('dir', name, has_cover) | ('song', title, marks). A level with a song has the pills (first row at SG_TOP), else the large title alone
    (FO_TOP_PLAIN; the index level starts at SG_TITLE_H as the Artists page does). index: the rail is shown, so the row's right edge (text end, chevron) moves left by SG_RAIL_INSET."""
    songs = any(i[0] == 'song' for i in items)
    top = O['SG_TOP'] if songs else O['SG_TITLE_H'] if index else F['FO_TOP_PLAIN']
    inset = INSET if index else 0
    y, rows, heads = top, [], []
    for it in items:
        if it[0] == 'hdr': heads.append((it[1], y)); y += O['SG_HDR_H']
        else: rows.append((y, it)); y += ROW_H
    end = y + F['FO_END']
    im = Image.new('RGBA', (W, max(end, WIN - NAV)), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    s.text(im, O['SG_TITLE_X'], O['SG_TITLE_H'] / 2, PS.fit(s, title, 32, O['SG_TITLE_W']), 32)
    if songs:
        for i, (label, g) in enumerate((('Play', 'sg_play'), ('Shuffle', 'sg_shuffle'))): PS.pill(s, im, (O['SG_PILL_X0'], O['SG_PILL_X1'])[i], O['SG_PILL_Y'], PS.tr(s, label), s.img(g), PS.PILL_RGB)
    for letter, hy in heads: PS.header(s, im, letter, hy)
    at, dots = atlas(), PS.dots(s)
    for ry, it in rows:
        kind, name = it[0], it[1]
        d.rectangle((TEXT_X, ry + ROW_H - 1, O['LIST_HAIR_END'] - inset - 1, ry + ROW_H - 1), fill=PS.HAIR)
        if kind == 'dir' and it[2]: im.alpha_composite(PF.cover_swatch(swatch_rgb(name)), (F['FO_COVER_X'], ry + F['FO_COVER_Y']))   # the 40 px cover, 4 px corners (the Folders page's covers look)
        else: im.alpha_composite(s.img('pod_ic_folders' if kind == 'dir' else 'fo_ic_file'), (ICON_X, ry + F['FO_ICON_Y']))
        tend, ymid = TEXT_END - inset, ry + F['FO_TEXT_Y'] + O['LIST_TITLE_H'] // 2
        if kind == 'dir': PF.chevron(im, F['FO_CHEV_X'] - inset, ry + (ROW_H - 1 - 16) // 2)
        else:   # a song: its "..." (the shared track sheet; patch/rowmenu.c) ends the row, the text and the marks end before it
            right = O['RM_MORE_RIGHT'] - inset
            im.alpha_composite(dots, (PS.dots_x(right, inset > 0), ry + (ROW_H - 1 - O['RM_DOTS_PX']) // 2))
            tend = PS.dots_x(right, inset > 0) + O['RM_INK_X'] - O['RM_INK_GAP']   # RM_INK_GAP before the glyph's ink (rowmenu_text_end)
            g = marks_w(it[2])
            if g: draw_marks(im, at, it[2], tend - g, ymid); tend -= g + GAP
        s.text(im, TEXT_X, ymid, s.clip(name, pod_ui.LIST_TITLE_PX, tend - TEXT_X), pod_ui.LIST_TITLE_PX)
    return im, end, heads


def page(s, title, items, scroll=0, index=False, root=False, loading=False):
    if loading: tall, end, heads = Image.new('RGBA', (W, WIN), (0, 0, 0, 255)), WIN, []; s.text(tall, O['SG_TITLE_X'], O['SG_TITLE_H'] / 2, PS.fit(s, title, 32, O['SG_TITLE_W']), 32)
    else: tall, end, heads = content(s, title, items, index)
    im = Image.new('RGBA', (W, WIN), (0, 0, 0, 255))
    scroll = max(0, min(scroll, end - (WIN - NAV)))
    im.alpha_composite(tall.crop((0, scroll, W, min(tall.height, scroll + WIN - NAV))), (0, NAV))
    if loading:   # ls_spin: one spinner centred in the room under the kept large title (nothing else; the navbar stays)
        im.alpha_composite(s.img('wf_spin2'), ((W - 14) // 2, pod_ui.room_y(14, NAV + O['SG_TITLE_H'])))
    ImageDraw.Draw(im).rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0)); PS.glass(s, im, 'ah_nav_back', 7, 44); PS.glass(s, im, 'ah_nav_np', 260, 60)   # no "..." on any level: Back and Now Playing's disc (tools/pod_nd.py build_folders)
    if scroll > O['SG_COLLAPSE']: s.text(im, O['NAV_TITLE_X'], 25, PS.fit(s, title, PI.title_px(s.tree), 260 - O['NAV_TITLE_X']), PI.title_px(s.tree))   # the small title once the large one has gone (to Now Playing's disc at 260)
    if index: PS.rail(s, im, [h for h, _ in heads], None, WIN - NAV)
    if scroll > 0:
        fade = Image.new('RGBA', (W, 20), (0, 0, 0, 0)); fd = ImageDraw.Draw(fade)
        for y in range(20): fd.rectangle((0, y, W, y), fill=(0, 0, 0, int(160 * (1 - y / 20))))
        im.alpha_composite(fade, (0, NAV))
    return im


def ndroot(s):
    """The Subsonic root: the built asset already has the Folders row after Playlists (tools/pod_nd.py ROWS)."""
    return PN.page(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('outdir')
    a = ap.parse_args()
    check_probe()
    s = PI.Side(a.workdir, True)
    os.makedirs(a.outdir, exist_ok=True)
    folders = PS.tr(s, 'Folders')
    index = [it for letter, artists in INDEXES for it in [('hdr', letter)] + [('dir', n, bool(c)) for n, c in artists]]
    songs = [('song', t, MARKS.get(i, ())) for i, t in enumerate(SONGS)]
    panels = [('nd-folders-root', 'Subsonic root: the Folders row', ndroot(s)),
              ('nd-folders-index', 'Folders: one music folder, the index', page(s, folders, index, index=True, root=True)),
              ('nd-folders-artist', 'An artist: album folders', page(s, '2 Mello', [('dir', 'Chrono Jigga', True)])),
              ('nd-folders-album', 'An album: songs, marks', page(s, 'Chrono Jigga', songs)),
              ('nd-folders-album-scrolled', 'The album scrolled', page(s, 'Chrono Jigga', songs, scroll=150)),
              ('nd-folders-loading', 'Loading (ls_spin)', page(s, '2 Mello', [], loading=True))]
    for name, _, im in panels: im.convert('RGB').save(os.path.join(a.outdir, name + '.png'))
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, WIN + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (_, title, im) in enumerate(panels):
        x = pad + i * (W + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    PI.save_compact(sheet, os.path.join(a.outdir, 'nd-folders-sheet.png'))
    print('wrote', len(panels), 'panels and the sheet to', a.outdir)


if __name__ == '__main__':
    main()
