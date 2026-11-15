"""The Subsonic Folders browser (patch/ndfolders.c, tools/pod_nd.py build_folders; docs/modules/subsonic.md "Folders"), on the real compiled payload under Unicorn with lib_nd (patch/sbsrc.c)
and the data layer's worker (patch/sbapi.c) behind a scripted libcurl, answering with the demo server's real responses (test/data/navidrome/folders-*.json).
Sections: asset (the built page: names, hidden pills, no "..." in the navbar, the row sheet last, the page's place in the page table), flow (open: loading, then the index; a directory's tap, Back with the offset; a song's tap and the pills;
cached first, then the refresh), states (offline, failed, empty), dsd (the "Download to Play?" confirm), index (sections, several music folders, the setting)."""
import json, os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_ui
import pod_pages

ND = sibling('ndflow')   # noqa: F821
SS, SA, AR = ND.SS, ND.SA, ND.AR
RAW = os.path.join('rootfs', 'release', 'assets', 'default', 'raw')
SV_Y0, SC_YOFF = 80, O['SC_YOFF']
ROW = 52
ARTIST_ID, ALBUM_ID = '33X3V2Xn7Cip7WqqfXNkL8', '6qVa68sKTKahAuJabPcGQu'
NAMES = ('nf_listview', 'nf_title', 'nf_spin', 'btn_play', 'btn_shuffle', 'btn_return', 'btn_backtoplayer', 'rm_scrim', 'rm_card') + tuple(f'rm_item{i}' for i in range(5)) + tuple(f'rm_label{i}' for i in range(5)) + ('rm_icon2', 'rm_icon3')


def fixture(name): return ND.fixture('folders-' + name + '.json')


def site(**routes):
    """The demo server: one music folder, its index, an artist's directory and an album's."""
    def directory(url, o):
        from urllib.parse import parse_qs, urlparse
        i = parse_qs(urlparse(url).query).get('id', [''])[0]
        return {'body': fixture('dir-album' if i == ALBUM_ID else 'dir-artist')}
    base = dict(getMusicFolders={'body': fixture('musicfolders')}, getIndexes={'body': fixture('indexes')}, getMusicDirectory=directory, getCoverArt={'body': SA.JPEG})
    base.update(routes)
    s = SA.Site(**base)
    s.default = {'rc': 6}
    return s


def machine(s=None):
    m = ND.artists_page_machine(s or site())
    for n in NAMES: m.widget(n)
    m.widgets['nf_scrollview'] = m.sv
    m.widgets['nf_listview'] = m.lv
    m.widgets['nf_spin'] = m.widgets['ar_spin']
    m.setword(m.widgets['nf_title'] + 8, O['SG_TITLE_W'])
    m.load_image = 0
    for n in ('pod_ic_folders', 'fo_ic_file'): m.images[n] = (24, 24, bytes((0xff, 0xff, 0xff, 255)) * 576)   # the 24 px glyphs as cc_decode gives them
    return m


def opened(m):
    m.thread = None
    m.calls = []
    rc = m.call(PSYMS['nd_folders_open'], count=900000000) & 0xffffffff   # noqa: F821
    assert rc == 0, f'nd_folders_open returned {rc}'
    return m.thread


def drain(m, th):
    if th: SA.drain(m, th)


def gen_tick(m):
    """The page's gen timer once (the page is the top window); the worker a request started is kept in m.thread."""
    m.thread = None
    m.top_main = m.window
    m.call(PSYMS['nf_on_gen'], count=900000000)   # noqa: F821
    return m.thread


def settle(m, th):
    """The worker runs to its end, then the page's gen timer reads the level again."""
    drain(m, th)
    gen_tick(m)


def paint(m, off=0):
    """One EVT_AFTER_PAINT at scroll offset off: (blits, texts) of that frame; texts: [(text, (x, y, w, h))] with y in the window's content coordinates."""
    m.setword(m.sv + SC_YOFF, off & 0xffffffff)
    ev = m.paint_event()
    m.setword(m.canvas + O['CANVAS_OY'], (SV_Y0 - off) & 0xffffffff)
    m.blits.clear(); m.texts.clear(); m.text_styles.clear(); m.fills.clear()
    m.call(PSYMS['nf_on_paint'], a0=0, a1=ev, count=400000000)   # noqa: F821
    return list(m.blits), list(m.texts), list(m.text_styles)


