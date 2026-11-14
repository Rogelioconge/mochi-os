#!/usr/bin/env python3
"""The Audiobooks page's layout model (patch/bkpage.c, docs/modules/audiobooks.md "The page"): the BK_* numbers of patch/books.h, the Book header's wrapped title and the blocks'
tops, the rows' places, and the grey lines' words (English). test/pod/bkpage.py checks the payload against it and tools/preview_books.py draws from it, so the preview, the tests and
the device share one set of numbers.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_ui, pod_wrap

O = pod_ui.OFFSETS
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ' · '                                   # the " · " between the two halves of a line
PX = {name: px for name, px, _, _ in pod_ui.BK_STYLES}   # the header's text styles' sizes: label_bk_title 22 ...
SPEEDS = ('1×', '1.25×', '1.5×', '2×')        # the sheet's Playback Speed values, in the order of playspeed_mode


def _numbers():
    out = {}
    text = open(os.path.join(ROOT, 'patch', 'books.h')).read().replace('\\\n', ' ')
    for k, v in re.findall(r'#define (BK_\w+) ([0-9()* x]+?)\s*(?:/\*.*)?$', text, re.M):
        try: out[k] = eval(v, {}, {})   # noqa: S307 (this repo's own header: plain numbers and a product)
        except Exception: pass   # noqa: S110
    return out


BK = _numbers()
ROW_H = O['PC_ROW_H']


def btn_x(): return (BK['BK_W'] - BK['BK_PLAY_W']) // 2   # the capsule stands alone, centred (the Show page's Latest Episode pill, the preview's capsule)


def library(n, cont=False, all=False):
    """The Library level (patch/bkpage.c bk_lib_layout), the Podcasts Shows level's order: the large title, Continue Listening (cont: a book is in progress), the header Books and the first PS_SHOW_MAX books, the See All row when
    there are more, PP_SEC_GAP of air, the header Discover and the LibriVox row. Content height h, the top of book row i, the blocks' tops (shelf, head_books, all_row, head_disc, lv_row: 0 for a block that is not there), the rows
    shown. No book: no Books header (Podcasts has no Shows header with no show), the Discover header and row stay. all: the See All page, the complete list from the top."""
    if all: return dict(h=n * ROW_H + BK['BK_BOTTOM'], row=lambda i: i * ROW_H, shelf=0, head_books=0, all_row=0, head_disc=0, lv_row=0, shown=n, list=0)
    y = BK['BK_TOP']
    shelf = head_books = 0
    if cont: shelf, y = y, y + O['PP_HEAD_PITCH'] + O['PP_SHELF_PITCH_Y'] + O['PP_SEC_GAP']
    if n: head_books, y = y, y + O['PP_HEAD_PITCH']
    top, shown = y, min(n, O['PS_SHOW_MAX'])
    y += shown * ROW_H
    all_row = 0
    if n > O['PS_SHOW_MAX']: all_row, y = y, y + O['PS_MORE_H']
    if n: y += O['PP_SEC_GAP']
    head_disc, y = y, y + O['PP_HEAD_PITCH']
    return dict(h=y + ROW_H + O['PP_BOTTOM'] if n else O['GRID_VIEW_H'], row=lambda i: top + i * ROW_H, shelf=shelf, head_books=head_books, all_row=all_row, head_disc=head_disc, lv_row=y, shown=shown, list=top)


def librivox(n, want=False):
    """The LibriVox level with n rows (patch/bkfind.c): want False, the Discover-like level (the large title PP_TITLE_H, the grey line Public domain audiobooks at line_y, the section header Popular at pop_y, the rows from BK_LV_POP_TOP);
    want True, the search level (no large title, the Podcasts search field at PQ_FIELD_Y, the rows from PQ_TOP). No rows: the status line's room (the view), its top hint_y."""
    top = O['PQ_TOP'] if want else BK['BK_LV_POP_TOP']
    return dict(h=top + n * ROW_H + (O['PQ_BOTTOM'] if want else BK['BK_BOTTOM']) if n else O['GRID_VIEW_H'], row=lambda i: top + i * ROW_H, top=top, field_y=O['PQ_FIELD_Y'], line_y=BK['BK_LV_LINE_Y'], pop_y=BK['BK_LV_POP_Y'],
                title_h=O['PP_TITLE_H'], hint_y=O['PQ_TOP'] if want else BK['BK_LV_POP_Y'])


