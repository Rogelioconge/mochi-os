#!/usr/bin/env python3
"""Preview of the Audiobooks page (patch/bkpage.c, patch/bkfind.c, docs/modules/audiobooks.md "The page" and "LibriVox"): the Library level (the LibriVox row, a row per book, the grey line in the three
states), the Book level (the header with the capsule Play / Resume / Play Again, a row per part, the playing wave on the part that plays), the empty hint and the toast of a book too long for one file, and the
LibriVox levels: the catalog (Popular, a search, the status lines, a row that is Not available) and a book's Preview (the header with its Download capsule over the parts). Every frame is a 320 x 480 device
frame: the 30 px status bar and the 450 px window.

  uv run python -I tools/preview/preview_books.py WORKDIR OUTDIR

Writes OUTDIR/books.png (the Library and the Book level in each state), OUTDIR/books-states.png (the hint, the toast, a long title, the played and unplayed rows) and OUTDIR/books-librivox.png (the LibriVox
and Preview levels) and OUTDIR/books-download.png (a LibriVox book's rows, ring and header in each state of its download, the Library's lines).

WORKDIR is a built tree (work/mod-release): the font (the stb model: advance + 1 px a glyph, tools/pod_show.py Font), the glass navbar pieces and the Lucide glyphs come from it and from
tools/mod_icons.py. The geometry is tools/pod_books.py's, which parses patch/books.h, so the preview, the tests and the device share one set of numbers. Covers are synthetic stand-ins.
Neutral white and grey (no accent). Not pixel-exact AWTK.
"""
import argparse, os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import preview_icons as PI
import preview_podcasts_revamp as R
import preview_songs as PS
import mod_icons as M
import pod_books
import pod_show
from stb_raster import _paste

W, WIN, NAV = R.W, R.WIN, R.NAV
O, BK = R.O, pod_books.BK
WHITE, GREY, DIM = R.WHITE, R.GREY, R.DIMT
ROW = O['PC_ROW_H']
FOLD = (0x22, 0x22, 0x22, 255)
FONT = None


class Book:
    def __init__(self, title, kind, parts, kb, state, permille=0, cur=0, played=(), left=None):
        self.title, self.kind, self.parts, self.kb, self.state, self.permille, self.cur, self.played, self.left = title, kind, parts, kb, state, permille, cur, played, left
        self.cover = None
        self.ring = None   # the Library row of a book that downloads: the ring's fraction before its grey line


def books(s):
    """Sample books: (title, cover kind, parts, KB, state, permille, current part, played parts, minutes left in the current one)."""
    data = [Book('Dune', 'deep', 41, 1_300_000, 1, 330, 13, set(range(13)), 22), Book('The Hobbit', 'brief', 12, 300_000, 0), Book('Meditations', 'minute', 1, 48_000, 1, 420, 0, (), 74),
            Book('Project Hail Mary', 'tech', 18, 520_000, 2, 1000, 18, set(range(18))), Book('Sapiens', 'night', 1, 410_000, 0)]
    for b in data: b.cover = R.synth_cover(s, b.kind)
    return data


def cover(b, size, r): return R.cover_img(b, size, r)


def title_px(s): return PI.title_px(s.tree)


def part_lines(b):
    """[(title, grey line, played, current)] for the parts a page shows: the first sixteen."""
    out = []
    for i in range(min(b.parts, 16)):
        played = i in b.played
        cur = b.state == 1 and i == b.cur
        sub = pod_books.part_sub(2 if played else 1 if cur and b.left else 0, 0 if not cur else 100 * 60 - b.left * 60, 100 * 60, 24_000 + 37 * i)
        out.append((f'Part {i + 1}', sub, played, cur))
    return out