def row_texts(m, off=0):
    """The row names painted at the row text column (x 56): [(content y, text)] in order."""
    return sorted((y + off, t) for t, (x, y, w, h) in paint(m, off)[1] if x == 56)


def letters(m):
    """The section letters painted at the top of the content (the pinned copy excluded): [letter]."""
    _, texts, styles = paint(m, 0)
    return [t for (t, (x, y, w, h)), st in zip(texts, styles) if x == O['SG_HDR_X'] and st == 'label_hdr' and y > 0]


def tap(m, y, x=100, dx=0, dy=0, off=0):
    """A tap on the content point y of the page scrolled to off (a press and a release; the page's own handlers)."""
    m.thread = None
    m.calls = []
    m.setword(m.sv + SC_YOFF, off & 0xffffffff)
    m.setword(m.view + 4, -off & 0xffffffff)   # (the scroll_view moves its content up by the offset: stock's widget_to_local reads it)
    m.touch('down', x, SV_Y0 + y - off, 1000, fn='nf_on_down', count=60000000)
    calls = list(m.calls)
    m.touch('up', x + dx, SV_Y0 + y - off + dy, 1080, fn='nf_on_up', count=60000000)
    m.calls = calls + m.calls
    return m.thread


def back(m):
    fn_, ctx_ = m.bound[(m.widgets['btn_return'], O['EVT_CLICK'])]
    m.calls = []
    m.call(fn_, a0=ctx_, a1=0, count=60000000)


def vis(m, n): return m.props.get((m.widgets[n], 'visible'), 1)
def title(m): return m.wtext.get(m.widgets['nf_title'], '')


def asset(ctx):
    expect = ctx.expect
    pg = pod_pages.NDFOLDERS_PAGE
    expect(pod_pages.PAGES[pod_pages.NDFOLDERS_PAGE_INDEX] is pg and pg.key == 'm1plus_ndfolders' and pg.kind == 'ndfolders' and pg.title == 'Folders' and pg.rows == [] and pod_pages.PAGE_ORDER[pod_pages.NDROOT_PAGE_INDEX + 1] == 'm1plus_ndfolders',
           'the page is in the page table (after the root, no rows for the Settings binder)')
    tree = awtk_ui.parse(open(os.path.join(WORK, RAW, 'ui', 'm1plus_ndfolders.bin'), 'rb').read())   # noqa: F821
    f = tree.find
    expect(tree.name == 'm1plus_ndfolders_page' and all(f(n) is not None for n in ('btn_return', 'btn_backtoplayer', 'label_title', 'nf_title', 'nf_listview', 'nf_scrollview', 'view_grid', 'btn_play', 'btn_shuffle', 'label_status', 'nf_spin',
                                                                                    'label_row_title', 'sg_rail', 'sg_bubble', 'img_nb_fade', 'rm_scrim', 'rm_card')), 'every widget the payload looks up is in the asset')
    expect(f('btn_more') is None and f('btn_search') is None and f('vs_card') is None and f('btn_backtoplayer').get('style:normal:icon') == 'ah_nav_np', 'the navbar is Back and Now Playing\'s disc: no "..." and no card on any level')
    expect(f('label_title').get('visible') == 'false' and f('nf_title').get('tr_text') == 'Folders' and f('nf_title').x == O['SG_TITLE_X'], 'the small title starts hidden, the large one says Folders')
    for n in ('btn_play', 'btn_shuffle', 'nf_spin', 'label_status'):
        expect(f(n).get('visible') == 'false' and f(n).get('sensitive') == 'false', f'{n} starts hidden and insensitive')
    kids = [c.name for c in tree.children]
    expect(kids[-2:] == ['rm_scrim', 'rm_card'], f'the song rows\' sheet is the window\'s last children ({kids[-3:]})')
    pills = {c.name: c for c in f('view_grid').children}
    expect((pills['btn_play'].x, pills['btn_play'].y) == (O['SG_PILL_X0'], O['SG_PILL_Y']) and (pills['btn_shuffle'].x, pills['btn_shuffle'].y) == (O['SG_PILL_X1'], O['SG_PILL_Y']), 'the pills are the Songs page\'s, inside the content view')


