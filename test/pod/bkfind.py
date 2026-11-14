"""The Audiobooks page's LibriVox levels (patch/bkfind.c, docs/modules/audiobooks.md "LibriVox"): the Library's first row, the LibriVox level (the search field, Popular, the rows and their thumbnails, every
status, a search and clearing it, a book downloading beside the page, leaving while the worker runs), the Preview level (the header against the shared model, the parts, Not available, a failure's toast, Back at
the offset it was left at), Download (the folder, the manifest, the job, the Book level of a book of no part yet), Open, a refusal after the folder was made, and every new text in the 13 languages. The compiled
payload runs under Unicorn; the card is a dict of paths and libcurl is scripted."""
import json, os, re, subprocess, sys
from urllib.parse import unquote
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools'))

BKP, BKN, BKD = sibling('bkpage'), sibling('bknet'), sibling('bkdl')
PCP, BKM, PCN = BKP.PCP, BKP.BKM, BKN.PCN
import pod_books, pod_i18n, pod_show, pod_ui   # noqa: E402

BR, BK, ROW = BKP.BR, BKP.BK, BKP.ROW
POP, SRCH, LINE_Y, POP_Y, FIELD_Y = BK['BK_LV_POP_TOP'], O['PQ_TOP'], BK['BK_LV_LINE_Y'], BK['BK_LV_POP_Y'], O['PQ_FIELD_Y']   # Popular's rows, a search's rows, the grey line under the large title, Popular's line, the field (the Podcasts search level's numbers)
HOST = BKN.HOST
ID = 'pride_and_prejudice_librivox'
DL = '/mnt/mmc/.m1plus/audiobooks/search'
SEARCH_DOCS = [{'identifier': 'twain_tales_librivox', 'title': 'Twain Tales', 'creator': 'Mark Twain', 'runtime': '3:00:00'},
               {'identifier': 'tom_sawyer_librivox', 'title': 'Tom Sawyer', 'creator': ['Mark Twain', 'Someone'], 'runtime': '6:30:00'}]
CANCEL = PSYMS['pn'] + 20 + 12 * O['PC_MAX_SHOWS'] + 12


class FM(PCN.NM, BKM.BM):
    """The card machine with the worker's calls and the model's records, under the page."""


def popular_rows():
    """[(title, author)] of the sample popular answer as the page words them (the author of an array is its first, none is empty), the row with a bad identifier skipped."""
    out = []
    for d in json.loads(BKN.SEARCH_RAW)['response']['docs']:
        if '/' in d['identifier']: continue
        a = d.get('creator', '')
        out.append((d['title'], a[0] if isinstance(a, list) else a))
    return out


def archive(reqs, search=None, files=BKN.FILES_RAW, img=lambda u: {'body': BKN.THUMB, 'chunk': 5500}, meta=None):
    """The scripted Internet Archive: the popular answer, a search answer (search: the docs, a reply dict or a function), the files answer (meta overrides it), pictures."""
    def site(url, o):
        reqs.append(url)
        if 'advancedsearch' in url:
            if ('AND' in url.split('&')[0]) and search is not None:
                return search(url, o) if callable(search) else {'body': json.dumps({'response': {'docs': search}}).encode()} if isinstance(search, list) else search
            return {'body': BKN.SEARCH_RAW}
        if '/metadata/' in url: return meta(url, o) if meta else {'body': files, 'chunk': 16384}
        return img(url)
    return site


def machine(site=None, ring=None, cardf=None, ca=True, **kw):
    """The page machine over FM, not opened: the card of test/pod/bkpage.py, the worker's directories, the real font's widths, the keyboard page not openable (the test calls what it would)."""
    m = PCP.page_machine(lambda mm: (BKP.card(mm, ring), cardf(mm) if cardf else None), FM)
    for n in BKP.WIDGETS: m.widget(n)
    m.widgets['books_scrollview'] = m.sv
    m.cont = BKP.has_cont(ring)
    m.px = {m.widgets[n]: px for n, px, *_ in pod_ui.BK_STYLES}
    m.px.update({m.widgets[n]: px for n, px in (('label_row_title', 21), ('label_row_sub', 18), ('ps_text', 18), ('ps_hint', 18))})
    m.setword(m.widgets['ps_text'] + 8, O['PQ_TEXT_W']); m.setword(m.widgets['ps_hint'] + 8, O['PQ_TEXT_W'])
    m.dirs.update({BR, '/mnt/mmc/.m1plus'})
    if ca: m.present.add(PCN.CA)
    m.curl_site = site or (lambda url, o: {'rc': 6})
    for k, v in kw.items(): setattr(m, k, v)
    m.jinit()
    m.windows['m1plus_keyboard'] = 0
    for i in range(8): m.images[f'wf_spin{i}'] = (14, 14, bytes((0x55, 0x55, 0x55, 255)) * 196)
    return m


def opened(site=None, **kw):
    m = machine(site, **kw)
    assert m.call(PSYMS['books_open'], count=200000000) == 0
    return m


def work(m):
    """The worker the page started runs to its end."""
    th, m.thread = m.thread, None
    assert th, 'a worker was started'
    PCN.work(m, th)


def tick(m): return BKP.tick(m)
def visible(m, n): return m.props.get((m.widgets[n], 'visible'), 1)
def toasts(m): return BKP.toasts(m)
def texts(m, off=0): return BKP.texts_of(m, off)
def style(m, s, off=0): return [t for t, r, st in texts(m, off) if st == s]
def active(m): return m.call(PSYMS['bd_active'], count=2000000)


def lv_at(m):
    """(content y of the Library's LibriVox row, the offset of the frame that drew it): the row is under the books, so frames are scrolled 100 px apart until its title is drawn (a text is drawn only wholly in view)."""
    for off in range(0, 6000, 100):
        t = texts(m, off)
        for x, r, s in t:
            if s == 'label_row_title' and x == 'LibriVox' and ('Public domain audiobooks', 'label_row_sub') in [(x_, s_) for x_, r_, s_ in t]: return r[1] - O['LIST_TITLE_Y'] + off, off
    raise AssertionError('no LibriVox row on the Library level')


def enter(m, off=None):
    """A tap on the Library's LibriVox row (the Library scrolled to off, or to where the row is drawn)."""
    m.thread = None
    y, o = lv_at(m)
    BKP.tap(m, 150, y + 20, off=o if off is None else off)


def settle(m, rounds=4):
    """The loader runs until it has nothing to decode; the pictures the worker fetched are known to the decoder."""
    for p in list(m.fs):
        if p.startswith(DL) and p.endswith(('.jpg', '.png')): m.images.setdefault(f'file://{p}', (180, 180, bytes((90, 120, 200, 255)) * 180 * 180))
    for _ in range(rounds): m.call(PSYMS['bk_on_load'], a0=0, count=40000000)


def popular(m):
    """Enter LibriVox, the worker answers and fetches the pictures, the tick takes them in."""
    enter(m); work(m); tick(m)


def top(m): return SRCH if field(m)[5] else POP   # where the rows start: under the field (a search) or under Popular's grey line


def rows(m, off=None):
    """[(title, grey line)] of the rows drawn in a frame (the grey line '' when there is none), top to bottom; the frame is scrolled until the first row is at the top."""
    off = top(m) if off is None else off
    t = {r[1]: x for x, r, s in texts(m, off) if s == 'label_row_title'}
    s = {r[1]: x for x, r, st in texts(m, off) if st == 'label_row_sub'}
    return [(t[y], next((v for k, v in s.items() if k - y == O['LIST_SUB_Y'] - O['LIST_TITLE_Y']), '')) for y in sorted(t)]


def same(shown, full):
    """A text as a row shows it: whole, or cut with an ellipsis."""
    return shown == full or (shown.endswith('…') and full.startswith(shown[:-1]))


def field(m):
    """(shown, moved to y, hint visible, text visible, clear visible, text) of the search field's widgets."""
    mv = [c[2:] for c in m.calls if c[0] == 'widget_move' and c[1] == m.widgets['ps_field']]
    return (m.props.get((m.widgets['ps_field'], 'visible'), 0), mv[-1] if mv else None, m.props.get((m.widgets['ps_hint'], 'visible'), 1), m.props.get((m.widgets['ps_text'], 'visible'), 0),
            m.props.get((m.widgets['ps_clear'], 'visible'), 0), m.wtext.get(m.widgets['ps_text'], ''))


def at_lv(m):
    """The LibriVox level (the Podcasts Discover level's look): the large title LibriVox, no field, the navbar's magnifier."""
    return visible(m, 'bk_big') == 1 and m.wtext.get(m.widgets['bk_big']) == 'LibriVox' and field(m)[0] == 0 and visible(m, 'btn_search') == 1


def at_srch(m):
    """The search level: no large title, the navbar's title LibriVox always, the field, no magnifier."""
    return visible(m, 'bk_big') == 0 and m.props.get((m.widgets['label_title'], 'visible'), 0) == 1 and m.wtext.get(m.widgets['label_title']) == 'LibriVox' and field(m)[0] == 1 and visible(m, 'btn_search') == 0


def to_search(m):
    """The navbar's magnifier on the LibriVox level: the search level, the keyboard asked for on the empty field."""
    m.calls = []; m.thread = None
    BKP.click(m, 'btn_search')
def at_library(m): return visible(m, 'bk_big') == 1 and m.wtext.get(m.widgets['bk_big']) == 'Audiobooks' and field(m)[0] == 0


def font(): return pod_show.Font(pod_show.font_path(WORK))


def files_info():
    """The fixture's parts as the model counts them, read from the JSON itself: (count, seconds, bytes)."""
    parts = [o for o in json.loads(BKN.FILES_RAW)['result'] if o.get('format') == '64Kbps MP3']
    secs = 0
    for o in parts:
        s = str(o.get('length', '0'))
        secs += sum(int(float(x)) * f for x, f in zip(reversed(s.split(':')), (1, 60, 3600))) if s else 0
    return len(parts), secs, sum(int(o.get('size', 0)) for o in parts)


def preview(m, row=1):
    """Popular is up; a tap on row `row`, the worker answers, the tick opens the Preview level."""
    m.thread = None
    BKP.tap(m, 150, POP + row * ROW + 20, off=POP)
    work(m); tick(m)


# ---------------------------------------------------------------------------
def library_tests(ctx):
    """The LibriVox row on the Library (with and without books), the tap that opens the level, the press, Back at the offset."""
    expect = ctx.expect
    for what, cardf in (('books', None), ('no books', lambda mm: [mm.fs.pop(p) for p in [q for q in mm.fs if q.startswith(BR)]] and [mm.dirs.discard(q) for q in list(mm.dirs) if q.startswith(BR + '/')])):
        m = opened(archive([]), cardf=cardf)
        y, off = lv_at(m)
        L = pod_books.library(0 if cardf else 5)
        got = [(x, s) for x, r, s in texts(m, off)]
        expect(('LibriVox', 'label_row_title') in got and ('Public domain audiobooks', 'label_row_sub') in got and ('Discover', 'label_ps_sech') in got and y == L['lv_row'], f'{what}: the row says LibriVox over the grey line "Public domain audiobooks", under the header Discover ({y})')
        bl, _, _, fills = PCP.paint(m, off)
        expect(any(b[2] == (O['PP_DL_TILE_X'], y - off + O['PP_DL_TILE_Y'], O['PA_TILE_PX'], O['PA_TILE_PX']) for b in bl) and (O['LIST_HAIR'], O['PP_DL_TEXT_X'], y - off + ROW - 1, 320 - O['PP_DL_TEXT_X'], 1) in fills,
               f'{what}: the Discover row\'s tile and the hairline from the text')
        m.setword(m.sv + PCP.SC_YOFF, off); m.setword(m.view + 4, -off & 0xffffffff)
        m.touch('down', 100, BKP.SCREEN_Y0 + y - off + 20, 1000, fn='bk_on_down')
        _, _, _, fills = PCP.paint(m, off)
        expect((O['LIST_PRESS'], 0, y - off, 320, ROW - 1) in fills, f'{what}: a pressed row is lit')
        m.touch('abort', 100, BKP.SCREEN_Y0 + y - off + 20, 1010, fn='bk_on_abort')
        enter(m)
        expect(at_lv(m), f'{what}: a tap opens the LibriVox level (the large title LibriVox, the navbar\'s magnifier, no field)')
    expect(visible(m, 'label_status') == 0 and field(m)[0] == 0, 'the empty hint is gone on the LibriVox level, and it has no field')
    # Back returns to the Library at the offset it was left at, and the field goes
    m = opened(archive([]))
    y, off = lv_at(m)
    enter(m)
    expect(at_lv(m) and m.props.get((m.sv, 'yoffset')) == 0, 'the LibriVox level opens at its top')
    BKP.click(m, 'btn_return')
    expect(at_library(m) and m.props.get((m.sv, 'yoffset')) == off and 'navigator_back' not in m.names() and m.props.get((m.sv, 'virtual_h')) == pod_books.library(5)['h'],
           'Back goes to the Library level, at the offset it was left at, and the page stays')
    BKP.click(m, 'btn_return')
    expect('navigator_back' in m.names(), 'Back from the Library leaves the page')
    # a page without the field's widgets has no LibriVox level: the row does nothing
    m = machine(archive([])); m.widgets.pop('ps_field')
    m.call(PSYMS['books_open'], count=200000000)
    enter(m)
    expect(not at_lv(m) and m.props.get((m.sv, 'virtual_h')) == pod_books.library(5)['h'], 'without the field\'s widgets the row opens nothing')