def lv_row(s, im, y):
    """The Library's LibriVox row, under the books: the Podcasts Discover row's tile, the title, the grey line, the chevron, the hairline from the text."""
    _paste(im, R.IMGS[M.PC_SRCH_TILE], O['PP_DL_TILE_X'], y + O['PP_DL_TILE_Y'])
    s.text(im, O['PP_DL_TEXT_X'], y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, 'LibriVox', 20, WHITE)
    s.text(im, O['PP_DL_TEXT_X'], y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, PS.fit(s, 'Public domain audiobooks', 18, O['PP_DL_TEXT_W']), 18, GREY)
    _paste(im, M.pod_chevron(M.CARD_CHEVRON[3]), O['PP_DL_CHEV_X'], y + (ROW - 1 - M.POD_CHEV_H) // 2)
    R.hline(im, O['PP_DL_TEXT_X'], W, y + ROW - 1, FOLD)


def hint(s, im, top, text, busy=False):
    """An empty level's status line as patch/podcasts.c pg_paint_hint (tools/pod_show.py hint_layout): wrapped to the margins, centred as a block in the room under `top` and each line across the page; the spinner before it when busy."""
    lines = R.wrap(s, text, 20, W - 2 * O['PP_LINE_X'] - (O['PS_SPIN_PX'] + O['PS_SPIN_GAP'] if busy else 0), 4)[0]
    H = pod_show.hint_layout(top, [FONT.width(l_, 20) for l_ in lines], busy)
    for ln, (x, y) in zip(lines, H['lines']): s.text(im, x, y + O['PS_TITLE_PITCH'] / 2, ln, 20, GREY)
    if H['spin']: spinner(im, *H['spin'])
    return H


def shelf(s, im, y, b):
    """Continue Listening (patch/bkpage.c bk_paint_shelf, the Shows level's shelf with one item): the header, the cover with the play disc, the title and the percent."""
    s.text(im, O['PP_HEAD_X'], y + O['PP_HEAD_H'] / 2, 'Continue Listening', 20, WHITE)
    x, cy, ty, ly = pod_show.shelf_item(0, y)
    _paste(im, cover(b, O['PP_SHELF_ART'], O['PP_SHELF_R']), x, cy)
    _paste(im, R.sprite(O['PA_PLAYB_X'], O['PA_PLAYB_Y'], O['PA_PLAYB_PX'], O['PA_PLAYB_PX']), *pod_show.shelf_play(0, y))
    s.text(im, x, ty + O['PP_SHELF_TITLE_H'] / 2, PS.fit(s, b.title, 14, O['PP_SHELF_W']), 14, WHITE)
    s.text(im, x, ly + O['PP_SHELF_LEFT_H'] / 2, pod_books.pct(b.permille), 13, GREY)


def book_row(s, im, y, b, sub):
    """A Library row (the list painter's: the cover, the title and the grey line ending at x 278, the chevron at 288, the hairline from the text to 310); a book that downloads has the ring before its grey line."""
    _paste(im, cover(b, O['LIST_ART'], O['LIST_R']), O['LIST_ART_X'], y + O['LIST_ART_Y'])
    s.text(im, O['LIST_TEXT_X'], y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, PS.fit(s, b.title, 20, O['LIST_TEXT_W_CHEV']), 20, WHITE)
    x = O['LIST_TEXT_X']
    if b.ring is not None:   # the shared ring (14 px) and the stop square, then LS_MK_GAP (6) of air
        _paste(im, R.ring(O['PA_DL_PX'], b.ring, GREY), x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - O['PA_DL_PX'] // 2)
        x += O['PA_DL_PX'] + 6
    s.text(im, x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, PS.fit(s, sub, 18, O['LIST_TEXT_X'] + O['LIST_TEXT_W_CHEV'] - x), 18, GREY)
    _paste(im, M.pod_chevron(M.CARD_CHEVRON[3]), O['LIST_CHEV_X'], y + (ROW - 1 - M.POD_CHEV_H) // 2)
    R.hline(im, O['LIST_TEXT_X'], O['LIST_HAIR_END'], y + ROW - 1, FOLD)


def library(s, bs, scroll=0, hint_text=False, cont=None, all=False, tail=False):
    """The Library level in the Podcasts Shows level's order (patch/bkpage.c bk_lib_layout, tools/pod_books.py library): the large title, Continue Listening (cont: the book), the books (the first PS_SHOW_MAX, then
    See All), the LibriVox row. all: the See All page (the title in the navbar, no large title, the complete list). tail: scrolled to the end."""
    n = 0 if hint_text else len(bs)
    L = pod_books.library(n, cont=cont is not None, all=all)
    im = Image.new('RGBA', (W, max(L['h'], WIN - NAV)), (0, 0, 0, 255))
    if not all: s.text(im, O['SG_TITLE_X'], O['PP_TITLE_H'] / 2, 'Audiobooks', O['PP_TITLE_PX'], WHITE)
    if cont is not None: shelf(s, im, L['shelf'], cont)
    if L['head_books']: s.text(im, O['PP_SHOWS_X'], L['head_books'] + O['PP_HEAD_H'] / 2, 'Books', 20, WHITE)   # (the Shows header's x)
    if L['head_disc']: s.text(im, O['PP_SHOWS_X'], L['head_disc'] + O['PP_HEAD_H'] / 2, 'Discover', 20, WHITE)
    for i, b in enumerate(bs[:L['shown']] if not hint_text else []):
        sub = getattr(b, 'sub', None) or pod_books.lib_sub(b.state, b.permille, b.cur, b.parts)
        book_row(s, im, L['row'](i), b, sub)
    if L['all_row']: s.text(im, O['PP_SHOWS_X'], L['all_row'] + O['PS_MORE_H'] / 2, f'See All ({len(bs)})', 20, WHITE)
    if L['lv_row']: lv_row(s, im, L['lv_row'])
    if hint_text: hint(s, im, L['lv_row'] + ROW, 'No audiobooks. Copy a folder for each book into Audiobooks on the card.')
    if tail: scroll = max(0, L['h'] - (WIN - NAV))
    return window_of(s, im, scroll, 'Audiobooks' if all or scroll >= O['SG_COLLAPSE'] else None)


def book_page(s, b, scroll=0, title=None, man=None, sheet=None, playing=None):
    """The Book level of b: the capsule alone, centred (the speed is a row of the "..." sheet; sheet: its rows, R.bottom_sheet's). man: a LibriVox book with parts to come, {'rows': [(title, grey line, played, current (unused: no row mark), ring)]; playing: the row the player is on (the wave), 'line': the header's grey line,
    'cap': the capsule's word}: a row for every part the manifest names, the ring (pod_books.ring: step, mark) before the grey line of the part being fetched."""
    rows = man['rows'] if man else [r + (None,) for r in part_lines(b)]
    H = pod_books.book(FONT, title or b.title, len(rows))
    im = Image.new('RGBA', (W, H['h']), (0, 0, 0, 255))
    _paste(im, cover(b, O['PS_ART'], O['PS_ART_R']), O['PS_ART_X'], BK['BK_ART_Y'])
    for k, ln in enumerate(H['lines']):
        if H['y_name'] + k * BK['BK_NAME_PITCH'] >= scroll: s.text(im, W // 2, H['y_name'] + k * BK['BK_NAME_PITCH'] + BK['BK_NAME_PITCH'] / 2, ln, 22, WHITE, 'm')   # (a text is drawn only wholly in view)
    line = man['line'] if man else pod_books.book_sub(b.state, b.permille, b.cur, b.parts) if b.parts else ''
    if H['y_sub'] >= scroll and line: s.text(im, W // 2, H['y_sub'] + BK['BK_SUB_H'] / 2, line, 15, GREY, 'm')
    word = man['cap'] if man else pod_books.play_word(b.state) if b.parts else None
    if word:
        px, by = pod_books.btn_x(), H['y_btn']
        R.rrect(im, px, by, BK['BK_PLAY_W'], BK['BK_BTN_H'], BK['BK_BTN_H'] // 2, WHITE + (255,))
        s.text(im, px + BK['BK_PLAY_W'] // 2, by + BK['BK_BTN_H'] / 2, word, 18, (0, 0, 0), 'm')
    for i, (t, sub, played, cur, rg) in enumerate(rows):
        y = H['row'](i)
        x = BK['BK_PART_X']
        s.text(im, x, y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, PS.fit(s, t, 20, BK['BK_PART_W']), 20, DIM if played else WHITE)
        if i == playing:   # the part the player is on: the album page's wave in the ring's slot (12 px, centred on the grey line), the grey line LS_MK_GAP (6) right of it
            _paste(im, M.ab_wave(), x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - O['AB_WAVE'] // 2)
            x += O['AB_WAVE'] + 6
        if rg:   # the shared download ring (14 px) before the grey line, which starts a ring and LS_MK_GAP (6) right
            _paste(im, R.ring(O['PA_DL_PX'], rg[0] / O['PA_DL_N'], GREY), x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - O['PA_DL_PX'] // 2)
            x += O['PA_DL_PX'] + 6
        s.text(im, x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, PS.fit(s, sub, 18, BK['BK_PART_X'] + BK['BK_PART_W'] - x), 18, GREY)
        R.hline(im, BK['BK_PART_X'], W, y + ROW - 1, FOLD)
    win = Image.new('RGBA', (W, WIN), (0, 0, 0, 255))
    win.alpha_composite(im.crop((0, scroll, W, scroll + WIN - NAV)), (0, NAV))
    collapsed = scroll >= H['collapse']
    if scroll:
        for y in range(20): _paste(win, Image.new('RGBA', (W, 1), (0, 0, 0, M.nb_fade_alpha(y, 20))), 0, NAV + y)
    ImageDraw.Draw(win).rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0, 255))
    if collapsed: s.text(win, O['NAV_TITLE_X'], 25, PS.fit(s, b.title, title_px(s), O['NAV_VIEW_X'] - O['NAV_TITLE_X'] - 4), title_px(s))
    PS.glass(s, win, 'ah_nav_back', 7, 44)
    R.capsule(s, win, 'more')   # the Book level's "..." (the sheet: Playback Speed, and for a LibriVox book Pause or Resume Download and Delete Book)
    fr = R.frame(s, win, None)
    if sheet: R.bottom_sheet(s, fr, sheet)
    return fr, H


# ---------------------------------------------------------------------------
# The LibriVox levels (patch/bkfind.c)
POPULAR = [('The Adventures of Sherlock Holmes', 'Sir Arthur Conan Doyle', 'deep'), ('Pride and Prejudice', 'Jane Austen', 'brief'), ("Alice's Adventures in Wonderland", 'Lewis Carroll', 'minute'),
           ('Short Poetry Collection 001', '', 'tech'), ('Adventures of Huckleberry Finn', 'Mark Twain', 'night'), ('The Odyssey (Butler translation)', 'Homer', 'headlines'),
           ('こころ', '夏目 漱石', 'deep')]
SEARCH = [('Twain Tales', 'Mark Twain', 'night'), ('Tom Sawyer', 'Mark Twain', 'tech')]


def window_of(s, im, scroll, small=None, find=False):
    """The content `im` scrolled by `scroll` under the navbar (Back, Now Playing, the small title once given), as a device frame. find: the LibriVox level's magnifier, the capsule's left cap (the Podcasts Discover level's)."""
    win = Image.new('RGBA', (W, WIN), (0, 0, 0, 255))
    win.alpha_composite(im.crop((0, scroll, W, scroll + WIN - NAV)), (0, NAV))
    if scroll:
        for y in range(20): _paste(win, Image.new('RGBA', (W, 1), (0, 0, 0, M.nb_fade_alpha(y, 20))), 0, NAV + y)
    ImageDraw.Draw(win).rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0, 255))
    if small: s.text(win, O['NAV_TITLE_X'], 25, PS.fit(s, small, title_px(s), O['NAV_VIEW_X'] - O['NAV_TITLE_X'] - 4), title_px(s))
    PS.glass(s, win, 'ah_nav_back', 7, 44)
    if find: PS.glass(s, win, 'pod_nav_search', O['NAV_VIEW_X']); PS.glass(s, win, 'ah_nav_play', 260, 60)
    else: R.capsule(s, win, 'none')
    return R.frame(s, win, None)


def spinner(im, x, y, px=O['PS_SPIN_PX']):
    """The Wi-Fi page's spinner as a grey arc (the payload's wf_spin frames)."""
    ImageDraw.Draw(im).arc((x, y, x + px - 1, y + px - 1), 30, 300, fill=(0x8E, 0x8E, 0x93, 255), width=2)


def field(s, im, text):
    """The search field (the Podcasts search level's look and place: PQ_FIELD_Y, under the navbar; the level has no large title)."""
    fx, fy = O['PQ_FIELD_X'], O['PQ_FIELD_Y']
    R.rrect(im, fx, fy, O['PQ_FIELD_W'], O['PQ_FIELD_H'], O['PQ_FIELD_R'], (0x1C, 0x1C, 0x1E, 255))
    _paste(im, s.img('qk_mag'), fx + O['PQ_MAG_X'], fy + (O['PQ_FIELD_H'] - O['PQ_MAG']) // 2)
    s.text(im, fx + O['PQ_TEXT_X'], fy + O['PQ_FIELD_H'] / 2, PS.fit(s, text, 18, O['PQ_TEXT_W']) if text else 'Search LibriVox', 18, WHITE if text else (0x8E, 0x8E, 0x93))
    if text: _paste(im, s.img('qk_clear'), fx + O['PQ_CLEAR_X'] + (O['PQ_CLEAR_W'] - O['PQ_CLEAR']) // 2, fy + (O['PQ_FIELD_H'] - O['PQ_CLEAR']) // 2)


def librivox_page(s, rows=(), text='', status=None, busy=False, dim=(), scroll=0, covers=True, search=False):
    """The LibriVox level (the Podcasts Discover level's look: the large title, the grey line Public domain audiobooks at the Shows level's refresh line, the section header Popular and the rows, or the status line in the room
    under them; the navbar's magnifier) or, search, the search level (the Podcasts search level's: no large title, the field under the navbar, the rows of the term, the status line under the field). rows: (title, author,
    cover kind); dim: row numbers that are Not available."""
    L = pod_books.librivox(len(rows), want=search)
    im = Image.new('RGBA', (W, max(L['h'], WIN - NAV)), (0, 0, 0, 255))
    if search: field(s, im, text)
    else:
        s.text(im, O['SG_TITLE_X'], O['PP_TITLE_H'] / 2, 'LibriVox', O['PP_TITLE_PX'], WHITE)
        s.text(im, O['PP_LINE_X'], L['line_y'] + O['PP_LINE_H'] / 2, 'Public domain audiobooks', 15, GREY)
        if rows: s.text(im, O['PP_SHOWS_X'], L['pop_y'] + O['PP_HEAD_H'] / 2, 'Popular', 20, WHITE)   # (a section header, as Books)
    for i, (title, author, kind) in enumerate(rows):
        y = L['row'](i)
        b = Book(title, kind, 1, 0, 0)
        b.cover = R.synth_cover(s, kind) if covers else None   # (None: the placeholder disc)
        _paste(im, cover(b, O['LIST_ART'], O['LIST_R']), O['LIST_ART_X'], y + O['LIST_ART_Y'])
        s.text(im, O['LIST_TEXT_X'], y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, PS.fit(s, title, 20, O['LIST_TEXT_W_CHEV']), 20, WHITE)
        if i in dim: s.text(im, O['LIST_TEXT_X'], y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, 'Not available', 18, GREY)
        elif author: s.text(im, O['LIST_TEXT_X'], y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, PS.fit(s, author, 18, O['LIST_TEXT_W_CHEV']), 18, GREY)
        if i not in dim: _paste(im, M.pod_chevron(M.CARD_CHEVRON[3]), O['LIST_CHEV_X'], y + (ROW - 1 - M.POD_CHEV_H) // 2)
        R.hline(im, O['LIST_TEXT_X'], O['LIST_HAIR_END'], y + ROW - 1, FOLD)
        if i in dim: _paste(im, Image.new('RGBA', (W, ROW - 1), (0, 0, 0, O['PQ_DIM'] >> 24)), 0, y)
    if status: hint(s, im, L['hint_y'], status, busy)
    return window_of(s, im, scroll, 'LibriVox' if search or scroll >= O['SG_COLLAPSE'] else None, find=not search)


def preview_page(s, title, author, parts, scroll=0, oncard=None):
    """The Preview level of a LibriVox book: the Book header with the author's line, the totals' line and the Download capsule alone, then the parts as plain rows. parts: (title, seconds, bytes)."""
    n = len(parts)
    H = pod_books.preview(FONT, title, author, n, oncard=bool(oncard))
    im = Image.new('RGBA', (W, H['h']), (0, 0, 0, 255))
    b = Book(title, 'brief', n, 0, 0)
    b.cover = R.synth_cover(s, 'brief')
    _paste(im, cover(b, O['PS_ART'], O['PS_ART_R']), O['PS_ART_X'], BK['BK_ART_Y'])
    for k, ln in enumerate(H['lines']): s.text(im, W // 2, H['y_name'] + k * BK['BK_NAME_PITCH'] + BK['BK_NAME_PITCH'] / 2, ln, 22, WHITE, 'm')
    if author: s.text(im, W // 2, H['y_auth'] + BK['BK_SUB_H'] / 2, author, 15, GREY, 'm')
    secs, size = sum(p[1] for p in parts), sum(p[2] for p in parts)
    s.text(im, W // 2, H['y_tot'] + BK['BK_SUB_H'] / 2, pod_books.line_text(n, secs, size), 15, GREY, 'm')
    if oncard: s.text(im, W // 2, H['y_card'] + BK['BK_SUB_H'] / 2, pod_books.card_line(*oncard), 15, GREY, 'm')
    R.rrect(im, H['x_btn'], H['y_btn'], BK['BK_PLAY_W'], BK['BK_BTN_H'], BK['BK_BTN_H'] // 2, WHITE + (255,))
    s.text(im, H['x_btn'] + BK['BK_PLAY_W'] // 2, H['y_btn'] + BK['BK_BTN_H'] / 2, 'Open Book' if oncard else 'Download', 18, (0, 0, 0), 'm')
    for i, (t, sec, nbytes) in enumerate(parts):
        y = H['row'](i)
        s.text(im, BK['BK_PART_X'], y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, PS.fit(s, t, 20, BK['BK_PART_W']), 20, WHITE)
        s.text(im, BK['BK_PART_X'], y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, PS.fit(s, pod_books.line_text(0, sec, nbytes), 18, BK['BK_PART_W']), 18, GREY)
        R.hline(im, BK['BK_PART_X'], W, y + ROW - 1, FOLD)
    return window_of(s, im, scroll, title if scroll >= H['collapse'] else None), H


def manifest_rows(n, got, fetching=None, failed=None, fetch=None, secs=1130, nbytes=9_000_000):
    """The Book level's rows of a LibriVox book of n manifest parts, `got` of them on the card (the shared model's words): the part being fetched (`fetching`, with its (got, total, wait) in `fetch`) says how far it is and has the ring, the one
    the last try failed on (`failed`: the word) says why, the others their time and size; a part on the card is an ordinary row."""
    out = []
    for i in range(n):
        t = f'Chapter {i + 1:02}'
        if i < got: out.append((t, pod_books.part_sub(0, 0, 0, nbytes // 1024, man=(secs, nbytes)), False, False, None))
        elif i == fetching: out.append((t, pod_books.fetch_sub(*fetch), False, False, pod_books.ring('run', *fetch)))
        elif failed and i == got: out.append((t, pod_books.failed_sub(failed), False, False, None))
        else: out.append((t, pod_books.miss_sub(secs, nbytes), False, False, None))
    return out


def download_frames(s):
    """The Book level of a LibriVox book while it downloads and when it stops, and the Library's lines of such books (patch/bkpage.c, the shared model's words)."""
    fresh = Book('Moby Dick', 'night', 0, 0, 0)
    fresh.cover = R.synth_cover(s, 'night')
    part = Book('Pride and Prejudice', 'brief', 12, 110_000, 0)
    part.cover = R.synth_cover(s, 'brief')
    tot = pod_books.line_text(37, 37 * 1130, 37 * 9_000_000)
    f1 = book_page(s, fresh, man=dict(rows=manifest_rows(37, 0, 0, fetch=(0, 0)), line=tot, cap='Pause'))
    f2 = book_page(s, fresh, man=dict(rows=manifest_rows(37, 0, 0, fetch=(4_000_000, 9_000_000)), line=tot, cap='Pause'))
    f3 = book_page(s, fresh, man=dict(rows=manifest_rows(37, 0), line=tot, cap='Resume'))
    f4 = book_page(s, fresh, man=dict(rows=manifest_rows(37, 0, failed='Server error'), line=tot, cap='Retry'))
    sc = pod_books.book(FONT, part.title, 37)['row'](10) - 6
    f5 = book_page(s, part, scroll=sc, man=dict(rows=manifest_rows(37, 12, 12, fetch=(3_100_000, 9_000_000)), line=pod_books.dl_head('run', 12, 37), cap='Play'))
    f6 = book_page(s, part, scroll=sc, man=dict(rows=manifest_rows(37, 12, 12, fetch=(0, 0, 1)), line=pod_books.dl_head('run', 12, 37, wait=1), cap='Play'))
    f7 = book_page(s, part, scroll=sc, man=dict(rows=manifest_rows(37, 12), line=pod_books.dl_head('idle', total=37, present=12), cap='Play'))
    f8 = book_page(s, part, scroll=sc, man=dict(rows=manifest_rows(37, 12, failed="Can't connect"), line=pod_books.dl_head('idle', total=37, present=12, failed="Can't connect"), cap='Play'))
    f9 = book_page(s, part, man=dict(rows=manifest_rows(37, 12), line=pod_books.dl_head('queued', present=12, total=37), cap='Play'))
    f10 = book_page(s, fresh, man=dict(rows=manifest_rows(37, 0), line=tot, cap='Pause'))
    lib = [Book('Moby Dick', 'night', 0, 0, 0), Book('Pride and Prejudice', 'brief', 12, 0, 0), Book('Emma', 'tech', 9, 0, 0), Book('Dune', 'deep', 41, 0, 0, 330, 13), Book('Persuasion', 'minute', 9, 0, 0)]
    for b in lib: b.cover = R.synth_cover(s, b.kind)
    lib[0].sub, lib[1].sub, lib[2].sub, lib[4].sub = pod_books.dl_lib_sub('run', 3, 135), pod_books.dl_lib_sub('run', 12, 37), pod_books.dl_lib_sub('queued', 9, 20), pod_books.dl_lib_sub('idle', 9, 20)
    lib[0].ring, lib[1].ring, lib[2].ring = pod_books.ring('run', 0, 0)[0] / O['PA_DL_N'], pod_books.ring('run', 3, 9)[0] / O['PA_DL_N'], pod_books.ring('queued')[0] / O['PA_DL_N']
    lib[0].title = 'Moby Dick'
    return [('Download just started: every part of the manifest\na row, the capsule is Pause, the first part has the ring', f1[0]), ('the percent of the part, the ring follows', f2[0]), ('paused: the capsule says Resume', f3[0]),
            ('the first part failed: Retry, the reason\non the part', f4[0]), ('12 parts on the card, the 13th downloading:\nPlay, the header says what it does', f5[0]), ('waiting to retry', f6[0]),
            ('paused: how many parts are there', f7[0]), ('a failure: the reason in the header and on the part', f8[0]), ('queued behind another book: "Waiting ·" and the\nparts downloaded, the capsule stays Play', f9[0]),
            ('queued, no part yet: the totals in hours,\nthe capsule Pause, no ring on a part', f10[0]), ('Library: ring and part of the running book,\nWaiting + ring for a queued book', library(s, sorted(lib, key=lambda b: b.title)))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('outdir')
    a = ap.parse_args()
    global FONT
    FONT = R.FONT = pod_show.Font(pod_show.font_path(a.workdir))
    R.IMGS = M.podcast_images()
    s = PI.Side(a.workdir, True, 'en_US')
    PI.ANN = ImageFont.truetype(pod_show.font_path(a.workdir), 13)   # (the captions: the device font has the multiplication sign of 1.5×; Pillow's default font draws a box for it)
    os.makedirs(a.outdir, exist_ok=True)
    bs = books(s)
    dune, hobbit, med, hail, sapiens = [next(b for b in bs if b.title.startswith(t)) for t in ('Dune', 'The Hobbit', 'Meditations', 'Project', 'Sapiens')]
    sorted_books = sorted(bs, key=lambda b: (b.title[4:] if b.title.lower().startswith('the ') else b.title).lower())   # (a leading "The " aside, as the model sorts)
    f1 = book_page(s, dune)
    f2 = book_page(s, dune, scroll=f1[1]['row'](dune.cur - 2) - 6)
    f2p = book_page(s, dune, scroll=f1[1]['row'](dune.cur - 2) - 6, playing=dune.cur)
    f3 = book_page(s, hobbit)
    f4 = book_page(s, hail)
    f5 = book_page(s, med)
    many = [Book(f'{t} {i + 1:02}', k, 3 + i % 10, 100_000, 0) for i, (t, k) in enumerate(zip(['Anthology'] * 16 + ['Chronicle'] * 5, ['deep', 'brief', 'minute', 'tech', 'night'] * 5))]
    for b in many: b.cover = R.synth_cover(s, b.kind)
    LM = pod_books.library(len(many) + 1, cont=True)
    R.assemble([('Library, the Shows level\'s order: the title,\nContinue Listening, the books, LibriVox', library(s, sorted_books, cont=dune)), ('the same scrolled to the end: the LibriVox row\nunder the books (the Discover row\'s look)', library(s, sorted_books, cont=dune, tail=True)),
                ('Library with no book in progress:\nno Continue Listening', library(s, [b for b in sorted_books if b.title != 'Dune' and b.state != 1])),
                ('22 books: the first 20, then See All (22),\nthe LibriVox row after it', library(s, [dune] + many, cont=dune, scroll=LM['all_row'] - 200)), ('See All: the complete list, the title in the navbar,\nno large title, no LibriVox row', library(s, [dune] + many, all=True, scroll=300)),
                ('Book, in progress: Resume; "22m left" says which\npart (no mark on the row)', f1[0]), ('the same scrolled: played parts grey,\n"22m left", the sizes', f2[0]), ('the player is on that part: the playing wave\nbefore its grey line', f2p[0]),
                ('Book, not started: Play, "Not started · 12 parts"', f3[0]), ('Book, every part played: Play Again', f4[0]), ('Book of one file: the percent, no part', f5[0])], 3, os.path.join(a.outdir, 'books.png'))
    R.assemble(download_frames(s), 3, os.path.join(a.outdir, 'books-download.png'))
    sh = lambda *rows: [('pc_ic_speed', 'Playback Speed', '1.5×', WHITE), *rows]
    pause, resume, delete = ('pod_ic_pause', 'Pause Download', '', WHITE), ('pod_ic_play', 'Resume Download', '', WHITE), ('pc_ic_trash', 'Delete Book', '', R.REDISH)
    own = book_page(s, dune, sheet=sh())[0]
    fresh = Book('Moby Dick', 'night', 0, 0, 0)
    fresh.cover = R.synth_cover(s, 'night')
    mrows = lambda *a_, **k: dict(rows=manifest_rows(37, *a_, **k), line=pod_books.line_text(37, 37 * 1130, 37 * 9_000_000), cap='Pause')
    dl_run = book_page(s, fresh, man=mrows(0, 0, fetch=(4_000_000, 9_000_000)), sheet=sh(pause, delete))[0]
    dl_idle = book_page(s, fresh, man=dict(mrows(0), cap='Resume'), sheet=sh(resume, delete))[0]
    R.assemble([('"..." of a book of your own: Playback Speed\nalone, the value 1.5×', own), ('a LibriVox book that downloads: Pause Download,\nDelete Book (red)', dl_run), ('paused or failed: Resume Download, Delete Book', dl_idle)], 3, os.path.join(a.outdir, 'books-sheet.png'))
    long_title = Book('The Lord of the Rings: The Fellowship of the Ring, Unabridged', 'headlines', 36, 900_000, 0)
    long_title.cover = R.synth_cover(s, 'headlines')
    f6 = book_page(s, long_title)
    f7 = book_page(s, long_title, scroll=f6[1]['collapse'] + 4)
    toast = R.toast_frame(f1[0], a.workdir, PS.fit(s, 'Too long. Split it into parts.', 18, 236))   # (the stock box shows its line 260 px wide and scrolls a longer one)
    R.assemble([('A long title: two lines, ellipsis', f6[0]), ('scrolled: the small title in the navbar', f7[0]), ('the empty hint under the LibriVox row', library(s, [], hint_text=True)), ('the MP4 guard\'s toast (the box scrolls\nthe whole sentence)', toast)], 4, os.path.join(a.outdir, 'books-states.png'))
    parts = [(f'Chapter {i + 1:02}', 1130 + 37 * i, 9_000_000 + 41_000 * i) for i in range(37)]
    pv, PH = preview_page(s, 'Pride and Prejudice', 'Jane Austen', parts)
    pv2, _ = preview_page(s, 'Pride and Prejudice', 'Jane Austen', parts, scroll=PH['y_list'] - 10)
    pv3, _ = preview_page(s, 'Short Poetry Collection 001', '', parts[:3])
    pv4, _ = preview_page(s, 'Pride and Prejudice', 'Jane Austen', parts, oncard=(12, 37))
    R.assemble([('LibriVox: the large title, the grey line,\nPopular, thumbnails, the magnifier', librivox_page(s, POPULAR)), ('scrolled: the small title in the navbar', librivox_page(s, POPULAR, scroll=120)),
                ('the magnifier opens the search level:\nan empty field, the keyboard opens', librivox_page(s, search=True)), ('a search: the text, the clear button, the rows', librivox_page(s, SEARCH, text='mark twain', search=True)),
                ('Loading... on LibriVox with the spinner', librivox_page(s, status='Loading…', busy=True)), ('a status: No Wi-Fi', librivox_page(s, status='No Wi-Fi')),
                ('a search with no result', librivox_page(s, text='zzzz', status='No results', search=True)),
                ('no thumbnails yet (placeholders), and a row\nthat is Not available (dimmed, no chevron)', librivox_page(s, POPULAR, dim=(1,), covers=False)), ('Preview: the header, Download, the parts', pv),
                ('the parts scrolled: plain rows', pv2), ('a book with no author: one grey line', pv3), ('the folder is on the card with parts missing:\na third line says how many, Open Book', pv4)], 6, os.path.join(a.outdir, 'books-librivox.png'))


if __name__ == '__main__': main()