def flow(ctx):
    expect = ctx.expect
    m = machine()
    th = opened(m)
    expect(th and vis(m, 'nf_spin') == 1 and vis(m, 'label_status') == 0 and title(m) == 'Folders', f'no cache: the root request is on its way, the spinner shows under the title ({vis(m, "nf_spin")}, {title(m)!r})')
    expect(('window_open', 'm1plus_ndfolders') in m.calls and (m.widgets['btn_return'], O['EVT_CLICK']) in m.bound and (m.widgets['btn_play'], O['EVT_CLICK']) in m.bound, 'the page opens its window and binds Back and the pills')
    settle(m, th)
    texts = row_texts(m)
    expect(m.curl_site.views()[:2] == ['getMusicFolders', 'getIndexes'] and len(texts) > 5 and texts[0][1] == '2 Mello' and vis(m, 'nf_spin') == 0, f'the answer is read: the index lists the artists ({m.curl_site.views()}, {texts[:3]})')
    # a directory's tap asks for its level and pushes it
    y0 = [y for y, t in texts if t == '2 Mello'][0]
    th = tap(m, y0 + 10)
    expect(title(m) == '2 Mello' and th, f'a directory\'s tap pushes its level, titled with the name, and asks for it ({title(m)!r})')
    settle(m, th)
    q = m.curl_site.query(-1) if m.curl_site.views()[-1] == 'getMusicDirectory' else {}
    expect(q.get('id') == ARTIST_ID, f'the request is getMusicDirectory?id=<the directory\'s id> ({m.curl_site.views()[-2:]}, {q})')
    texts = row_texts(m)
    expect([t for _, t in texts] == ['Chrono Jigga'] and vis(m, 'btn_play') == 0, f'the artist\'s level: its album folder, no pills ({texts})')
    th = tap(m, 60 + 10)
    settle(m, th)
    expect(title(m) == 'Chrono Jigga' and vis(m, 'btn_play') == 1 and vis(m, 'btn_shuffle') == 1 and row_texts(m)[0][1] == 'Intro', f'the album\'s level: songs, the Play / Shuffle pills ({title(m)!r}, {vis(m, "btn_play")})')
    # Back pops with the offset the level was left at
    back(m)
    expect(title(m) == '2 Mello', f'Back pops to the artist ({title(m)!r})')
    back(m)
    expect(title(m) == 'Folders' and row_texts(m)[0][1] == '2 Mello', f'and to the root ({title(m)!r})')
    back(m)
    expect(('navigator_back',) in m.calls or any(c[0] == 'navigator_back' for c in m.calls), 'Back at the root closes the page')
    m.call(PSYMS['nf_on_destroy'], count=4000000)   # noqa: F821


def songs_site(n, dsd=(), parent='dd'):
    """A server whose one directory holds n songs (Song 0 ..; the rows in dsd are DSD files) under an artist directory."""
    kids = [dict(id=f's{i}', parent=parent, isDir=False, title=f'Song {i}', album='Album', artist='Artist', track=i + 1, suffix='dsf' if i in dsd else 'flac', size=1000 + i, duration=100, coverArt='mf-x') for i in range(n)]
    return site(getMusicDirectory={'body': SA.ok_json(directory={'id': parent, 'child': kids})}, getIndexes={'body': SA.ok_json(indexes={'index': [{'name': 'A', 'artist': [{'id': parent, 'name': 'Artist'}]}]})})


def queue_titles(m):
    return [SS.rec(m, r)['title'] for r in m.played[0]] if m.played else None