def collapse_tests(ctx):
    """The navbar's small title on the Library and LibriVox levels (m1_title_gone: SG_COLLAPSE, as the Podcasts Shows and Discover levels): hidden at the top, shown from the threshold, and right at once after a level change at a kept
    offset; the magnifier is on the LibriVox level only."""
    expect = ctx.expect
    C = O['SG_COLLAPSE']
    shown = lambda mm: mm.props.get((mm.widgets['label_title'], 'visible'), 0)
    name = lambda mm: mm.wtext.get(mm.widgets['label_title'])
    mag = lambda mm: mm.props.get((mm.widgets['btn_search'], 'visible'), 0)

    def scroll(mm, off):
        mm.setword(mm.sv + PCP.SC_YOFF, off); mm.call(PSYMS['bk_on_scroll'], a0=0, a1=0, count=4000000)
    m = opened(archive([]))
    expect(at_library(m) and shown(m) == 0 and not mag(m), 'the Library opens with the large title and no small one, no magnifier')
    scroll(m, C - 1)
    expect(shown(m) == 0, f'one pixel before the threshold ({C}): the navbar\'s title is still hidden')
    scroll(m, C)
    expect(shown(m) == 1 and name(m) == 'Audiobooks', 'at the threshold the large title is gone: the navbar shows Audiobooks')
    scroll(m, 0)
    expect(shown(m) == 0, 'back at the top it is hidden again')
    # a book opened at a kept offset: Back shows the small title at once, with no scroll event
    L = pod_books.library(5)
    m.thread = None
    BKP.tap(m, 150, L['row'](4) + 20, off=300)
    expect(not at_library(m) and name(m) == 'Zed' and shown(m) == 0, 'the Book level: its own title, hidden under the header')
    BKP.click(m, 'btn_return')
    expect(at_library(m) and m.props.get((m.sv, 'yoffset')) == 300 and shown(m) == 1 and name(m) == 'Audiobooks', 'Back from the book to the Library at 300: the small title is there at once')
    # the LibriVox level: the large title at the top, the small one from the threshold, the magnifier on this level only
    y, off = lv_at(m)
    enter(m)
    expect(at_lv(m) and shown(m) == 0 and name(m) == 'LibriVox' and mag(m) == 1 and m.props.get((m.sv, 'yoffset')) == 0, 'the LibriVox level opens at the top: the large title, no small one, the magnifier')
    work(m); tick(m)
    scroll(m, C - 1)
    expect(shown(m) == 0, 'LibriVox: still hidden before the threshold')
    scroll(m, C)
    expect(shown(m) == 1 and name(m) == 'LibriVox' and mag(m) == 1, 'LibriVox: shown from the threshold, the magnifier stays')
    scroll(m, 0); m.props[(m.sv, 'yoffset')] = 0
    # the search level and back at a kept offset below and above the threshold
    for kept, want in ((C - 10, 0), (C + 60, 1)):
        scroll(m, kept); m.props[(m.sv, 'yoffset')] = kept
        to_search(m)
        expect(at_srch(m) and shown(m) == 1 and not mag(m), f'the search level (left at {kept}): the navbar\'s title always, no magnifier')
        BKP.click(m, 'btn_return')
        expect(at_lv(m) and m.props.get((m.sv, 'yoffset')) == kept and shown(m) == want and mag(m) == 1, f'Back to the LibriVox level at {kept}: the small title is {"shown" if want else "hidden"} at once')
    # a preview from the LibriVox level at an offset past the threshold, and Back
    m.thread = None
    BKP.tap(m, 150, POP + 1 * ROW + 20, off=C + 60)
    work(m); tick(m)
    expect(m.wtext.get(m.widgets['label_title']) == 'Pride and Prejudice' and not mag(m), 'the Preview level: the book\'s title, no magnifier')
    BKP.click(m, 'btn_return')
    expect(at_lv(m) and m.props.get((m.sv, 'yoffset')) == C + 60 and shown(m) == 1 and name(m) == 'LibriVox', 'Back from the preview to LibriVox at its offset: the small title at once')
    BKP.click(m, 'btn_return')
    expect(at_library(m) and m.props.get((m.sv, 'yoffset')) == off >= C and shown(m) == 1 and name(m) == 'Audiobooks' and not mag(m), 'Back from LibriVox: the Library at its offset, the small title there, no magnifier')
    # the See All page has no large title: its title is always there
    m = opened(archive([]), cardf=BKP.more_books(16))
    L = pod_books.library(21)
    m.thread = None
    BKP.tap(m, 150, L['all_row'] + 20, off=L['all_row'] - 120)
    expect(shown(m) == 1 and name(m) == 'Audiobooks' and visible(m, 'bk_big') == 0, 'the See All page: the navbar\'s title always')


def popular_tests(ctx):
    """Entering: Loading... and the field, then Popular and its rows (thumbnails: the placeholder first, the pictures as they arrive), the offsets."""
    expect = ctx.expect
    reqs = []
    m = opened(archive(reqs))
    enter(m)
    calls = list(m.calls)
    f = field(m)
    expect(f[0] == 0 and not any(c[0] == 'widget_move' and c[1] == m.widgets['ps_field'] for c in calls) and m.props.get((m.widgets['bk_big'], 'visible')) == 1 and m.wtext.get(m.widgets['bk_big']) == 'LibriVox',
           f'the LibriVox level has no field and the large title LibriVox ({f})')
    expect(m.props.get((m.widgets['label_title'], 'visible'), 0) == 0 and m.wtext.get(m.widgets['label_title']) == 'LibriVox' and visible(m, 'btn_search') == 1 and visible(m, 'btn_more') == 0
           and m.props.get((m.widgets['btn_backtoplayer'], 'style:normal:icon')) == 'ah_nav_play',
           'at the top the navbar\'s small title is hidden (the large one shows) and the magnifier is the capsule\'s left cap beside Now Playing')
    expect(style(m, 'label_bk_hint') == ['Loading…'] and ('timer_add', PSYMS['bf_spin_tick'], O['PS_SPIN_MS']) in calls and m.props.get((m.sv, 'virtual_h')) == pod_books.librivox(0)['h'],
           f'the status line says Loading... with the spinner turning while the worker has not answered ({style(m, "label_bk_hint")})')
    expect(reqs == [] and m.thread is not None, 'the worker is started, nothing is fetched yet')
    work(m); tick(m)
    want = popular_rows()
    expect(reqs[0] == BKN.POPULAR and len(reqs) == 1 + len(want), f'the popular address, then a picture a row ({len(reqs)} requests)')
    expect(m.props.get((m.sv, 'virtual_h')) == pod_books.librivox(len(want))['h'], f'the content is the title, the field, Popular and {len(want)} rows ({pod_books.librivox(len(want))["h"]} px)')
    t = texts(m)
    expect([(x, r) for x, r, s in t if s == 'label_bk_meta'] == [('Public domain audiobooks', (O['PP_LINE_X'], LINE_Y, 320 - 2 * O['PP_LINE_X'], O['PP_LINE_H']))] and [(x, r) for x, r, s in t if s == 'label_ps_sech'] == [('Popular', (O['PP_SHOWS_X'], POP_Y, 320 - 2 * O['PP_SHOWS_X'], O['PP_HEAD_H']))] and POP == POP_Y + O['PP_HEAD_PITCH'] and LINE_Y == O['PP_LINE_Y'] and not style(m, 'label_bk_hint'),
           'under the large title one grey line, Public domain audiobooks, where the Shows level has its refresh line (PP_LINE_X, PP_LINE_Y), then the section header Popular in the Library\'s Books header\'s style and place (label_ps_sech at PP_SHOWS_X, PP_HEAD_PITCH over the rows), no status line')
    got = rows(m)
    first = [r for x, r, st in texts(m, POP) if st == 'label_row_title']
    expect(first and first[0][1] == O['LIST_TITLE_Y'] and POP_Y + O['PP_HEAD_H'] <= POP, f'Popular\'s rows start under its header ({first[:1]})')
    expect(len(got) >= 5 and all(same(a, w[0]) and same(b, w[1]) for (a, b), w in zip(got, want)), f'a row per book: the title and the author in grey ({got})')
    expect(got[3][1] == '' and want[3][1] == '', 'a book with no author has no grey line')
    _, _, _, fills = PCP.paint(m, top(m))
    expect(all(any(f_[0] == O['LIST_HAIR'] and f_[2] == r * ROW + ROW - 1 for f_ in fills) for r in range(5)) and not [f_ for f_ in fills if f_[0] == O['PQ_DIM']], 'a hairline under each row, no row dimmed')
    # thumbnails: the placeholder first, one a tick, the picture shows
    bl, _, _, _ = PCP.paint(m, top(m))
    before = [b[0] for b in bl if tuple(b[2][2:]) == (O['LIST_ART'], O['LIST_ART'])]
    settle(m, 12)
    loads = [u for u in m.loads if u.startswith(f'file://{DL}/p')]
    bl, _, _, _ = PCP.paint(m, top(m))
    after = [b[0] for b in bl if tuple(b[2][2:]) == (O['LIST_ART'], O['LIST_ART'])]
    expect(len(loads) == len(want) and len(set(before)) == 1 and before[0] not in after, f'every row starts with the placeholder disc, the pictures come off the paint path ({len(loads)} decoded)')
    expect(not any(c[0] == 'widget_load_image' for c in m.calls), 'painting decodes nothing')
    # Back and in again: the held list needs no request; the offset is the level's own
    m.setword(m.sv + PCP.SC_YOFF, 90)
    BKP.click(m, 'btn_return')
    expect(at_library(m), 'Back: the Library')
    reqs.clear(); enter(m); tick(m)
    expect(not reqs and m.thread is None and len(rows(m)) >= 5 and same(rows(m)[0][0], want[0][0]) and m.props.get((m.sv, 'yoffset')) == 0, 'the popular list is held: entering again asks for nothing and shows it at once, at the top')


def status_tests(ctx):
    """Every status in the page's words as Discover has them."""
    expect = ctx.expect
    cases = [('no Wi-Fi', dict(wifi=-1), None, 'No Wi-Fi'), ('a clock never set', dict(wall=1700000000), None, 'Set the date first'), ('no CA bundle', dict(ca=False), None, 'Certificates missing'),
             ('no card', dict(card_mounted=False), None, 'Storage unavailable'),
             ('no connection', {}, lambda u, o: {'rc': 6}, "Can't connect"), ('a time-out', {}, lambda u, o: {'rc': 28}, "Can't connect"), ('a certificate error', {}, lambda u, o: {'rc': 60}, 'Certificate problem'),
             ('HTTP 503', {}, lambda u, o: {'rc': 22, 'code': 503}, 'Server error'), ('an HTML page', {}, lambda u, o: {'body': b'<html>blocked</html>'}, 'Server error'),
             ('an empty list', {}, lambda u, o: {'body': json.dumps({'response': {'docs': []}}).encode()}, 'No results')]
    for label, kw, site, word in cases:
        m = opened(site or archive([]), **kw)
        enter(m)
        if m.thread: work(m)
        tick(m)
        h = style(m, 'label_bk_hint')
        expect(h == [word] and not rows(m) and style(m, 'label_bk_meta') == ['Public domain audiobooks'] and m.props.get((m.sv, 'virtual_h')) == pod_books.librivox(0)['h'], f'{label}: the status line says "{word}", no rows, no Popular ({h})')
    # a failed query is not held: Back and in again asks again
    reqs = []
    m = opened(lambda u, o: reqs.append(u) or {'rc': 6})
    enter(m); work(m); tick(m)
    BKP.click(m, 'btn_return'); reqs.clear(); m.curl_site = archive(reqs)
    enter(m); work(m); tick(m)
    expect(reqs and reqs[0] == BKN.POPULAR and len(rows(m)) >= 5 and not style(m, 'label_bk_hint'), 'after a failure the next entry asks again and shows the rows')
    # the status line wraps and fits in every language
    m = opened(archive([]), wifi=-1)
    enter(m); tick(m)
    expect(style(m, 'label_bk_hint') == ['No Wi-Fi'] and not any(c[0] == 'timer_add' and c[1] == PSYMS['bf_spin_tick'] for c in m.calls), 'a failure has no spinner')
    # the Podcasts search level's status line: centred as a block in the room under the field, each line across the page
    r = [r for x, r, s in texts(m) if s == 'label_bk_hint']
    mid = (POP_Y + O['GRID_VIEW_H']) / 2
    expect(len(r) == 1 and abs(r[0][1] + r[0][3] / 2 - mid) <= 1 and 100 <= r[0][0] <= 150 and r[0][1] >= POP_Y,   # (the words start left of the middle by half their width: not at x 12)
           f'the status line is centred in the room under the grey lines ({r}, middle {mid})')
    m = opened(archive([]))
    enter(m)
    r = [r for x, r, s in texts(m) if s == 'label_bk_hint']
    expect(len(r) == 1 and 110 <= r[0][0] <= 160 and abs(r[0][1] + r[0][3] / 2 - mid) <= 1, f'a busy line: the spinner and the words centred together as one group ({r})')