def book(font, title, n, extra=0):
    """The Book level of a book titled `title` with n parts: the title wrapped (font: pod_show.Font), the blocks' tops (content y from the list's top), the content height. extra: grey lines above the
    one (the preview's author line, at y_sub - BK_SUB_H)."""
    lines = pod_wrap.wrap_font(font, title, PX['label_bk_title'], BK['BK_NAME_W'], BK['BK_NAME_LINES']) if title else []
    y = BK['BK_ART_Y'] + O['PS_ART'] + BK['BK_NAME_GAP']
    d = dict(lines=lines, y_name=y)
    y += len(lines) * BK['BK_NAME_PITCH']
    d['collapse'] = y - BK['BK_COLLAPSE_BACK']
    y += BK['BK_SUB_GAP'] + extra * BK['BK_SUB_H']
    d['y_sub'] = y
    y += BK['BK_SUB_H'] + BK['BK_BTN_GAP']
    d['y_btn'] = y
    y += BK['BK_BTN_H'] + BK['BK_LIST_GAP']
    d['y_list'] = y
    d['h'] = y + n * ROW_H + (BK['BK_BOTTOM'] if n else 0)
    d['row'] = lambda i: d['y_list'] + i * ROW_H
    return d


def pct(permille): return f'{min(permille // 10, 100)}%'


def lib_sub(state, permille, cur, parts):
    """The reading progress, the one wording of every line (state 0 not started, 1 in progress, 2 finished): "Part 14 of 41 · 33%", "42%" for one file, "Finished", "Not started · 12 parts" ("Not started" for one file); "" for no part."""
    if not parts: return ''
    if state == 2: return 'Finished'
    if state == 1: return (f'Part {cur + 1} of {parts}' + SEP if parts > 1 else '') + pct(permille)
    return 'Not started' + (SEP + f'{parts} parts' if parts > 1 else '')


def kb_text(kb):
    if kb >= 10 << 20: return f'{(kb + 524288) >> 20} GB'
    if kb >= 1048576:
        t = (kb + 52428) // 104858
        return f'{t // 10}.{t % 10} GB'
    return f'{(kb + 1023) >> 10 if kb else 0} MB'


def book_sub(state, permille, cur, parts):
    """The Book header's grey line: the reading progress, as the Library's."""
    return lib_sub(state, permille, cur, parts)


def part_sub(state, pos, length, kb, man=None):
    """A part's grey line: Played, "12m left" or, not played, its size; man = (secs, bytes) of the manifest's row of a LibriVox part: the same "19m · 9 MB" the part said before it landed."""
    if state == 2: return 'Played'
    if state == 1 and length > pos: return left_text(length - pos)
    if man and (man[0] or man[1]): return line_text(0, man[0], man[1])
    return kb_text(kb)


def len_text(secs):
    """A length, Podcasts' "48m" (pc_len_text: minutes rounded up)."""
    return f'{(secs + 59) // 60}m'


def total_len_text(secs):
    """A whole book's running time: len_text under an hour, else hours and minutes ("18h 28m", "2h" on the hour); bkfind.c bf_total_len."""
    m = (secs + 59) // 60
    if m < 60: return len_text(secs)
    return f'{m // 60}h {m % 60}m' if m % 60 else f'{m // 60}h'


def left_text(secs):
    """The time left, Podcasts' "35m left" (pc_left_text)."""
    return f'{(secs + 59) // 60}m left'