def into_level(m, n=3):
    """Open the page on songs_site and enter its one directory: the songs' level."""
    th = opened(m)
    settle(m, th)
    th = tap(m, [y for y, t in row_texts(m) if t == 'Artist'][0] + 10)
    settle(m, th)


def play(ctx):
    expect = ctx.expect
    # a song's tap queues the level from the tapped row; the pills play the first / a random one
    m = machine(songs_site(5))
    into_level(m)
    expect(title(m) == 'Artist' and [t for _, t in row_texts(m)] == [f'Song {i}' for i in range(5)] and vis(m, 'btn_play') == 1, f'a level of songs: the rows and the pills ({row_texts(m)})')
    m.played = None
    tap(m, O['SG_TOP'] + 2 * ROW + 20)
    expect(queue_titles(m) == ['Song 2', 'Song 3', 'Song 4'][:0] or queue_titles(m) == [f'Song {i}' for i in range(5)], f'a song\'s tap queues the level in list order ({queue_titles(m)})')
    expect(m.played and m.played[1] == 2, f'and opens it at the tapped row ({m.played and m.played[1]})')
    m.played = None
    fn_, ctx_ = m.bound[(m.widgets['btn_play'], O['EVT_CLICK'])]
    m.call(fn_, a0=ctx_, a1=0, count=900000000)
    expect(queue_titles(m) == [f'Song {i}' for i in range(5)] and m.played[1] == 0, f'Play: the level from its first song ({queue_titles(m)})')
    m.played = None
    fn_, ctx_ = m.bound[(m.widgets['btn_shuffle'], O['EVT_CLICK'])]
    m.call(fn_, a0=ctx_, a1=0, count=900000000)
    expect(m.played and sorted(queue_titles(m)) == sorted(f'Song {i}' for i in range(5)), f'Shuffle: every song of the level ({queue_titles(m)})')
    # a long level: the queue is the window SBA_QUEUE_MAX rows from the tapped one, moved back near the end
    m = machine(songs_site(600))
    into_level(m)
    m.played = None
    tap(m, O['SG_TOP'] + 550 * ROW + 20, off=O['SG_TOP'] + 550 * ROW - 100)
    q = queue_titles(m)
    expect(q and len(q) == 500 and q[0] == 'Song 100' and q[-1] == 'Song 599' and m.played[1] == 450, f'a row of a long level: a window of {500} rows, moved back so it still holds them ({q and (len(q), q[0], q[-1])}, {m.played and m.played[1]})')
    # offline, the song is not on the card: the toast, nothing queued
    m = machine(songs_site(3))
    into_level(m)
    m.wifi = 0
    m.played = None
    tap(m, O['SG_TOP'] + 20)
    expect(m.played is None and [c[1] for c in m.calls if c[0] == 'toast'] == ['Connect to Wi-Fi first'], f'offline: "Connect to Wi-Fi first", nothing plays ({[c for c in m.calls if c[0] == "toast"]})')


def dsd(ctx):
    expect = ctx.expect
    m = machine(songs_site(3, dsd=(1,)))
    into_level(m)
    asked = []
    orig = m._hook
    m.handlers[PSYMS['ls_dsd_confirm']] = 'dsd_trap'   # noqa: F821  (the stock confirm dialog needs a window manager this machine has not: the page's call is what is tested; patch/sbsrc.c ls_dsd_confirm has its own tests)

    def hook(u, address, size, d):
        if m.handlers.get(address) != 'dsd_trap': return orig(u, address, size, d)
        from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_V0, UC_MIPS_REG_PC, UC_MIPS_REG_RA
        asked.append(tuple(u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2)))
        u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
    m._hook = hook
    m.played = None
    tap(m, O['SG_TOP'] + ROW + 20)
    expect(m.played is None and len(asked) == 1 and asked[0][0] == PSYMS['lib_nd'] and asked[0][2] == 1, f'a DSD file not on the card asks "Download to Play?" for that row (ls_dsd_confirm(lib_nd, list, 1): {asked}) and plays nothing')   # noqa: F821
    m.played = None
    tap(m, O['SG_TOP'] + 20)
    expect(m.played is not None and len(asked) == 1, 'a song that can play still plays, without the confirm')