def search_tests(ctx):
    """The navbar's magnifier opens the search level (the keyboard on the empty field), a term is searched, the rows replace nothing (the level starts empty), clearing empties it again; Back returns to Popular where it was."""
    expect = ctx.expect
    reqs = []
    m = opened(archive(reqs, search=SEARCH_DOCS))
    popular(m)
    reqs.clear()
    m.setword(m.sv + PCP.SC_YOFF, 90); m.props[(m.sv, 'yoffset')] = 90
    to_search(m)
    expect(at_srch(m) and ('window_open', 'm1plus_keyboard') in m.calls and m.props.get((m.sv, 'yoffset')) == 0, 'the magnifier opens the search level: no large title, the navbar\'s title, the field, and the keyboard on the empty field')
    f = field(m)
    expect(f[1] == (O['PQ_FIELD_X'], FIELD_Y) and f[2:] == (1, 0, 0, '') and ('widget_set_tr_text', m.widgets['ps_hint'], 'Search LibriVox') in m.calls and m.props.get((m.widgets['label_title'], 'visible')) == 1,
           f'the field at the Podcasts search level\'s place with its hint, no text, no clear button ({f})')
    expect(not rows(m) and not style(m, 'label_bk_hint') and not style(m, 'label_bk_meta') and not reqs and m.thread is None and m.props.get((m.sv, 'virtual_h')) == pod_books.librivox(0, want=True)['h'],
           'the search level starts empty: no rows, no status line, no Popular, no request')
    expect(m.props.get((m.widgets['btn_search'], 'visible')) == 0 and m.props.get((m.widgets['btn_backtoplayer'], 'style:normal:icon')) == 'ah_nav_np', 'the magnifier is gone on this level and Now Playing is the disc again')
    m.thread = None; m.calls = []
    BKP.tap(m, 150, FIELD_Y + 10, off=0)
    expect(('window_open', 'm1plus_keyboard') in m.calls, 'a tap on the field opens the keyboard page')
    m.thread = None; m.calls = []
    m.call(PSYMS['bf_done'], a0=m.cstr('mark twain'), count=40000000)
    expect(m.thread is not None and field(m)[2:] == (0, 1, 1, 'mark twain') and style(m, 'label_bk_hint') == ['Loading…'] and not rows(m), f'Search with a term: the worker starts, the field shows its text and the clear button, the status says Loading... ({field(m)})')
    work(m); tick(m)
    expect('advancedsearch' in reqs[0] and 'twain' in reqs[0] and 'AND' in reqs[0], f'the search request ({reqs[0][:120]})')
    got = rows(m)
    first = [r for x, r, st in texts(m, SRCH) if st == 'label_row_title']
    expect(first and first[0][1] == O['LIST_TITLE_Y'] and SRCH == O['PQ_TOP'] and not style(m, 'label_bk_meta', SRCH), f'after a search the rows start right under the field (the Podcasts search level\'s PQ_TOP {SRCH}): there is no blank label line ({first[:1]})')
    expect([(a, b) for a, b in got] == [('Twain Tales', 'Mark Twain'), ('Tom Sawyer', 'Mark Twain')] and not style(m, 'label_bk_meta') and m.props.get((m.sv, 'virtual_h')) == pod_books.librivox(2, want=True)['h'] and rows(m, SRCH) == got,
           f'the search\'s rows (an author array shows its first), no Popular line ({got})')
    settle(m)
    expect(len([u for u in m.loads if u.startswith(f'file://{DL}/s')]) == 2, 'their thumbnails arrive (s0, s1)')
    # a term with no answer: No results; the field keeps its text
    m.curl_site = archive(reqs, search=[])
    m.call(PSYMS['bf_done'], a0=m.cstr('zzzz'), count=40000000); work(m); tick(m)
    expect(style(m, 'label_bk_hint') == ['No results'] and not rows(m) and field(m)[5] == 'zzzz', 'a search with no result: "No results", the field keeps what was typed')
    m.curl_site = archive(reqs, search=lambda u, o: {'rc': 6})
    m.call(PSYMS['bf_done'], a0=m.cstr('bad'), count=40000000); work(m); tick(m)
    expect(style(m, 'label_bk_hint') == ["Can't connect"], 'a failed search says why')
    # the clear button: the text and the rows go, no request, the keyboard asked for on the empty field (Podcasts' search level has nothing under an empty field)
    reqs.clear(); m.calls = []; m.thread = None
    BKP.tap(m, O['PQ_FIELD_X'] + O['PQ_CLEAR_X'] + 10, FIELD_Y + 10, off=0)
    calls = list(m.calls)
    expect(field(m)[2:] == (1, 0, 0, '') and not reqs and m.thread is None and not rows(m) and not style(m, 'label_bk_meta') and not style(m, 'label_bk_hint') and ('window_open', 'm1plus_keyboard') in calls and at_srch(m),
           f'the clear button: the text and the button go, the level is empty again (no request), the keyboard opens ({field(m)})')
    # the keyboard's Back does nothing; an empty text is not a search; the keyboard's answer waits for the page to be in front
    reqs.clear(); m.thread = None
    m.call(PSYMS['bf_done'], a0=m.cstr(''), count=40000000)
    expect(not reqs and m.thread is None and not rows(m), 'an empty text searches nothing')
    BKP.fire(m, 'EVT_WINDOW_TO_BG')
    m.call(PSYMS['bf_done'], a0=m.cstr('twain'), count=40000000)
    expect(m.thread is None and not reqs, 'the keyboard\'s answer while the page is behind it waits')
    BKP.fire(m, 'EVT_WINDOW_TO_FG')
    expect(m.thread is not None and field(m)[5] == 'twain' and at_srch(m), 'back in front the term is searched')
    work(m); tick(m)
    # Back from the search level: Popular again at the offset it was left at, from the held list (no request), the field gone, the magnifier back
    reqs.clear(); m.thread = None
    BKP.click(m, 'btn_return')
    expect(at_lv(m) and not reqs and m.thread is None and m.props.get((m.sv, 'yoffset')) == 90 and style(m, 'label_bk_meta') == ['Public domain audiobooks'] and style(m, 'label_ps_sech') == ['Popular'] and len(rows(m, 90)) >= 1 and same(rows(m, POP)[0][0], popular_rows()[0][0]),
           f'Back from the search level returns to the LibriVox level at its offset, Popular from the held list ({m.props.get((m.sv, "yoffset"))})')
    expect(m.props.get((m.widgets['label_title'], 'visible')) == 1 and 'navigator_back' not in m.names(), 'the offset is past the large title: the small title is shown at once; the page stays')
    # Back and in again, the magnifier again: an empty field, nothing typed is kept
    BKP.click(m, 'btn_return'); enter(m); tick(m)
    to_search(m)
    expect(at_srch(m) and field(m)[2:] == (1, 0, 0, '') and not rows(m), 'the search level is empty again on the next visit')