def size_text(nbytes):
    """The size of a file or book from its bytes (KB rounded up, then kb_text)."""
    return kb_text(nbytes // 1024 + (1 if nbytes % 1024 else 0))


def line_text(parts, secs, nbytes):
    """The grey line of a preview (the whole book: parts, running time, size) or of one part (parts 0): the pieces that are known, joined by a middle dot."""
    out = []
    if parts > 1: out.append(f'{parts} parts')
    if secs: out.append(total_len_text(secs) if parts else len_text(secs))
    if nbytes: out.append(size_text(nbytes))
    return SEP.join(out)


def preview(font, title, author, n, oncard=False):
    """The Preview level of a LibriVox book: the Book level's header with the author's grey line above the totals' line and a capsule alone; y_auth is the author line's top, y_tot the totals' line's. oncard: a folder of the book is on the card with parts
    missing, so a third grey line (y_card, the last) says how many parts are there."""
    d = book(font, title, n, (1 if author else 0) + (1 if oncard else 0))
    d['y_tot'] = d['y_sub'] - (BK['BK_SUB_H'] if oncard else 0)
    d['y_auth'] = d['y_tot'] - BK['BK_SUB_H']
    d['y_card'] = d['y_sub'] if oncard else None
    d['x_btn'] = (BK['BK_W'] - BK['BK_PLAY_W']) // 2
    return d


def card_line(done, total):
    """The preview's third grey line: the parts of the book that are on the card."""
    return f'{done} of {total} parts downloaded'


def miss_sub(secs, nbytes):
    """The grey line of a manifest part that is not on the card (its time and size, as the preview's rows)."""
    return line_text(0, secs, nbytes)


def fetch_sub(got=0, total=0, wait=0):
    """The grey line of the part being fetched, Podcasts' In Progress words: the percent, "12 MB" while its length is unknown, Waiting while the job sleeps before a retry."""
    if wait: return 'Waiting'
    if total: return f'{min(got * 100 // total, 100)}%'
    return f'{got >> 20} MB' if got >> 20 else 'Downloading'


def failed_sub(word):
    """The grey line of the part the last try failed on (and the header's line of a book with parts on the card): Podcasts' "Failed: <why>"."""
    return f'Failed: {word}'


def dl_head(kind, part=0, total=0, wait=0, present=0, failed=None):
    """The header's grey line of a book with parts on the card and parts to come: the job on this book ('run': part is 0-based, total the manifest's parts), why it stopped, or how many parts are there."""
    if kind == 'run': return ('Waiting' if wait else 'Downloading') + SEP + f'Part {part + 1} of {total}'
    if kind == 'queued': return 'Waiting' + SEP + f'{present} of {total} parts downloaded'
    if failed: return failed_sub(failed)
    return f'{present} of {total} parts downloaded'


def ring(kind, got=0, total=0, wait=0, steps=12):
    """The download ring of a row whose job runs (libsrc's ls_ring_step: the arc is the percent in `steps` steps rounded to the nearest, step 0 for an unknown size or while it waits to retry; the mark over it is the stop square, the arrow while it waits); None when the row is not downloading."""
    if kind == 'queued': return (0, 'arrow')   # a book waiting in the queue: the ring at step 0 with the arrow, as a queued episode has it
    if kind != 'run': return None
    if wait or not total: return (0, 'arrow' if wait else 'stop')
    p = min(got * 100 // total, 100)
    return (min((p * steps + 50) // 100, steps - 1), 'stop')


def hdr_word(nparts, running, failed):
    """The header capsule of a LibriVox book with parts to come: Play's words are play_word's; with no part on the card yet it is the download's own button (Pause while it downloads or waits in the queue, Retry after a failure, else Resume)."""
    return None if nparts else 'Pause' if running else 'Retry' if failed else 'Resume'


def dl_lib_sub(kind, part, total):
    """The Library line of a book whose manifest names `total` parts: while the job runs on the book the part it is on (part 0-based), after the ring that says Downloading (the row's text ends at the chevron and
    "Downloading · Part 13 of 37" does not fit in 204 px); else how many parts are on the card (`part`)."""
    if kind == 'queued': return 'Waiting'
    if kind == 'idle': return f'{part} of {total} parts downloaded'
    return f'Part {part + 1} of {total}'


def play_word(state):
    return 'Play Again' if state == 2 else 'Resume' if state == 1 else 'Play'