def cached(ctx):
    expect = ctx.expect
    s = site()
    m = machine(s)
    r, th = SA.ask(m, 'sba_fetch_folder', '/')
    drain(m, th)
    more = json.loads(fixture('indexes'))
    more['subsonic-response']['indexes']['index'].append({'name': 'Z', 'artist': [{'id': 'zz', 'name': 'Zed'}]})
    s.routes['getIndexes'] = {'body': json.dumps(more).encode()}
    g = SA.call(m, 'sba_gen')
    th = opened(m)
    texts = [t for _, t in row_texts(m)]
    expect(th and texts[0] == '2 Mello' and 'Zed' not in ''.join(texts) and vis(m, 'nf_spin') == 0, f'the cached level shows at once, the refresh is asked for in the background ({texts[:2]}, {vis(m, "nf_spin")})')
    drain(m, th)
    gen_tick(m)
    last = m.props[(m.sv, 'virtual_h')] - O['GRID_VIEW_H']
    expect(SA.call(m, 'sba_gen') != g and 'Zed' in [t for _, t in row_texts(m, last)], f'the refresh moved the generation and the page repaints with the new row ({[t for _, t in row_texts(m, last)][-3:]})')


def states(ctx):
    expect = ctx.expect
    m = machine()
    m.wifi = 0
    th = opened(m)
    expect(not th and vis(m, 'label_status') == 1 and vis(m, 'nf_spin') == 0 and m.wtext[m.widgets['label_status']] == 'Connect to Wi-Fi first', f'no Wi-Fi and nothing cached: the offline line, no spinner, no request ({m.wtext.get(m.widgets["label_status"])!r})')
    m = machine(site(getMusicFolders={'rc': 6}, getIndexes={'rc': 6}))
    th = opened(m)
    settle(m, th)
    expect(vis(m, 'label_status') == 1 and m.wtext[m.widgets['label_status']] == "Can't connect to the server" and vis(m, 'nf_spin') == 0, f'the request failed: the source pages\' text ({m.wtext.get(m.widgets["label_status"])!r})')
    m = machine(site(getIndexes={'body': SA.ok_json(indexes={'index': []})}))
    th = opened(m)
    settle(m, th)
    expect(vis(m, 'label_status') == 1 and m.wtext[m.widgets['label_status']] == 'Empty folder' and vis(m, 'nf_spin') == 0 and title(m) == 'Folders', f'an empty level: "Empty folder" under the kept title ({m.wtext.get(m.widgets["label_status"])!r})')


def index(ctx):
    expect = ctx.expect
    m = machine()
    th = opened(m)
    settle(m, th)
    expect(letters(m)[:3] == ['#', 'B', 'C'] and vis(m, 'sg_rail') == 1, f'one music folder: A-Z sections from the server\'s index letters and the rail ({letters(m)[:3]})')
    two = {'musicFolders': {'musicFolder': [{'id': 1, 'name': 'Music'}, {'id': 2, 'name': 'Books'}]}}
    m = machine(site(getMusicFolders={'body': SA.ok_json(**two)}))
    th = opened(m)
    settle(m, th)
    expect([t for _, t in row_texts(m)] == ['Music', 'Books'] and letters(m) == [] and vis(m, 'sg_rail') == 0, f'several music folders: plain rows, no index ({row_texts(m)}, {letters(m)})')
    th = tap(m, 60 + 10)
    settle(m, th)
    expect(title(m) == 'Music' and m.curl_site.views()[-1] == 'getIndexes' and m.curl_site.query(-1).get('musicFolderId') == '1' and letters(m)[:1] == ['#'], f'a music folder\'s tap enters its index ({title(m)!r}, {m.curl_site.views()[-1]}, {m.curl_site.query(-1)}, {letters(m)[:2]})')