def busy_tests(ctx):
    """A book downloads beside the page: the held Popular list shows, leaving the level leaves the job alone, a search runs beside the download (nothing gives way); the user's pause is final; bd_gen only grows."""
    expect = ctx.expect
    reqs = []
    m = opened(archive(reqs))
    popular(m); settle(m)
    preview(m, 1)
    BKP.tap(m, BK['BK_PLAY_W'] // 2 + (320 - BK['BK_PLAY_W']) // 2, pod_books.preview(font(), 'Pride and Prejudice', 'Jane Austen', 8)['y_btn'] + 20)   # Download
    key, bth = active(m), m.thread
    expect(key == pod_books.PC.pc_hash('audiobooks/Pride and Prejudice') if hasattr(pod_books, 'PC') else key != 0, f'the book job is running (key {key:#x})')
    BKP.click(m, 'btn_return')   # the Book level: Back to the Library
    reqs.clear(); m.calls = []; m.thread = None
    enter(m)
    expect(not reqs and len(rows(m)) >= 5 and 'Popular' in style(m, 'label_ps_sech') and not style(m, 'label_bk_hint'), 'the held Popular list shows while a book downloads: no request, no status')
    BKP.click(m, 'btn_return')
    expect(active(m) == key and m.word(CANCEL) == 0, 'leaving the level leaves the book job alone')
    # a search made meanwhile runs beside the book's download: nothing gives way, both threads are alive at once
    book_th = bth
    enter(m)
    to_search(m)
    m.call(PSYMS['bf_done'], a0=m.cstr('twain'), count=40000000)
    w = lambda n: m.call(PSYMS[n], count=2000000)
    tick(m)
    sth = m.thread
    expect(sth is not None and sth != book_th and sth[0] != PSYMS['bd_main'] and w('pn_job_busy') == 1 and active(m) == key and w('pn_dl_running') == 0 and w('pn_dl_waiting') == 0,
           'a search made while a book downloads starts at once: the job slot is busy and the book is still active, nothing waits or is asked to give way')
    m.thread = None
    PCN.work(m, sth); tick(m)
    expect(any('advancedsearch' in u and 'twain' in u for u in reqs) and len(rows(m)) >= 1 and not style(m, 'label_bk_hint') and active(m) == key and w('pn_job_busy') == 0,
           'the search answered beside the download: its rows show and the book job is still active')
    PCN.work(m, book_th)
    expect(active(m) == 0 and w('pn_dl_waiting') == 0 and m.thread is None, 'the book job ran to its end; nothing was started again')
    # a book is never held back from a start by a catalog job or a preview job: the user's own pause is final
    mb = machine(archive([]))
    BKN.preview(mb, ID)
    r, d = BKD.create(mb, ID, 'Pride', 'Austen')
    r2, th = BKD.start(mb, d, run=False)
    expect(r == 0 and r2 == 0 and th is not None and active(mb) != 0, 'a book was made and its job started')
    g0 = mb.call(PSYMS['bd_gen'], count=2000000)
    mb.call(PSYMS['bd_pause'], key_of_pause(mb), count=2000000)
    PCN.work(mb, th)
    mb.thread = None
    expect(active(mb) == 0 and mb.call(PSYMS['pn_dl_start'], count=1 << 30) == 0 and mb.thread is None, 'a pause of the user: nothing runs, nothing is started again')
    # the generation never goes back over a restart
    g1 = mb.call(PSYMS['bd_gen'], count=2000000)
    r3, th = BKD.start(mb, d, run=False)
    g2 = mb.call(PSYMS['bd_gen'], count=2000000)
    PCN.work(mb, th)
    g3 = mb.call(PSYMS['bd_gen'], count=2000000)
    expect(r3 == 0 and g0 < g1 < g2 < g3, f'bd_gen only grows across jobs ({g0}, {g1}, {g2}, {g3})')


def leave_tests(ctx):
    """Leaving the level cancels a catalog job of the page; the page closing cleans up; the preview takes the worker from the thumbnails."""
    expect = ctx.expect
    m = opened(archive([]))
    enter(m)
    expect(m.thread is not None and m.call(PSYMS['pn_job_busy'], count=2000000) == 1 and m.word(CANCEL) == 0, 'the catalog job runs')
    BKP.click(m, 'btn_return')
    expect(m.word(CANCEL) == 1 and at_library(m), 'Back from the LibriVox level cancels the running job and shows the Library')
    # another page's job (a Podcasts search) is never cancelled by leaving the level; a running book download is not touched either
    m = opened(archive([]))
    enter(m); work(m); tick(m)
    m.thread = None
    m.call(PSYMS['pn_search'], a0=m.cstr('x'), count=1 << 40)
    BKP.click(m, 'btn_return')
    expect(m.word(CANCEL) == 0 and at_library(m), 'Back from the LibriVox level leaves another page\'s job running')
    m = opened(archive([]))
    enter(m); work(m); tick(m)
    BKP.fire(m, 'EVT_DESTROY')
    expect(not [p for p in m.fs if p.startswith(f'{DL}/p')] and m.names().count('timer_remove') >= 2, 'the page closing removes the thumbnails and its timers')
    m = opened(archive([]))
    popular(m); settle(m)
    BKP.fire(m, 'EVT_WINDOW_TO_BG')
    expect(not any(c[0] == 'timer_add' and c[1] == PSYMS['bf_spin_tick'] for c in m.calls[-3:]) and m.names().count('timer_remove') >= 2, 'behind another page the timers go')
    BKP.fire(m, 'EVT_WINDOW_TO_FG')
    expect(at_lv(m) and len(rows(m)) >= 5, 'back in front: the level as it was')


def preview_tests(ctx):
    """A tap on a row: Loading... in its grey line, the header against the shared model, the parts, Not available, a failure's toast, Back at the offset."""
    expect = ctx.expect
    reqs = []
    m = opened(archive(reqs))
    popular(m); settle(m)
    n, secs, size = files_info()
    reqs.clear(); m.thread = None; m.calls = []
    m.setword(m.sv + PCP.SC_YOFF, 100)
    BKP.tap(m, 150, POP + 1 * ROW + 20, off=100)
    sub = [s for t, s in rows(m, 100) if t.startswith('Pride')]
    expect(sub == ['Loading…'] and m.thread is not None and not reqs, f'the tapped row\'s grey line reads Loading... while the parts are fetched ({sub})')
    BKP.tap(m, 150, POP + 2 * ROW + 20, off=100)
    expect(m.thread is not None and len([c for c in m.calls if c[0] == 'pthread_create']) <= 1, 'a second tap meanwhile starts nothing')
    work(m); tick(m)
    expect(reqs[0] == f'{HOST}/metadata/{ID}/files' and reqs[1] == f'{HOST}/services/img/{ID}', f'the files answer, then the picture ({reqs})')
    H = pod_books.preview(font(), 'Pride and Prejudice', 'Jane Austen', n)
    expect(m.props.get((m.sv, 'virtual_h')) == H['h'] and m.props.get((m.sv, 'yoffset')) == 0 and not field(m)[0] and visible(m, 'bk_big') == 0 and m.wtext.get(m.widgets['label_title']) == 'Pride and Prejudice',
           f'the Preview level: the header and {n} part rows ({H["h"]} px), the field and the large title gone, the small title the book\'s')
    t = texts(m)
    by = lambda s: [(x, r) for x, r, st in t if st == s]
    expect(by('label_bk_title') == [(l_, (BK['BK_NAME_X'], H['y_name'] + i * BK['BK_NAME_PITCH'], BK['BK_NAME_W'], BK['BK_NAME_PITCH'])) for i, l_ in enumerate(H['lines'])], f'the title in the header\'s place ({by("label_bk_title")})')
    line = pod_books.line_text(n, secs, size)
    expect(by('label_bk_sub') == [('Jane Austen', (BK['BK_NAME_X'], H['y_auth'], BK['BK_NAME_W'], BK['BK_SUB_H'])), (line, (BK['BK_NAME_X'], H['y_sub'], BK['BK_NAME_W'], BK['BK_SUB_H']))],
           f'the author, then "{line}" (the shared model\'s words): {by("label_bk_sub")}')
    expect(by('label_bk_btn') == [('Download', (H['x_btn'] + 8, H['y_btn'], BK['BK_PLAY_W'] - 16, BK['BK_BTN_H']))] and not by('label_bk_pill'), f'a white capsule alone: Download ({by("label_bk_btn")})')
    bl, _, _, fills = PCP.paint(m)
    white = [f_ for f_ in fills if f_[0] == 0xffffffff and H['y_btn'] <= f_[2] < H['y_btn'] + BK['BK_BTN_H']]
    expect(len(white) == BK['BK_BTN_H'] and max(f_[3] for f_ in white) == BK['BK_PLAY_W'] - 2 and min(f_[1] for f_ in white) >= H['x_btn'] - 1 and max(f_[1] + f_[3] for f_ in white) <= H['x_btn'] + BK['BK_PLAY_W'] + 1, 'the capsule is a white stadium, centred')
    expect(any(b[2][:2] == (O['PS_ART_X'], BK['BK_ART_Y']) and b[2][2:] == (O['PS_ART'], O['PS_ART']) for b in bl), 'the cover at the Show page\'s place and size (the placeholder first)')
    settle(m)
    expect(any(u == f'file://{DL}/preview.jpg' for u in m.loads), 'the cover picture is decoded from the preview file')
    # the parts: plain rows
    off = H['y_list']
    t = texts(m, off)
    parts = [(x, r[1]) for x, r, s in t if s == 'label_row_title']
    subs = [x for x, r, s in t if s == 'label_row_sub']
    got = BKN.part(m, 0), BKN.part(m, n - 1)
    expect(len(parts) >= 5 and parts[0][0] == got[0][1] and subs[0] == pod_books.line_text(0, got[0][2], got[0][3]) and parts[0][1] == O['LIST_TITLE_Y'], f'a part row: its title and "duration · size" ({parts[0]}, {subs[0]})')
    expect(all(any(c in ' ·' for c in s) or s for s in subs) and all(re.fullmatch(r'\d+m · \d+ MB', s) for s in subs), f'every part line has a running time and a size ({subs})')
    bl, _, _, fills = PCP.paint(m, off)
    expect(all((O['LIST_HAIR'], BK['BK_PART_X'], i * ROW + ROW - 1, 320 - BK['BK_PART_X'], 1) in fills for i in range(5)) and not [f_ for f_ in fills if f_[0] == O['LIST_PRESS']], 'a hairline from the text, no chevron')
    reqs.clear()
    BKP.tap(m, 150, H['row'](0) + 20)
    BKP.tap(m, 10, H['y_btn'] + 20)
    expect(m.props.get((m.sv, 'virtual_h')) == H['h'] and not reqs and not toasts(m), 'the parts take no tap, nor does the margin beside the capsule')
    # the small title shows once the header has gone
    m.setword(m.sv + PCP.SC_YOFF, H['collapse']); m.call(PSYMS['bk_on_scroll'], a0=0, a1=0, count=4000000)
    expect(m.props.get((m.widgets['label_title'], 'visible')) == 1, 'scrolled past the title: the navbar shows the small title')
    # Back: the LibriVox level at the offset it was left at, the rows as they were
    BKP.click(m, 'btn_return')
    expect(at_lv(m) and m.props.get((m.sv, 'yoffset')) == 100 and same(rows(m, 100)[0][0], popular_rows()[0][0]) and m.props.get((m.widgets['label_title'], 'visible'), 0) == 1, 'Back: the LibriVox level at its offset, with its rows')
    expect(sub == ['Loading…'] and [s for t_, s in rows(m, 100) if t_.startswith('Pride')] == ['Jane Austen'], 'the row\'s grey line is the author again')
    # the same preview again, then Back: Back from LibriVox is the Library
    BKP.click(m, 'btn_return')
    expect(at_library(m), 'Back from the LibriVox level: the Library')
    # a new question while a preview was asked for (on the search level, from its rows): the preview belongs to the old rows and never opens under a new row's title
    MOBY = [{'identifier': 'moby_dick_librivox', 'title': 'Moby Dick', 'creator': 'Herman Melville', 'runtime': '20:00:00'}]
    pick = lambda u, o: {'body': json.dumps({'response': {'docs': SEARCH_DOCS if 'twain' in u else MOBY}}).encode()}
    for label, answered in (('the answer came while the keyboard was open', True), ('the worker still runs', False)):
        reqs = []
        m = opened(archive(reqs, search=pick))
        popular(m)
        to_search(m)
        m.call(PSYMS['bf_done'], a0=m.cstr('mark twain'), count=40000000)
        work(m); tick(m)
        m.thread = None
        BKP.tap(m, 150, SRCH + 1 * ROW + 20, off=SRCH)   # (Tom Sawyer: Loading...)
        expect(m.thread is not None and [s for t_, s in rows(m) if t_ == 'Tom Sawyer'] == ['Loading…'], f'{label}: a tap on a search result asks for its parts')
        if answered: work(m)   # (no tick: the page is behind the keyboard)
        old = m.thread
        m.call(PSYMS['bf_done'], a0=m.cstr('melville'), count=40000000)
        if not answered:
            expect(m.thread is old, f'{label}: the search waits for the worker')
            work(m); tick(m)
        work(m); tick(m)
        got = rows(m)
        expect(at_srch(m) and got == [('Moby Dick', 'Herman Melville')] and not toasts(m), f'{label}: the new search\'s rows on the search level, no preview opened, no row left on Loading... ({got}, {toasts(m)})')
        expect(m.call(PSYMS['bn_preview_count'], count=2000000) == 0, f'{label}: the old book\'s parts are not held')
        reqs.clear(); m.thread = None
        BKP.tap(m, 150, SRCH + 20, off=SRCH)
        expect(m.thread is not None, f'{label}: a new row can be tapped')
        work(m); tick(m)
        expect(reqs and reqs[0] == f'{HOST}/metadata/moby_dick_librivox/files' and m.wtext.get(m.widgets['label_title']) == 'Moby Dick' and not field(m)[0], f'{label}: the tapped row\'s own parts are fetched and its preview opens ({reqs[:1]})')
    # the clear button lets go of a preview that was asked for too, and the magnifier waits while a row's parts are fetched
    reqs = []
    m = opened(archive(reqs, search=SEARCH_DOCS))
    popular(m); settle(m)
    m.thread = None
    BKP.tap(m, 150, POP + 1 * ROW + 20, off=POP)   # (Pride and Prejudice: Loading...)
    BKP.click(m, 'btn_search')
    expect(at_lv(m) and m.thread is not None, 'the magnifier does nothing while a row\'s parts are being fetched (Podcasts: no search while a preview loads)')
    work(m); tick(m)
    expect(m.wtext.get(m.widgets['label_title']) == 'Pride and Prejudice', 'the preview opens')
    # Back from a preview returns to the level it was opened from: Popular at its offset, or the search results at theirs
    BKP.click(m, 'btn_return')
    expect(at_lv(m), 'Back from a Popular preview: the LibriVox level')
    MANY = [{'identifier': f'book_{i:02}_librivox', 'title': f'Book {i:02}', 'creator': 'An Author', 'runtime': '1:00:00'} for i in range(12)]
    m.curl_site = archive(reqs, search=MANY)
    to_search(m)
    m.call(PSYMS['bf_done'], a0=m.cstr('twain'), count=40000000); work(m); tick(m)
    m.thread = None
    m.setword(m.sv + PCP.SC_YOFF, 100)
    BKP.tap(m, 150, SRCH + ROW + 20, off=100)
    work(m); tick(m)
    expect(m.wtext.get(m.widgets['label_title']) == 'Book 01', 'a search result opens its preview')
    BKP.click(m, 'btn_return')
    expect(at_srch(m) and field(m)[5] == 'twain' and rows(m, 100)[0][0] == 'Book 00' and m.props.get((m.sv, 'yoffset')) == 100, f'Back from a search result\'s preview: the search level with its rows, at the offset it was left at ({rows(m, 100)[:1]})')
    # the search's pictures were cut (opening a preview cancels them): Back fetches only the missing ones, with no new query, and the rows and the offset stay
    pics = []
    def cut(u):
        pics.append(u)
        if len(pics) == 3: m.setword(CANCEL, 1)
        return {'body': BKN.THUMB, 'chunk': 5500}
    m.curl_site = archive(reqs, search=MANY, img=cut)
    m.call(PSYMS['bf_done'], a0=m.cstr('austen'), count=40000000); work(m); tick(m)
    expect(len(pics) == 3 and rows(m)[0][0] == 'Book 00', f'the search answered and its pictures were cut at the third ({len(pics)})')
    m.curl_site = archive(reqs, search=MANY)
    m.thread = None
    m.setword(m.sv + PCP.SC_YOFF, 100)
    BKP.tap(m, 150, SRCH + ROW + 20, off=100)
    work(m); tick(m)
    expect(m.wtext.get(m.widgets['label_title']) == 'Book 01', 'a result of that search opens its preview')
    reqs.clear(); m.thread = None
    BKP.click(m, 'btn_return')
    expect(at_srch(m) and field(m)[5] == 'austen' and rows(m, 100)[0][0] == 'Book 00' and m.props.get((m.sv, 'yoffset')) == 100 and not style(m, 'label_bk_hint', 100) and m.thread is not None,
           f'Back with pictures missing: the rows and the offset stay, a worker starts for the pictures ({m.props.get((m.sv, "yoffset"))}, {rows(m, 100)[:1]})')
    work(m); tick(m)
    expect(reqs and not [u for u in reqs if 'advancedsearch' in u] and rows(m, 100)[0][0] == 'Book 00' and m.props.get((m.sv, 'yoffset')) == 100, f'only pictures are fetched, no query ({len(reqs)} requests, {[u[:60] for u in reqs if "advancedsearch" in u]})')
    # the same while another page's job has the slot: the pictures wait for it, the rows and the offset stay meanwhile
    pics.clear()
    m.curl_site = archive(reqs, search=MANY, img=cut)
    m.call(PSYMS['bf_done'], a0=m.cstr('bronte'), count=40000000); work(m); tick(m)
    m.curl_site = archive(reqs, search=MANY)
    m.thread = None
    m.setword(m.sv + PCP.SC_YOFF, 100)
    BKP.tap(m, 150, SRCH + ROW + 20, off=100)
    work(m); tick(m)
    expect(len(pics) == 3 and m.wtext.get(m.widgets['label_title']) == 'Book 01', 'a search cut at its third picture again, and a preview')
    m.thread = None
    m.call(PSYMS['pn_search'], a0=m.cstr('x'), count=1 << 40)
    other, m.thread = m.thread, None
    reqs.clear()
    BKP.click(m, 'btn_return')
    held = lambda: at_srch(m) and len(rows(m, 100)) > 0 and rows(m, 100)[0][0] == 'Book 00' and m.props.get((m.sv, 'yoffset')) == 100 and not style(m, 'label_bk_hint', 100)
    expect(other is not None and m.thread is None and held(), f'Back while another page\'s job runs: nothing starts, the rows and the offset stay ({m.props.get((m.sv, "yoffset"))}, {len(rows(m, 100))} rows)')
    tick(m)
    expect(m.thread is None and m.word(CANCEL) == 0 and held(), 'a tick meanwhile: still waiting, the other job is not cancelled, the rows stay')
    PCN.work(m, other); tick(m)
    expect(m.thread is not None and held(), 'the other job ended: the pictures\' worker starts, the rows stay')
    reqs.clear(); work(m); tick(m)
    expect(reqs and not [u for u in reqs if 'advancedsearch' in u] and held(), f'only pictures are fetched ({len(reqs)} requests)')
    BKP.click(m, 'btn_return')
    expect(at_lv(m) and 'navigator_back' not in m.names(), 'Back from the search level: the LibriVox level')
    # a book with no author has only the totals line
    m = opened(archive([]))
    popular(m)
    preview(m, 3)   # (Short Poetry Collection 001: no author)
    H = pod_books.preview(font(), 'Short Poetry Collection 001', '', n)
    expect(m.props.get((m.sv, 'virtual_h')) == H['h'] and [x for x, r, s in texts(m) if s == 'label_bk_sub'] == [line], f'no author: one grey line ({[x for x, r, s in texts(m) if s == "label_bk_sub"]})')
    # a failure toasts and leaves the row as it was; a search of the preview is a failure of its own
    for label, meta, word in (('no connection', lambda u, o: {'rc': 6}, "Can't connect"), ('HTTP 503', lambda u, o: {'rc': 22, 'code': 503}, 'Server error'), ('a certificate error', lambda u, o: {'rc': 60}, 'Certificate problem')):
        m = opened(archive([], meta=meta))
        popular(m)
        m.calls = []
        preview(m, 1)
        expect(toasts(m) == [word] and at_lv(m) and [s for t_, s in rows(m) if t_.startswith('Pride')] == ['Jane Austen'], f'{label}: the toast says "{word}", the level stays, the row is the author again ({toasts(m)})')
    # no book we can take: Not available, dimmed, no chevron, no tap, for the session
    m = opened(archive([], meta=lambda u, o: {'body': BKN.result(BKN.obj(name='a.zip', format='ZIP'))}))
    popular(m)
    m.calls = []
    preview(m, 1)
    expect(not toasts(m) and at_lv(m), 'an item with no MP3 part: no toast')
    bl, _, _, fills = PCP.paint(m, top(m))
    dim = [f_ for f_ in fills if f_[0] == O['PQ_DIM']]
    expect([s for t_, s in rows(m) if t_.startswith('Pride')] == ['Not available'] and len(dim) == 1 and dim[0][2] == ROW, f'the row says Not available and is dimmed ({dim})')
    chev = [b for b in bl if tuple(b[2][2:]) == (10, 16)]   # (POD_CHEV_W x POD_CHEV_H)
    covers = [b for b in bl if tuple(b[2][2:]) == (O['LIST_ART'], O['LIST_ART'])]
    expect(len(covers) >= 5 and len(chev) == len(covers) - 1, f'only the rows that can open have a chevron: the dimmed one has none ({len(chev)} of {len(covers)})')
    reqs = []
    m.curl_site = archive(reqs)
    BKP.tap(m, 150, POP + ROW + 20, off=POP)
    expect(not reqs and m.thread is None and at_lv(m), 'a dimmed row takes no tap')
    BKP.click(m, 'btn_return'); enter(m); tick(m)
    expect([s for t_, s in rows(m) if t_.startswith('Pride')] == ['Not available'], 'it stays Not available when the level is entered again')


def download_tests(ctx):
    """Download: the folder, the manifest, the job, the Book level of a book of no part yet; Open; a refusal after the folder was made; a failed create."""
    expect = ctx.expect
    n, secs, size = files_info()
    H = pod_books.preview(font(), 'Pride and Prejudice', 'Jane Austen', n)
    cap = lambda m, dy=20: BKP.tap(m, H['x_btn'] + 40, H['y_btn'] + dy)
    reqs = []
    m = opened(archive(reqs))
    popular(m); preview(m, 1)
    folder = f'{BR}/Pride and Prejudice'
    m.thread = None; m.calls = []
    cap(m)
    expect(f'{folder}/.librivox' in m.fs and f'{folder}/cover.jpg' in m.fs and active(m) == PCN.pc_hash('audiobooks/Pride and Prejudice') and m.thread is not None,
           f'Download: the folder with its manifest and cover, the download job started ({[p for p in m.fs if p.startswith(folder)]})')
    man = m.fs[f'{folder}/.librivox'].decode()
    expect(man.startswith('M1PLUS-LIBRIVOX 1\ni=pride_and_prejudice_librivox\nt=Pride and Prejudice\na=Jane Austen\n') and man.count('\n') == 4 + n, 'the manifest names the identifier, the title (the row\'s), the author and the parts')
    B = pod_books.book(font(), 'Pride and Prejudice', n)   # (a book of no part yet: its header and a row for each part the manifest names)
    expect(m.props.get((m.sv, 'virtual_h')) == B['h'] and m.props.get((m.sv, 'yoffset')) == 0 and not field(m)[0] and visible(m, 'bk_big') == 0 and not toasts(m), f'the Book level of the new folder, a book of no part yet: the header and a row for each of the {n} parts ({B["h"]} px)')
    t = texts(m)
    expect([x for x, r, s in t if s == 'label_bk_title'] == B['lines'] and [x for x, r, s in t if s == 'label_bk_sub'] == [pod_books.line_text(n, secs, size)] and [x for x, r, s in t if s == 'label_bk_btn'] == ['Pause'],
           f'its title, the grey line of the manifest\'s totals as the preview said them, the capsule: the download\'s Pause ({[(x, s) for x, r, s in t if s.startswith("label_bk_")]})')
    bl, _, _, fills = PCP.paint(m)
    expect([f_ for f_ in fills if f_[0] == 0xffffffff and B['y_btn'] <= f_[2] < B['y_btn'] + BK['BK_BTN_H']] and not [f_ for f_ in fills if f_[0] in (0xff2b2b2b, 0xff4a4a4a)], 'the capsule is drawn (white), no grey pill beside it')
    rws = rows(m, B['y_list'])
    expect(len(rws) >= 4 and rws[0][0] == '1 Chapters 1-3' and all(r[1] for r in rws), f'a row for each part of the manifest, in its order ({rws[:2]})')
    BKP.tap(m, pod_books.btn_x() + BK['BK_PLAY_W'] + 30, B['y_btn'] + 20)
    expect(not BKP.nav(m) and not toasts(m) and active(m) != 0, 'a tap beside the capsule does nothing')
    # Back: the Library at the offset it was left at, the new book among the rest; the Podcasts row of the same page is untouched
    BKP.click(m, 'btn_return')
    expect(at_library(m) and m.props.get((m.sv, 'virtual_h')) == pod_books.library(6)['h'], 'Back: the Library, six books now')
    expect(any(x == 'Pride and Prejudice' for x, r, s in texts(m, BKP.lib_off(m, 6))), 'the new book is listed')
    # Open: the same book, the folder it is in
    m.call(PSYMS['bd_pause'], key_of_pause(m), count=2000000); work(m)   # (the download is stopped: the rest of the test starts the Preview level over a quiet card)
    enter(m); tick(m)
    mm = m
    preview(mm, 1)
    H2 = pod_books.preview(font(), 'Pride and Prejudice', 'Jane Austen', n, oncard=True)
    t = texts(mm)
    expect([x for x, r, s in t if s == 'label_bk_btn'] == ['Open Book'], 'a book whose folder is on the card: the capsule says Open Book')
    sub = [(x, r) for x, r, s in t if s == 'label_bk_sub']
    expect(sub == [('Jane Austen', (BK['BK_NAME_X'], H2['y_auth'], BK['BK_NAME_W'], BK['BK_SUB_H'])), (pod_books.line_text(n, secs, size), (BK['BK_NAME_X'], H2['y_tot'], BK['BK_NAME_W'], BK['BK_SUB_H'])),
                   (pod_books.card_line(0, n), (BK['BK_NAME_X'], H2['y_card'], BK['BK_NAME_W'], BK['BK_SUB_H']))] and pod_books.card_line(0, n) == f'0 of {n} parts downloaded' and H2['y_btn'] == H['y_btn'] + BK['BK_SUB_H'],
           f'parts missing: a third grey line says how many are on the card, the header one line taller ({sub})')
    names = [ln.split('\t')[0] for ln in mm.fs[f'{folder}/.librivox'].decode().split('\n')[4:4 + n]]
    for nm in names[:2]: mm.put(f'{folder}/{nm}')
    BKP.click(mm, 'btn_return')
    preview(mm, 1)
    expect([x for x, r, s in texts(mm) if s == 'label_bk_sub'][-1:] == [pod_books.card_line(2, n)] and [x for x, r, s in texts(mm) if s == 'label_bk_btn'] == ['Open Book'], 'two parts on the card: "2 of N parts downloaded", still Open Book')
    for nm in names[2:]: mm.put(f'{folder}/{nm}')
    BKP.click(mm, 'btn_return')
    preview(mm, 1)
    expect([x for x, r, s in texts(mm) if s == 'label_bk_sub'][-1:] == [pod_books.line_text(n, secs, size)] and [x for x, r, s in texts(mm) if s == 'label_bk_btn'] == ['Open Book'], 'every part on the card: no third line')
    folders = len([p for p in mm.dirs if p.startswith(BR + '/')])
    mm.calls = []
    cap(mm)
    expect(mm.props.get((mm.sv, 'virtual_h')) == B['h'] and [x for x, r, s in texts(mm) if s == 'label_bk_title'] == B['lines'] and len([p for p in mm.dirs if p.startswith(BR + '/')]) == folders, 'Open: the Book level of that folder, nothing made again')
    # a refusal after the folder was made: the Book level opens and the toast says why
    for label, kw, word in (('no Wi-Fi', dict(wifi=-1), 'No Wi-Fi'), ('a clock never set', dict(wall=1700000000), 'Set the date first')):
        m = opened(archive([]))
        popular(m); preview(m, 1)
        for k, v in kw.items(): setattr(m, k, v)
        m.calls = []
        cap(m)
        expect(f'{BR}/Pride and Prejudice/.librivox' in m.fs and toasts(m) == [word] and m.props.get((m.sv, 'virtual_h')) == B['h'] and active(m) == 0, f'{label}: the folder is made, the Book level opens, the toast says "{word}", no job ({toasts(m)})')
    m = opened(archive([]))
    popular(m); preview(m, 1)
    other_book(m)
    BKD.start(m, 'Other', run=False)   # another book downloads
    m.thread = None; m.calls = []
    cap(m)
    expect(f'{BR}/Pride and Prejudice/.librivox' in m.fs and toasts(m) == [] and m.props.get((m.sv, 'virtual_h')) == B['h'] and active(m) == BKD.key_of('Other') and m.thread is None and state_of(m, 'Pride and Prejudice') == 2,
           f'another book downloads: the folder is made, the Book level opens, the book waits in the queue behind it, no toast, no second thread ({toasts(m)})')
    # bd_create fails: Storage unavailable, the preview stays
    m = opened(archive([]))
    popular(m); preview(m, 1)
    m.fail.add(('mkdir', f'{BR}/Pride and Prejudice'))
    m.calls = []
    cap(m)
    expect(toasts(m) == ['Storage unavailable'] and m.props.get((m.sv, 'virtual_h')) == H['h'] and not [p for p in m.fs if p.startswith(f'{BR}/Pride')], f'no folder could be made: "Storage unavailable", the preview stays ({toasts(m)})')
    # the capsule only responds on the capsule
    m = opened(archive([]))
    popular(m); preview(m, 1)
    m.setword(m.sv + PCP.SC_YOFF, 0); m.setword(m.view + 4, 0)
    m.touch('down', H['x_btn'] + 40, BKP.SCREEN_Y0 + H['y_btn'] + 20, 1000, fn='bk_on_down')
    bl, _, _, fills = PCP.paint(m)
    expect(any(f_[0] == 0xffc8c8c8 for f_ in fills), 'a pressed capsule is a little darker')
    m.touch('abort', 5, BKP.SCREEN_Y0 + 5, 1010, fn='bk_on_abort')


# ---------------------------------------------------------------------------
# The Book level's download row, the Library's line, the tick, the keep-awake timer (patch/bkpage.c)
DLP = [('b_01.mp3', 'Chapter One', 70000), ('b_02.mp3', 'Chapter Two', 50000), ('b_03.mp3', 'Chapter Three', 90000)]
DIR = 'Pride and Prejudice'
BOOK_DIR = f'{BR}/{DIR}'
BKEY = BKD.key_of(DIR)
BYTES = sum(s for *_, s in DLP)
DL_REC = 16 + 3 * 4 * 16 + 2 * 4   # patch/bkdl.c's record up to its pnw_dl_t: run, key, part, parts, the three result tables, next, gen
DL_AT = {'got': 0, 'total': 4, 'gen': 12, 'wait': 16}


def book_site(hook=None, parts=DLP):
    """The scripted archive for one book of small parts: the popular answer, the files answer, the pictures and the parts (Range understood); hook(name, start, opts) may answer a part instead."""
    files = BKD.BK.result(*[BKD.obj(n, t, s) for n, t, s in parts])
    data = {n: bytes([i + 1]) * s for i, (n, t, s) in enumerate(parts)}
    arch = archive([], meta=lambda u, o: {'body': files, 'chunk': 16384})

    def site(url, o):
        if '/download/' not in url: return arch(url, o)
        name = unquote(url.rsplit('/', 1)[1])
        rng = o.get(10007)
        start = int(rng.rstrip('-')) if rng else 0
        r = hook(name, start, o) if hook else None
        if r is not None: return r
        d = data[name]
        base = dict(chunk=65536, ctype='audio/mpeg')
        return dict(base, code=206, body=d[start:], length=len(d) - start) if start else dict(base, code=200, body=d, length=len(d))
    return site


def other_book(m, d='Other'):
    """A second book on the card (a manifest of the same three parts under another identifier), so that a download of it can run while the page asks for Pride and Prejudice."""
    m.put(f'{BR}/{d}/.librivox', BKD.man_text([(f'{i} {t}.mp3', 60, s, n_, t) for i, (n_, t, s) in enumerate(DLP, 1)], ident='other_librivox', title=d))


def started(site=None, **kw):
    """Popular, the preview of Pride and Prejudice (three parts), a tap on Download: the Book level of the new folder, the job started and not yet run (m.thread)."""
    m = opened(site or book_site(), **kw)
    popular(m); preview(m, 1)
    H = pod_books.preview(font(), 'Pride and Prejudice', 'Jane Austen', len(DLP))
    BKP.tap(m, H['x_btn'] + 40, H['y_btn'] + 20)
    return m


def layout(n): return pod_books.book(font(), DIR, n)
def row(m, n): return rows(m, layout(n)['y_list'])   # [(title, grey line)] of the Book level, n rows in all
def bd_at():
    """The address of patch/bkdl.c's static record `bd` (another file has a static of that name: PSYMS holds one of them), found by its size in the symbol table."""
    import pod   # noqa: PLC0415
    size = DL_REC + 6 * 4 + 4
    for line in subprocess.check_output([os.path.join(pod.LLVM, 'llvm-readelf'), '-sW', os.path.join(BUILD, 'patch.elf')], text=True).splitlines():
        f = line.split()
        if len(f) >= 8 and f[7] == 'bd' and f[2] == str(size): return int(f[1], 16)
    raise AssertionError('the record bd of bkdl.c')
def poke(m, what, v): m.setword(bd_at() + DL_REC + DL_AT[what], v)
def peek(m, what): return m.word(bd_at() + DL_REC + DL_AT[what])
def step(m, **kw):
    """The worker's counters as a transfer in progress leaves them, the generation moved."""
    for k, v in kw.items(): poke(m, k, v)
    poke(m, 'gen', peek(m, 'gen') + 1)
def row_tap(m, n, i=None): BKP.tap(m, 150, layout(n)['y_list'] + ROW * (n - 1 if i is None else i) + 20, off=layout(n)['y_list'])
def ended(m): work(m); tick(m)
def height(m): return m.props.get((m.sv, 'virtual_h'))
def state_of(m, d): return m.call(PSYMS['bd_state'], BKD.key_of(d), count=2000000)   # 0 none, 1 runs, 2 waits
def key_of_pause(m): return m.call(PSYMS['bd_active'], count=2000000)   # the running book's key, what bd_pause is asked with
def pause(m): m.call(PSYMS['bd_pause'], key_of_pause(m), count=2000000); ended(m)
def flags(m, n): return m.props.get((m.widgets[n], 'visible'), 1), m.props.get((m.widgets[n], 'sensitive'), 1)
def confirms(m): return [c[1] for c in m.calls if c[0] == 'confirm']
def unlinks(m): return [c[1] for c in m.calls if c[0] == 'unlink']
def fixed(s):
    try: return s.encode('latin-1').decode('utf-8') if s else s
    except (UnicodeEncodeError, UnicodeDecodeError): return s


TITLES = [f'{i} {t}' for i, (n_, t, s) in enumerate(DLP, 1)]   # a part's row says its local file name without the extension, on the card or not
WAITING = [pod_books.miss_sub(60, s) for *_, s in DLP]         # the grey line of a manifest part that is not on the card: its time and size
PX, X0, GAP = O['PA_DL_PX'], BK['BK_PART_X'], 6   # (LS_MK_GAP, patch/libsrc.h)
STOP, ARROW = O['PA_DL_STOP'], O['PA_DL_ARROW']
CAP_X = pod_books.btn_x()                                      # the capsule stands alone, centred (the Show page's main pill, the preview's capsule)


def hdr(m):
    """(the grey line, the capsule's word) of the Book level's header, as lists."""
    t = texts(m)
    return [x for x, r, s in t if s == 'label_bk_sub'], [x for x, r, s in t if s == 'label_bk_btn']


def rings(m, n):
    """{row: [(atlas cell, x)]} of the download ring blits of the Book level's n rows (a 14 px square at the middle of the grey line)."""
    L = layout(n)
    off = L['y_list']
    out = {}
    for b in PCP.paint(m, off)[0]:
        if tuple(b[2][2:]) == (PX, PX):
            for i in range(n):
                if b[2][1] == L['row'](i) - off + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - PX // 2:
                    out.setdefault(i, []).append((b[1][0] // PX + (b[1][1] - O['PA_DSD_H']) // PX * O['PA_DL_COLS'], b[2][0]))
    return out


def ring_of(*a, **kw):
    """The cells the model says: the arc's step, then the stop square or the arrow, at the text column."""
    r = pod_books.ring('run', *a, **kw)
    return [(r[0], X0), (STOP if r[1] == 'stop' else ARROW, X0)]


def row_tests(ctx):
    """Every part the manifest names is a row from the first moment, on the card or not; the part being fetched has the shared ring and its percent; the capsule of a book with no part follows the download; a tap on a part that is not on the card starts it."""
    expect = ctx.expect
    m = started()
    L = layout(3)
    expect(m.thread and m.thread[0] == PSYMS['bd_main'] and active(m) == BKEY, 'Download started the job')
    expect(pod_books.fetch_sub(0, 0) == 'Downloading' and row(m, 3)[0][1] == 'Downloading', f'the part just started (no length, no bytes yet): Downloading, not "0 MB" beside the ring ({row(m, 3)[0]})')
    expect(row(m, 3) == [(TITLES[0], pod_books.fetch_sub(0, 0))] + list(zip(TITLES[1:], WAITING[1:])) and height(m) == L['h'] and len(row(m, 3)) == 3,
           f'a book with no file yet lists all three parts the manifest names, in its order: the part being fetched "0 MB" (its length is not known yet), the others their time and size ({row(m, 3)}, {height(m)})')
    expect(hdr(m) == ([pod_books.line_text(3, 180, BYTES)], ['Pause']) and pod_books.line_text(3, 180, BYTES) == '3 parts · 3m · 1 MB',
           f'the header: the manifest\'s totals as the preview says them, the capsule alone is the download\'s Pause ({hdr(m)})')
    expect(rings(m, 3) == {0: ring_of(0, 0)} and pod_books.ring('run', 0, 0) == (0, 'stop'), f'the ring (the Podcasts ring cells, the stop square) before the grey line of the part being fetched, none on the others ({rings(m, 3)})')
    bl, texts_, styles, fills = PCP.paint(m, L['y_list'])
    sub = {r[1]: (x, r) for (x, r), s in zip(texts_, styles) if s == 'label_row_sub'}
    y0 = L['row'](0) - L['y_list'] + O['LIST_SUB_Y']
    expect(sub[y0][1][0] == X0 + PX + GAP and sub[y0][1][2] == BK['BK_PART_W'] - PX - GAP and sub[y0 + ROW][1][0] == X0,
           f'the grey line of the ring row starts a ring and a gap right, the others at the text column ({sub[y0][1]})')
    expect((O['LIST_HAIR'], BK['BK_PART_X'], ROW - 1, 320 - BK['BK_PART_X'], 1) in fills and not [f_ for f_ in fills if f_[0] not in (O['LIST_HAIR'], O['LIST_PRESS'], 0xff000000) and f_[2] == ROW - 1],
           'plain rows: the hairline from the text, no other colour')
    step(m, total=70000, got=31500)
    tick(m)
    expect(row(m, 3)[0] == (TITLES[0], pod_books.fetch_sub(31500, 70000)) and row(m, 3)[0][1] == '45%' and rings(m, 3) == {0: ring_of(31500, 70000)} and rings(m, 3)[0][0][0] == 5,
           f'the percent of the part follows the generation: "45%", step 5 of 12 ({row(m, 3)[0]}, {rings(m, 3)})')
    step(m, wait=1)
    tick(m)
    expect(row(m, 3)[0] == (TITLES[0], 'Waiting') and rings(m, 3) == {0: ring_of(wait=1)} and ring_of(wait=1)[1][0] == ARROW,
           f'while it sleeps before a retry: "Waiting", the empty ring with the arrow ({row(m, 3)[0]}, {rings(m, 3)})')
    step(m, wait=0, got=0, total=0)
    tick(m)
    m.calls = []; th0 = m.thread
    row_tap(m, 3, 0); row_tap(m, 3, 2)
    expect(not toasts(m) and m.thread is th0 and active(m) == BKEY, 'a tap on a part, the one being fetched or one that is not there yet, while the book downloads does nothing')
    # the capsule pauses; the rows are idle, the capsule resumes
    BKP.tap(m, CAP_X + 40, L['y_btn'] + 20)
    ended(m)
    expect(active(m) == 0 and row(m, 3) == list(zip(TITLES, WAITING)) and not rings(m, 3) and hdr(m)[1] == ['Resume'], f'paused from the capsule: no ring, every part its time and size, the capsule says Resume ({row(m, 3)}, {hdr(m)})')
    m.thread = None
    BKP.tap(m, CAP_X + 40, L['y_btn'] + 20)
    expect(m.thread and m.thread[0] == PSYMS['bd_main'] and hdr(m)[1] == ['Pause'] and rings(m, 3) == {0: ring_of(0, 0)}, 'the capsule resumes the download')
    pause(m)
    # a tap on a part that is not on the card starts the job
    m.thread = None
    row_tap(m, 3, 1)
    expect(m.thread and m.thread[0] == PSYMS['bd_main'] and active(m) == BKEY and rings(m, 3).get(0), 'a tap on a part that is not on the card starts the book\'s download')
    # every part lands: the rows are ordinary rows in place, the height is the same
    m.setword(m.sv + PCP.SC_YOFF, 20)
    ended(m)
    W = layout(3)
    expect(sorted(p for p in m.fs if p.startswith(BOOK_DIR) and p.endswith('.mp3')) == [f'{BOOK_DIR}/{t}.mp3' for t in TITLES] and height(m) == W['h'] == L['h'] and m.props.get((m.sv, 'yoffset')) == 20,
           f'all parts landed: the same three rows at the same scroll offset ({height(m)} / {W["h"]})')
    expect(row(m, 3) == [(t, pod_books.part_sub(0, 0, 0, (s + 1023) // 1024, man=(60, s))) for t, (n_, tt, s) in zip(TITLES, DLP)] and not rings(m, 3) and [r[1] for r in row(m, 3)] == WAITING and WAITING[0] == '1m · 1 MB', f'ordinary rows now: the same grey line as before the file landed, the manifest\'s time and the size ({row(m, 3)}, {WAITING})')
    expect(hdr(m) == (['Not started · 3 parts'], ['Play']), f'and the header is the book\'s: its grey line and Play ({hdr(m)})')
    # one part to fetch of known and of unknown size
    for parts, line in (([('b_01.mp3', 'One', 3 << 20)], '1m · 3 MB'), ([('b_01.mp3', 'One', 0)], '1m')):
        m = started(book_site(parts=parts))
        pause(m)
        expect(row(m, 1) == [('1 One', line)] == [('1 One', pod_books.miss_sub(60, parts[0][2]))], f'one part to fetch: "{line}" ({row(m, 1)})')


def fail_tests(ctx):
    """A failure: the reason on the part it stopped at and in the header, the part before it is a normal row, a tap on the failed part tries again; refusals toast their word; a book of your own has Playback Speed alone in its sheet."""
    expect = ctx.expect
    for label, rep, word in (('a part the archive no longer has', {'code': 404}, 'Server error'), ('a certificate error', {'rc': 60}, 'Certificate problem'), ('a web page for a part', {'ctype': 'text/html', 'body': b'<html>x</html>', 'code': 200}, 'Server error')):
        bad = [True]
        m = started(book_site(lambda n_, st, o: rep if n_ == 'b_02.mp3' and bad[0] else None))
        ended(m)
        want = [(TITLES[0], pod_books.part_sub(0, 0, 0, 69, man=(60, DLP[0][2]))), (TITLES[1], pod_books.failed_sub(word)), (TITLES[2], WAITING[2])]
        expect(row(m, 3) == want and height(m) == layout(3)['h'] and f'{BOOK_DIR}/1 Chapter One.mp3' in m.fs and active(m) == 0 and not rings(m, 3),
               f'{label}: the first part is a row of the card, the second says "Failed: {word}", the third its time and size ({row(m, 3)}, {height(m)} / {layout(3)["h"]})')
        expect(hdr(m) == ([pod_books.dl_head('idle', total=3, present=1, failed=word)], ['Play']) and hdr(m)[0] == [f'Failed: {word}'],
               f'the header keeps Play and says why the rest stopped ({hdr(m)})')
        bad[0] = False
        m.thread = None; m.calls = []
        row_tap(m, 3, 1)
        expect(m.thread and not toasts(m) and active(m) == BKEY, f'{label}: a tap on the failed part tries again')
        ended(m)
        expect(height(m) == layout(3)['h'] and [r[0] for r in row(m, 3)] == TITLES and not [r for r in row(m, 3) if r[1].startswith('Failed')] and not rings(m, 3),
               f'{label}: and the book is whole after the retry ({row(m, 3)})')
    m = started(book_site(lambda n_, st, o: {'code': 404} if n_ == 'b_01.mp3' else None))
    ended(m)
    expect(row(m, 3)[0] == (TITLES[0], 'Failed: Server error') and hdr(m)[1] == ['Retry'] and hdr(m)[0] == [pod_books.line_text(3, 180, BYTES)],
           f'no part on the card and the first failed: the capsule says Retry, the header keeps the manifest\'s totals ({row(m, 3)[0]}, {hdr(m)})')
    m.thread = None
    BKP.tap(m, CAP_X + 40, layout(3)['y_btn'] + 20)
    expect(m.thread and hdr(m)[1] == ['Pause'], 'the capsule tries again')
    m = started(book_site(lambda n_, st, o: {'rc': 6} if n_ == 'b_02.mp3' else None))
    ended(m)
    expect(row(m, 3)[1] == (TITLES[1], "Failed: Can't connect"), f'no connection (after the three retries): "Failed: Can\'t connect" ({row(m, 3)})')
    # refusals: another book downloads, no Wi-Fi
    m = started(); pause(m)
    other_book(m)
    BKD.start(m, 'Other', run=False)   # another book downloads
    m.thread = None; m.calls = []
    row_tap(m, 3, 0)
    expect(toasts(m) == [] and active(m) == BKD.key_of('Other') and m.thread is None and state_of(m, DIR) == 2 and not rings(m, 3) and row(m, 3) == list(zip(TITLES, WAITING)) and hdr(m)[1] == ['Pause'],
           f'another book downloads: the tap queues the book, no toast; no ring on its rows; the capsule says Pause ({toasts(m)}, {row(m, 3)}, {hdr(m)})')
    m = started(); pause(m)
    m.wifi = -1; m.calls = []
    row_tap(m, 3, 0)
    expect(toasts(m) == ['No Wi-Fi'] and active(m) == 0 and row(m, 3) == list(zip(TITLES, WAITING)), f'no Wi-Fi: the toast says so ({toasts(m)})')
    # a book of your own (no manifest): the same rows as ever, no download rows in its sheet
    m = opened(archive([]))
    BKP.open_book(m, 'Alpha')
    H = BKP.header(m, 'Alpha', 3)
    expect(height(m) == H['h'] and len(rows(m, H['y_list'])) == 3 and flags(m, 'btn_more') == (1, 1), 'a hand-copied book has its three parts and the "..."')
    BKP.click(m, 'btn_more')
    expect(flags(m, 'bk_sh_card') == (1, 1) and [r for r, *_ in pod_ui.BK_SHEET_ROWS if flags(m, f'bk_sh_{r}') == (1, 1)] == ['speed'], 'its sheet holds Playback Speed alone: no Pause, Resume or Delete Book')
    BKP.click(m, 'bk_sh_scrim')
    BKP.tap(m, 150, H['y_list'] + 3 * ROW + 20, off=H['y_list'])
    expect(not BKP.nav(m) and not toasts(m), 'nothing below its last part takes a tap')


def follow_tests(ctx):
    """Parts that appear as they land at the same offset, a book of no part getting its Play, the header's line with parts on the card, the queue of the parts on the card; the Podcasts queue and the book download run side by side and the tick starts neither."""
    expect = ctx.expect
    m = started(book_site(lambda n_, st, o: {'rc': 6} if n_ == 'b_02.mp3' else None))
    expect(hdr(m)[1] == ['Pause'], 'a book of no part yet: the capsule is the download\'s')
    m.setword(m.sv + PCP.SC_YOFF, 40)
    ended(m)
    expect(m.props.get((m.sv, 'yoffset')) == 40 and height(m) == layout(3)['h'], 'the rescan keeps the scroll offset and the height')
    expect(hdr(m)[1] == ['Play'], f'the first part landed: the capsule is Play ({hdr(m)})')
    expect([r[0] for r in rows(m, layout(3)['y_list'])] == TITLES, 'the part is a row of the list, in place')
    # the queue holds the parts on the card only, in order
    m.calls = []
    BKP.tap(m, pod_books.btn_x() + 40, layout(3)['y_btn'] + 20)
    q, idx = m.played
    expect(BKP.ids_of(m, q) == [f'{BOOK_DIR}/1 Chapter One.mp3'] and idx == 0, f'Play: the queue holds the file on the card ({BKP.ids_of(m, q)})')
    m.calls = []; m.played = None
    row_tap(m, 3, 2)
    expect(m.played is None and not BKP.nav(m), 'a part that is not on the card does not play')
    row_tap(m, 3, 0)
    expect(m.played and BKP.ids_of(m, m.played[0]) == [f'{BOOK_DIR}/1 Chapter One.mp3'], 'a part that is does')
    # parts on the card, the job running on the second: the header's line, the ring and the percent on its row
    m = started()
    m.put(f'{BOOK_DIR}/1 Chapter One.mp3'); m.sizes[f'{BOOK_DIR}/1 Chapter One.mp3'] = 70000
    m.setword(bd_at() + 8, 1)   # (the worker's part: the second)
    step(m, total=50000, got=25000)
    tick(m)
    expect(hdr(m) == ([pod_books.dl_head('run', 1, 3)], ['Play']) and hdr(m)[0] == ['Downloading · Part 2 of 3'], f'with the first part on the card the header says what the download does ({hdr(m)})')
    expect(row(m, 3) == [(TITLES[0], '1m · 1 MB'), (TITLES[1], '50%'), (TITLES[2], WAITING[2])] and rings(m, 3) == {1: ring_of(25000, 50000)}, f'the ring and the percent are on the second part\'s row ({row(m, 3)}, {rings(m, 3)})')
    step(m, wait=1)
    tick(m)
    expect(hdr(m)[0] == [pod_books.dl_head('run', 1, 3, wait=1)] and hdr(m)[0] == ['Waiting · Part 2 of 3'], 'waiting to retry')
    pause(m)
    expect(hdr(m)[0] == [pod_books.dl_head('idle', total=3, present=1)] and hdr(m)[0] == ['1 of 3 parts downloaded'], f'paused: how many parts are there ({hdr(m)})')
    # while the download runs, the percent moves with the generation and no scan is made
    m = started()
    m.calls = []
    step(m, total=70000, got=7000)
    tick(m)
    scans = len([c for c in m.calls if c[0] == 'opendir'])
    expect(row(m, 3)[0][1] == '10%' and scans == 0, f'a progress step retexts the row and scans nothing ({row(m, 3)}, {scans} scans)')
    # an episode download added while the book downloads starts at once on its thread; the tick of the Book and of the Library level starts nothing
    for level in ('Book', 'Library'):
        m = started()
        BKD.PCN.sub(m, 'Show', 'https://feeds.example/show', title='Show', checked=1)
        m.put(f'{BKD.DL.SHOW}/.episodes', BKD.DL.eps_text(BKD.DL.entries()))
        m.curl_site = (lambda site: lambda url, o: BKD.DL.server(BKD.DL.DATA)(url, o) if url.startswith('https://cdn.example/') else site(url, o))(m.curl_site)
        m.thread, th = None, m.thread
        m.call(PSYMS['pn_dl_add'], a0=m.cstr(BKD.DL.RP), a1=m.cstr('Show'), a2=m.cstr('a.mp3'), count=1 << 40)
        eth = m.thread
        expect(th[0] == PSYMS['bd_main'] and eth and eth[0] == PSYMS['pn_dmain'] and active(m) == BKEY, 'the episode starts beside the book job: two threads, nothing waits')
        if level == 'Library': BKP.click(m, 'btn_return')
        m.thread = None; m.calls = []
        tick(m)
        expect(m.thread is None and 'pthread_create' not in [c[0] for c in m.calls], f'the {level} level\'s tick starts no thread')
        BKD.PCN.work(m, eth); BKD.PCN.work(m, th)
        expect(m.call(PSYMS['pn_dl_running'], count=2000000) == 0 and active(m) == 0 and m.fs.get(f'{BKD.DL.SHOW}/a.mp3') == BKD.DL.DATA, f'{level}: both finish')


def library_row_tests(ctx):
    """The Library's grey line of a book with parts still to come, and the ring before it while the job runs; whole books keep the ordinary line."""
    expect = ctx.expect

    def line(m):
        y = [t for t, s in rows(m, BKP.lib_off(m))]
        return dict(rows(m, BKP.lib_off(m)))[DIR] if DIR in y else None

    def ring_row(m):
        """(ring cells, x of the grey line's text, its width) of the book's row in a frame."""
        bl, tx, st, _ = PCP.paint(m, BKP.lib_off(m))
        y = next(r[1] for (x, r), s in zip(tx, st) if x == DIR and s == 'label_row_title') - O['LIST_TITLE_Y']
        cells = [(b[1][0] // PX + (b[1][1] - O['PA_DSD_H']) // PX * O['PA_DL_COLS'], b[2][0]) for b in bl if tuple(b[2][2:]) == (PX, PX) and b[2][1] == y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - PX // 2]
        sub = next(r for (x, r), s in zip(tx, st) if s == 'label_row_sub' and r[1] == y + O['LIST_SUB_Y'])
        return cells, sub[0], sub[2]
    m = started()
    BKP.click(m, 'btn_return')
    expect(line(m) == pod_books.dl_lib_sub('run', 0, 3) == 'Part 1 of 3', f'the Library: the job runs ({line(m)})')
    cells, x, w = ring_row(m)
    expect(cells == [(0, O['LIST_TEXT_X']), (STOP, O['LIST_TEXT_X'])] and x == O['LIST_TEXT_X'] + PX + GAP and w == O['LIST_TEXT_W_CHEV'] - PX - GAP,
           f'the shared ring (the stop square, step 0 while the size is unknown) before the grey line, which starts a ring and a gap right ({cells}, {x}, {w})')
    step(m, total=70000, got=35000)
    tick(m)
    cells, x, w = ring_row(m)
    expect(cells == [(6, O['LIST_TEXT_X']), (STOP, O['LIST_TEXT_X'])], f'50% = step 6 ({cells})')
    step(m, wait=1)
    tick(m)
    expect(ring_row(m)[0] == [(0, O['LIST_TEXT_X']), (ARROW, O['LIST_TEXT_X'])], 'waiting to retry: the empty ring with the arrow')
    m.call(PSYMS['bd_pause'], key_of_pause(m), count=2000000)
    m.thread, th = None, m.thread
    BKD.PCN.work(m, th)
    tick(m)
    expect(line(m) == pod_books.dl_lib_sub('idle', 0, 3) == '0 of 3 parts downloaded', f'paused for good ({line(m)})')
    cells, x, w = ring_row(m)
    expect(cells == [] and x == O['LIST_TEXT_X'] and w == O['LIST_TEXT_W_CHEV'], 'no ring and the full width when nothing downloads')
    # one part came, the second failed: "1 of 3 parts downloaded", read again from the card while the Library is up
    m = started(book_site(lambda n_, st, o: {'code': 404} if n_ == 'b_02.mp3' else None))
    BKP.click(m, 'btn_return')
    ended(m)
    expect(line(m) == '1 of 3 parts downloaded', f'a part came and the job failed ({line(m)})')
    step(m)
    tick(m)
    # the whole book is an ordinary book again
    m = started()
    BKP.click(m, 'btn_return')
    ended(m)
    expect(line(m) == 'Not started · 3 parts' and ring_row(m)[0] == [], f'whole: the ordinary line ({line(m)})')
    # a book of your own and the other books keep their lines
    got = dict(rows(m, BKP.lib_off(m)))
    expect(got['Alpha'] == 'Not started · 3 parts' and got['Beta'] == 'Not started', f'the other books are unchanged ({got})')
    # a manifest that does not add up (a cut file) makes no claim
    m = opened(archive([]), cardf=lambda mm: mm.put(f'{BR}/Alpha/.librivox', b'M1PLUS-LIBRIVOX 1\ni=x\nt=T\na=A\nf\t1\t2\n'))
    expect(dict(rows(m, BKP.lib_off(m)))['Alpha'] == 'Not started · 3 parts', 'a cut manifest: the ordinary line')


def sheet_tests(ctx):
    """The "..." of a LibriVox book and its sheet: Playback Speed first, then Pause Download or Resume Download by the state and Delete Book; pause and resume from the sheet, Back, the Preview level without one."""
    expect = ctx.expect
    m = opened(book_site())
    expect(flags(m, 'btn_more') == (0, 0) and m.props.get((m.widgets['btn_backtoplayer'], 'style:normal:icon')) in (None, 'ah_nav_np'), 'the Library has no "..." and Now Playing is the disc')
    m = started()
    expect(flags(m, 'btn_more') == (1, 1) and m.props.get((m.widgets['btn_backtoplayer'], 'style:normal:icon')) == 'ah_nav_play' and m.props.get((m.widgets['btn_backtoplayer'], 'style:pressed:icon')) == 'ah_nav_play_down'
           and ('widget_resize', m.widgets['label_title'], O['NAV_VIEW_X'] - O['NAV_TITLE_X'], 22) in m.calls,
           'a book: the "..." where the Show page has it, Now Playing the right cap of the capsule, the small title ends before it')

    def sheet(m):
        rows_ = [r for r, *_ in pod_ui.BK_SHEET_ROWS if flags(m, f'bk_sh_{r}') == (1, 1)]
        mv = {r: [c[2:] for c in m.calls if c[0] == 'widget_move' and c[1] == m.widgets[f'bk_sh_{r}']][-1:] for r in rows_}
        return flags(m, 'bk_sh_card') == (1, 1) and flags(m, 'bk_sh_scrim') == (1, 1), rows_, mv, m.props.get((m.widgets['bk_sh_card'], 'style:normal:bg_image'))
    m.calls = []
    BKP.click(m, 'btn_more')
    shown, rws, mv, glass = sheet(m)
    expect(shown and rws == ['speed', 'pause', 'delete'] and [mv[r] for r in rws] == [[(0, 0)], [(0, O['PM_ROW_H'])], [(0, 2 * O['PM_ROW_H'])]] and glass == 'pc_sheet3',
           f'while the book downloads: Playback Speed, Pause Download, Delete Book, on the three-row glass ({rws}, {mv}, {glass})')
    expect([r[2] for r in pod_ui.BK_SHEET_ROWS] == ['Playback Speed', 'Pause Download', 'Resume Download', 'Delete Book'] and pod_ui.BK_SHEET_ROWS[3][4] and not any(r[4] for r in pod_ui.BK_SHEET_ROWS[:3]), 'the labels, Delete Book red as Unsubscribe is')
    BKP.click(m, 'bk_sh_scrim')
    expect(flags(m, 'bk_sh_card') == (0, 0) and flags(m, 'bk_sh_scrim') == (0, 0), 'a tap outside closes the sheet')
    BKP.click(m, 'btn_more'); m.calls = []
    BKP.click(m, 'btn_return')
    expect(flags(m, 'bk_sh_card') == (0, 0) and height(m) == layout(3)['h'] and not [c for c in m.calls if c[0] == 'navigator_back'], 'Back closes the sheet first and leaves the book where it is')
    BKP.click(m, 'btn_more'); m.calls = []
    BKP.click(m, 'bk_sh_pause')
    expect(flags(m, 'bk_sh_card') == (0, 0) and active(m) == BKEY, 'Pause Download: the sheet closes, the transfer is told to stop')
    ended(m)
    expect(active(m) == 0 and hdr(m)[1] == ['Resume'] and not rings(m, 3), 'and it has stopped')
    BKP.click(m, 'btn_more')
    shown, rws, mv, glass = sheet(m)
    expect(shown and rws == ['speed', 'resume', 'delete'], f'not downloading with parts missing: Playback Speed, Resume Download, Delete Book ({rws})')
    m.thread = None
    BKP.click(m, 'bk_sh_resume')
    expect(m.thread and m.thread[0] == PSYMS['bd_main'] and active(m) == BKEY and hdr(m)[1] == ['Pause'], 'Resume Download starts it again')
    pause(m)
    m.wifi = -1; m.calls = []
    BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_resume')
    expect(toasts(m) == ['No Wi-Fi'] and active(m) == 0, f'a refusal toasts its word ({toasts(m)})')
    m.wifi = 1; m.thread = None
    BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_resume')
    ended(m)
    BKP.click(m, 'btn_more')
    shown, rws, mv, glass = sheet(m)
    expect(shown and rws == ['speed', 'delete'] and mv['delete'] == [(0, O['PM_ROW_H'])] and glass == 'pc_sheet2', f'a complete book: Playback Speed and Delete Book, on the two-row glass ({rws}, {glass})')
    # the speed row of a LibriVox book: the value, a tap, the sheet stays
    expect(fixed(m.wtext.get(m.widgets['bk_sh_speed_vl'])) == '1×', 'Playback Speed shows 1×')
    BKP.click(m, 'bk_sh_speed')
    expect(fixed(m.wtext.get(m.widgets['bk_sh_speed_vl'])) == '1.25×' and flags(m, 'bk_sh_card') == (1, 1) and m.call(PSYMS['pc_speed_get'], a0=BKEY, count=3000000) == 1, 'a tap cycles it, saved under the book\'s key, the sheet stays')
    # a failure: Resume Download too
    m = started(book_site(lambda n_, st, o: {'code': 404} if n_ == 'b_02.mp3' else None))
    ended(m)
    BKP.click(m, 'btn_more')
    expect(sheet(m)[1] == ['speed', 'resume', 'delete'], 'after a failure the sheet offers Resume Download')
    # the Preview level has none
    m = opened(archive([]))
    popular(m); preview(m, 1)
    expect(flags(m, 'btn_more') == (0, 0), 'the Preview level has no "..."')


def delete_tests(ctx):
    """Delete Book: a confirm first; the files the manifest names with their .part files, the cover, the manifest; the folder only when empty; files that are not the manifest's stay; a running download is stopped and waited for; refused while the book plays."""
    expect = ctx.expect

    def ask(m, yes=True):
        m.calls = []
        m.confirm_yes = yes
        BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_delete')

    m = started()
    ended(m)
    m.put(f'{BOOK_DIR}/Note.txt', b'mine')
    m.put(f'{BOOK_DIR}/1 Chapter One.mp3.part', b'x')
    expect(f'{BOOK_DIR}/.librivox' in m.fs and f'{BOOK_DIR}/cover.jpg' in m.fs, 'the book is on the card with its manifest and cover')
    ask(m, False)
    expect(confirms(m) == ['Delete this book and its files?'] and not unlinks(m) and height(m) == layout(3)['h'], f'Delete Book asks first; No: nothing is touched, the book stays open ({confirms(m)})')
    ask(m)
    gone = sorted(p.replace(BOOK_DIR + '/', '') for p in unlinks(m))
    expect(gone == sorted([f'{t}.mp3' for t in TITLES] + [f'{t}.mp3.part' for t in TITLES] + ['cover.jpg', 'cover.png', '.librivox']),
           f'Yes: each file the manifest names and its .part, the cover the download wrote, the manifest ({gone})')
    expect(f'{BOOK_DIR}/Note.txt' in m.fs and f'{BOOK_DIR}/1 Chapter One.mp3.part' not in m.fs and not [p for p in m.fs if p.startswith(BOOK_DIR) and p != f'{BOOK_DIR}/Note.txt'] and BOOK_DIR in m.dirs and ('rmdir', BOOK_DIR) in m.calls,
           'a file of the user\'s stays, so the folder does too (rmdir refuses; nothing is deleted recursively)')
    expect(at_library(m) and not any(x == DIR for x, r, s in texts(m, BKP.lib_off(m, 5))) and height(m) == pod_books.library(5)['h'], 'back at the Library, read again: the book is gone (a folder with no audio is no book)')
    # a part of the user's own that the manifest does not name stays with the folder
    m = started()
    ended(m)
    m.put(f'{BOOK_DIR}/Extra.mp3', b'y'); m.sizes[f'{BOOK_DIR}/Extra.mp3'] = 1000
    ask(m)
    expect(f'{BOOK_DIR}/Extra.mp3' in m.fs and BOOK_DIR in m.dirs and not [p for p in m.fs if p.startswith(BOOK_DIR) and p != f'{BOOK_DIR}/Extra.mp3'], 'a part of the user\'s own that the manifest does not name is kept, with its folder')
    # nothing else in it: the folder is removed
    m = started()
    ended(m)
    ask(m)
    expect(not [p for p in m.fs if p.startswith(BOOK_DIR)] and BOOK_DIR not in m.dirs and ('rmdir', BOOK_DIR) in m.calls and BR in m.dirs, 'nothing else in it: the folder is removed, Audiobooks stays')
    # a part that cannot be removed: the manifest stays, the toast says so
    m = started()
    ended(m)
    m.fail.add(('unlink', f'{BOOK_DIR}/2 Chapter Two.mp3'))
    ask(m)
    expect(f'{BOOK_DIR}/.librivox' in m.fs and f'{BOOK_DIR}/2 Chapter Two.mp3' in m.fs and toasts(m) == ['Storage unavailable'], f'a file that stays: the manifest stays too, a toast says so ({toasts(m)})')
    # the player is on a file of the book: refused before anything is asked
    m = started()
    ended(m)
    m.track(f'{BOOK_DIR}/2 Chapter Two.mp3')
    ask(m)
    expect(toasts(m) == ['This book is playing'] and not confirms(m) and not unlinks(m) and f'{BOOK_DIR}/.librivox' in m.fs and height(m) == layout(3)['h'], f'refused with a toast while the player is on one of its files ({toasts(m)})')
    # the download runs: it is stopped, nothing is removed until its thread has let go, then the files go
    m = started()
    m.put(f'{BOOK_DIR}/1 Chapter One.mp3.part', b'x')
    ask(m)
    expect(confirms(m) == ['Delete this book and its files?'] and not unlinks(m) and f'{BOOK_DIR}/.librivox' in m.fs and active(m) == BKEY and height(m) == layout(3)['h'],
           'while the thread is running: the download is told to stop and the files stay')
    m.thread, th = None, m.thread
    tick(m); row_tap(m, 3, 1)
    expect(not unlinks(m) and m.thread is None, 'the tick waits for the thread (no join on the UI thread); a tap on a part meanwhile does nothing')
    BKD.PCN.work(m, th)
    expect(active(m) == 0, 'the thread has ended')
    tick(m)
    expect(not [p for p in m.fs if p.startswith(BOOK_DIR)] and BOOK_DIR not in m.dirs and at_library(m), 'the next tick removes the files, the .part, the manifest and the folder and shows the Library')


def queue_tests(ctx):
    """A book that waits in the download queue: Waiting and the ring at step 0 on its Library row and in its header, Pause for the capsule and the sheet, a tap that queues, Delete Book of a waiting and of the running book."""
    expect = ctx.expect
    OTHER = 'Other'

    def lib_ring(m, title):
        """(ring cells, x of the grey line) of the Library row called title."""
        off = BKP.lib_off(m, 7)
        bl, tx, st, _ = PCP.paint(m, off)
        y = next(r[1] for (x, r), s in zip(tx, st) if x == title and s == 'label_row_title') - O['LIST_TITLE_Y']
        cells = [(b[1][0] // PX + (b[1][1] - O['PA_DSD_H']) // PX * O['PA_DL_COLS'], b[2][0]) for b in bl if tuple(b[2][2:]) == (PX, PX) and b[2][1] == y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] // 2 - PX // 2]
        sub = next(r for (x, r), s in zip(tx, st) if s == 'label_row_sub' and r[1] == y + O['LIST_SUB_Y'])
        return cells, sub[0]

    def sheet_rows(m): return [r for r, *_ in pod_ui.BK_SHEET_ROWS if flags(m, f'bk_sh_{r}') == (1, 1)]

    def ask(m):
        m.calls = []
        m.confirm_yes = True
        BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_delete')
    # the Library: the book that runs and the one behind it
    m = started()
    th = m.thread
    other_book(m)
    r, th2 = BKD.start(m, OTHER, run=False)
    BKP.click(m, 'btn_return')
    got = dict(rows(m, BKP.lib_off(m, 7)))
    expect(r == 0 and th2 is None and got[DIR] == 'Part 1 of 3' and got[OTHER] == pod_books.dl_lib_sub('queued', 0, 3) == 'Waiting', f'the Library: the running book says its part, the waiting one says Waiting ({got})')
    cells, x = lib_ring(m, OTHER)
    ring = pod_books.ring('queued')
    expect(ring == (0, 'arrow') and cells == [(0, O['LIST_TEXT_X']), (ARROW, O['LIST_TEXT_X'])] and x == O['LIST_TEXT_X'] + PX + GAP, f'the ring at step 0 (the queued episodes\' ring) before it, the line a ring and a gap right ({cells}, {x})')
    cells, x = lib_ring(m, DIR)
    expect(cells[0][0] == 0 and cells[1] == (STOP, O['LIST_TEXT_X']), 'the running book keeps its ring with the stop square')
    m.calls = []
    m.call(PSYMS['bk_awake_tick'], a0=0, count=2000000)
    expect([c for c in m.calls if c[0] == 'reset_poweroptions_timer'] == [('reset_poweroptions_timer', 1, 1, 0)], 'keep-awake holds while the thread lives: a book runs and another waits')
    # the waiting book's own level: Pause, the totals, no ring on a row; Pause Download in the sheet
    i = [t for t, s in rows(m, BKP.lib_off(m, 7))].index(OTHER)
    BKP.tap(m, 150, BKP.lib(m, 7)['row'](i) + 20, off=BKP.lib_off(m, 7))
    expect(hdr(m)[1] == ['Pause'] and hdr(m)[0] == [pod_books.line_text(3, 180, BYTES)] and not rings(m, 3), f'a waiting book with no part: the totals and the capsule Pause, no ring on a part ({hdr(m)})')
    BKP.click(m, 'btn_more')
    expect(sheet_rows(m) == ['speed', 'pause', 'delete'], f'the sheet offers Pause Download to a waiting book ({sheet_rows(m)})')
    BKP.click(m, 'bk_sh_pause')
    tick(m)
    expect(state_of(m, OTHER) == 0 and hdr(m)[1] == ['Resume'] and BKD.result(m, OTHER) == (BKD.R_PAUSED, 0) and active(m) == BKEY, 'Pause Download of a waiting book: it leaves the queue, the capsule says Resume, the running book goes on')
    m.thread = None
    BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_resume')
    expect(m.thread is None and state_of(m, OTHER) == 2 and hdr(m)[1] == ['Pause'], 'Resume Download of it while another runs: it waits again, no toast, no thread')
    BKD.PCN.work(m, th)
    tick(m)
    expect(BKD.result(m, DIR) == (BKD.R_DONE, 0) and BKD.result(m, OTHER) == (BKD.R_DONE, 0) and active(m) == 0 and hdr(m)[1] == ['Play'], 'one run of the thread fetches both; the page followed (Play for the first part)')
    # a book with parts on the card that waits: "Waiting · 1 of 3 parts downloaded"
    m = started(book_site(lambda n_, st, o: {'code': 404} if n_ == 'b_02.mp3' else None))
    ended(m)
    other_book(m)
    r, th_o = BKD.start(m, OTHER, run=False)
    m.thread = None
    BKP.click(m, 'btn_more'); BKP.click(m, 'bk_sh_resume')
    tick(m)
    expect(m.thread is None and state_of(m, DIR) == 2 and hdr(m)[0] == [pod_books.dl_head('queued', present=1, total=3)] == ['Waiting · 1 of 3 parts downloaded'] and hdr(m)[1] == ['Play'],
           f'a book with a part on the card, waiting: "Waiting · 1 of 3 parts downloaded", the capsule stays Play ({hdr(m)})')
    BKP.click(m, 'btn_more')
    expect(sheet_rows(m) == ['speed', 'pause', 'delete'], 'Pause Download in its sheet')
    BKP.click(m, 'bk_sh_scrim')
    # Delete Book of a waiting book: it leaves the queue and the files go at once
    ask(m)
    expect(confirms(m) == ['Delete this book and its files?'] and not [p for p in m.fs if p.startswith(BOOK_DIR)] and state_of(m, DIR) == 0 and at_library(m) and active(m) == BKD.key_of(OTHER),
           'Delete Book of a waiting book: out of the queue and deleted at once (nothing holds its files); the running book goes on')
    BKD.PCN.work(m, th_o)
    expect(BKD.result(m, OTHER)[0] == BKD.R_FAILED and active(m) == 0, 'and the queue is done (the second book meets the same missing part: its own failure)')
    # Delete Book of the running book with another waiting: stopped, the files go when it has let go, the queue goes on
    m = started()
    th = m.thread
    other_book(m)
    BKD.start(m, OTHER, run=False)
    ask(m)
    expect(not unlinks(m) and f'{BOOK_DIR}/.librivox' in m.fs and active(m) == BKEY and state_of(m, OTHER) == 2, 'the running book: stopped, the files stay until it has let go')
    BKD.PCN.work(m, th)
    tick(m)
    expect(not [p for p in m.fs if p.startswith(BOOK_DIR)] and BKD.result(m, OTHER) == (BKD.R_DONE, 0) and active(m) == 0 and at_library(m), 'the thread went on to the next book; the tick deleted the files of the first')
    # the retry wait of the running book is not the queue's Waiting
    m = started()
    other_book(m)
    BKD.start(m, OTHER, run=False)
    step(m, wait=1)
    tick(m)
    BKP.click(m, 'btn_return')
    cells, x = lib_ring(m, DIR)
    expect(dict(rows(m, BKP.lib_off(m, 7)))[DIR] == 'Part 1 of 3' and cells == [(0, O['LIST_TEXT_X']), (ARROW, O['LIST_TEXT_X'])], 'the running book that sleeps before a retry keeps its own line')


def awake_tests(ctx):
    """The keep-awake timer: stock's power timers are set again while a download runs, not otherwise, also behind another page and with the screen off."""
    expect = ctx.expect
    def awake(m):
        m.calls = []
        m.call(PSYMS['bk_awake_tick'], a0=0, count=2000000)
        return [c for c in m.calls if c[0] == 'reset_poweroptions_timer']
    m = started()
    got = awake(m)
    expect(got == [('reset_poweroptions_timer', 1, 1, 0)], f'a download runs: the standby and power-off countdowns are set again ({got})')
    BKP.fire(m, 'EVT_WINDOW_TO_BG')
    m.screen(False)
    expect(len(awake(m)) == 1, 'behind another page and with the screen off it still does')
    m.screen(True)
    ended(m)
    expect(awake(m) == [], 'no download: nothing is touched')
    m = opened(book_site())
    expect(awake(m) == [], 'a page with nothing to download does not touch them')
    # an episode download of Podcasts alone does not hold the timer (its page does that); a book download does, beside it
    m = opened(book_site())
    BKD.PCN.sub(m, 'Show', 'https://feeds.example/show', title='Show', checked=1)
    m.put(f'{BKD.DL.SHOW}/.episodes', BKD.DL.eps_text(BKD.DL.entries()))
    m.thread = None
    m.call(PSYMS['pn_dl_add'], a0=m.cstr(BKD.DL.RP), a1=m.cstr('Show'), a2=m.cstr('a.mp3'), count=1 << 40)
    expect(m.thread and m.call(PSYMS['pn_dl_running'], count=2000000) == 1 and awake(m) == [], 'only a Podcasts episode downloads: the book page does not hold the timer')


def width_tests(ctx):
    """The new words fit their places in every language: the Library row's grey line, the status lines, the field's hint, the capsule's Open Book, a running time in a part's line."""
    expect = ctx.expect
    f = font()
    over = []
    for loc in pod_i18n.LOCALES:
        t = lambda k: pod_i18n.TEXT[k][loc]
        fill = lambda k, *a: t(k).replace('%d', '{}').format(*a)
        if f.width(t('LibriVox'), 21) > O['PP_DL_TEXT_W']: over.append((loc, 'LibriVox', 'Library row title'))
        if f.width(t('Public domain audiobooks'), 18) > O['PP_DL_TEXT_W']: over.append((loc, 'Public domain audiobooks', 'Library row grey line'))
        if f.width(t('Public domain audiobooks'), 15) > 320 - 2 * O['PP_LINE_X']: over.append((loc, 'Public domain audiobooks', 'grey line under the large title'))
        if f.width(t('LibriVox'), O['PP_TITLE_PX']) > O['SG_TITLE_W']: over.append((loc, 'LibriVox', 'large title'))
        for k in ('Books', 'Discover', 'Popular'):
            if f.width(t(k), pod_ui.SECTION_PX) > 320 - 2 * O['PP_SHOWS_X']: over.append((loc, k, 'section header'))
        if f.width(t('Search LibriVox'), 18) > O['PQ_TEXT_W']: over.append((loc, 'Search LibriVox', 'field'))
        for k in ('Loading…', 'No results'):
            if f.width(t(k), 20) > 3 * (320 - 2 * O['PP_LINE_X'] - O['PS_SPIN_PX'] - O['PS_SPIN_GAP']): over.append((loc, k, 'status line (three lines)'))
        for k in ('Queue is full', 'This book is playing'):
            if f.width(t(k), 18) > 300: over.append((loc, k, 'toast'))
        if f.width(t('Delete this book and its files?'), 18) > max(f.width(pod_i18n.TEXT[k][loc], 18) for k in ('Unsubscribe from this show?', 'Remove the selected downloads?', 'Delete the selected episodes?', 'Unsubscribe from these shows?')) + 1:
            over.append((loc, 'Delete this book and its files?', 'confirm (no longer than the longest confirm of the pages)'))
        for k in ('Playback Speed', 'Pause Download', 'Resume Download', 'Delete Book'):
            if f.width(t(k), 18) > O['PS_SHEET_VALUE_R'] - O['PS_SHEET_TEXT_X'] - (60 if k == 'Playback Speed' else 0): over.append((loc, k, 'sheet row (Playback Speed leaves room for its value)'))
        for k in ('Download', 'Open Book', 'Pause', 'Resume', 'Retry'):
            if f.width(t(k), 18) > BK['BK_PLAY_W'] - 16: over.append((loc, k, 'capsule'))
        for w in (fill('%d parts', 300) + ' · ' + fill('%dm', 9999) + ' · ' + '999 MB', fill('%dm', 9999) + ' · 1.9 GB', fill('%dm', 59), fill('%d parts', 300) + ' · ' + fill('%dh %dm', 99, 59) + ' · ' + '999 MB', fill('%d parts', 300) + ' · ' + fill('%dh', 99) + ' · ' + '1.9 GB'):
            if f.width(w, 15) > BK['BK_NAME_W']: over.append((loc, w, 'preview line'))
        if f.width(fill('%dm', 999) + ' · 99 MB', 18) > BK['BK_PART_W']: over.append((loc, 'part line', 'part'))
        # a part that is not on the card: its grey line with the ring in front of it (the part being fetched: its percent, a size, Waiting, or why the last try failed), and the header's line of a book with parts on the card
        ring = PX + GAP
        for w in ('100%', fill('%d MB', 9999), t('Waiting'), fill('%dm', 999) + ' · 999 MB'):
            if f.width(w, 18) > BK['BK_PART_W'] - ring: over.append((loc, w, 'part line with its ring'))
        for k in ('No Wi-Fi', 'Set the date first', 'Certificates missing', 'Certificate problem', "Can't connect", 'Server error', 'Storage unavailable', 'Queue is full', 'Not enough memory'):
            if f.width(t('Failed') + ': ' + t(k), 18) > BK['BK_PART_W']: over.append((loc, k, 'Failed: <why> in a part line'))
            if f.width(t('Failed') + ': ' + t(k), 15) > BK['BK_NAME_W']: over.append((loc, k, 'Failed: <why> in the header'))
        for w in (t('Downloading') + ' · ' + fill('Part %d of %d', 300, 300), t('Waiting') + ' · ' + fill('Part %d of %d', 300, 300), fill('%d of %d parts downloaded', 300, 300), t('Waiting') + ' · ' + fill('%d of %d parts downloaded', 99, 99)):
            if f.width(w, 15) > BK['BK_NAME_W']: over.append((loc, w, 'header line'))
        if f.width(fill('Part %d of %d', 99, 99), 18) > O['LIST_TEXT_W_CHEV'] - PX - GAP: over.append((loc, 'Part 99 of 99', 'Library line (after the ring)'))
        if f.width(fill('%d of %d parts downloaded', 12, 37), 18) > O['LIST_TEXT_W_CHEV']: over.append((loc, '12 of 37 parts downloaded', 'Library line'))   # (a longer count is cut with an ellipsis)
    expect(not over, f'every new text fits its place in the 13 languages: {over}')
    expect(all(pod_books.len_text(s_) == w for s_, w in ((47160, '786m'), (1080, '18m'), (20, '1m'), (3570, '60m'), (60, '1m'), (61, '2m'))) and pod_books.left_text(1320) == '22m left', 'the model\'s times are Podcasts\' ("19m", "22m left": minutes rounded up)')
    cases = ((37, 47160, 380 << 20), (2, 66480, 344 << 20), (1, 7200, 0), (1, 3541, 5 << 20), (3, 3599, 0), (0, 66480, 9 << 20), (0, 1140, 9 << 20), (300, 359940, 0), (2, 3600, 0), (2, 3601, 0))
    expect(pod_books.line_text(37, 47160, 380 << 20) == '37 parts · 13h 6m · 380 MB' and pod_books.line_text(1, 0, 0) == '' and pod_books.line_text(0, 90, 5 << 20) == '2m · 5 MB' and pod_books.line_text(0, 66480, 0) == '1108m'
           and pod_books.line_text(1, 7200, 0) == '2h' and pod_books.line_text(3, 3540, 0) == '3 parts · 59m' and pod_books.line_text(2, 66480, 344 << 20) == '2 parts · 18h 28m · 344 MB' and pod_books.line_text(2, 3601, 0) == '2 parts · 1h 1m',
           'the model\'s lines: a whole book from an hour reads hours and minutes ("18h 28m", "2h"), a part stays in minutes')
    m = opened(archive([]))
    out = m.alloc(96)
    got = []
    for parts, secs, nbytes in cases:
        m.setword(STACK + 16, nbytes)
        m.call(PSYMS['bf_line'], a0=out, a1=96, a2=parts, a3=secs, count=20000000)
        got.append((fixed(m.read_cstr(out)), pod_books.line_text(parts, secs, nbytes)))
    expect(all(a == b for a, b in got), f'the payload\'s bf_line says what the model says (hours for a whole book, minutes for a part): {[g for g in got if g[0] != g[1]]}')

SECTIONS = [library_tests, collapse_tests, popular_tests, status_tests, search_tests, busy_tests, leave_tests, preview_tests, download_tests, row_tests, fail_tests, follow_tests, library_row_tests, sheet_tests, delete_tests, queue_tests, awake_tests, width_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