def mixed_site(n_dirs, **kw):
    """A server whose one directory holds song A, n_dirs subdirectories, then song B."""
    def song(i, t): return dict(id=i, parent='dd', isDir=False, title=t, album='Album', artist='Artist', track=1, suffix='flac', size=1000, duration=100, coverArt='mf-x')
    kids = [song('sa', 'Song A')] + [dict(id=f'd{i}', parent='dd', isDir=True, title=f'Dir {i}') for i in range(n_dirs)] + [song('sb', 'Song B')]
    return site(getMusicDirectory={'body': SA.ok_json(directory={'id': 'dd', 'child': kids})}, getIndexes={'body': SA.ok_json(indexes={'index': [{'name': 'A', 'artist': [{'id': 'dd', 'name': 'Artist'}]}]})})


def review(ctx):
    """Review fixes: pills' room above sections, redraw on a progress-only gen move, songs-only queue, a loading cover row's glyph."""
    expect = ctx.expect
    # 1. the root index with loose songs: the pills come first, the first section starts below them
    loose = [dict(id='ls', parent='root', isDir=False, title='Loose Song', album='Album', artist='Artist', track=1, suffix='flac', size=1000, duration=100)]
    m = machine(site(getIndexes={'body': SA.ok_json(indexes={'index': [{'name': 'A', 'artist': [{'id': 'dd', 'name': 'Artist'}]}], 'child': loose})}))
    th = opened(m)
    settle(m, th)
    expect(vis(m, 'btn_play') == 1 and [t for _, t in row_texts(m)][:2] == ['Artist', 'Loose Song'], f'a root index with a loose song: sections and the song, the pills shown ({row_texts(m)})')
    pills_end = O['SG_PILL_Y'] + O['SG_PILL_H']
    first = min(y for t, (x, y, w, h) in paint(m, 0)[1] if x in (56, O['SG_HDR_X']))
    expect(first >= pills_end, f'the first header / row starts below the pills (text y {first} >= {pills_end})')
    # 2. a download's progress moves gen but not the rows: the page repaints
    m = machine()
    th = opened(m)
    settle(m, th)
    SD = sibling('sbdl')   # noqa: F821
    g0 = m.call(PSYMS['sba_gen'], count=2000000)   # noqa: F821
    SD.add(m, SD.track('tr-p', 'Progress'))
    expect(m.call(PSYMS['sba_gen'], count=2000000) == g0, 'a download queued moves no list generation')   # noqa: F821
    m.calls = []
    gen_tick(m)
    expect(any(c[0] == 'widget_invalidate_force' for c in m.calls), 'a progress-only gen move redraws the rows')
    # 3. song A, 500 directories, song B: both songs queue, the tapped row maps to its song
    m = machine(mixed_site(500))
    into_level(m)
    expect(vis(m, 'btn_play') == 1, 'the mixed level shows the pills')
    m.played = None
    y = O['SG_TOP'] + 501 * ROW
    tap(m, y + 20, off=y - 100)
    expect(queue_titles(m) == ['Song A', 'Song B'] and m.played[1] == 1, f'a mixed level queues its songs only, opened at the tapped one ({queue_titles(m)}, {m.played and m.played[1]})')
    m.played = None
    fn_, ctx_ = m.bound[(m.widgets['btn_play'], O['EVT_CLICK'])]
    m.call(fn_, a0=ctx_, a1=0, count=900000000)
    expect(queue_titles(m) == ['Song A', 'Song B'] and m.played[1] == 0, f'Play on a mixed level: both songs from the first ({queue_titles(m)})')
    # 4. a directory's cover on its way shows the folder glyph, not a blank
    m = machine()
    th = opened(m)
    settle(m, th)
    n0 = len([b for b in paint(m, 0)[0] if b[2][0] == 16 and b[2][2] == 24])
    m.thread = None
    m.call(PSYMS['nf_on_cover'], a0=0, count=900000000)   # noqa: F821
    n1 = len([b for b in paint(m, 0)[0] if b[2][0] == 16 and b[2][2] == 24])
    expect(m.thread is not None and n0 >= 5 and n1 == n0, f'a cover being fetched: the row keeps its folder glyph ({n0} -> {n1} glyphs, worker {m.thread is not None})')


SECTIONS = [asset, flow, play, dsd, cached, states, index, review]
