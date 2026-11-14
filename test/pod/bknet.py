"""Audiobooks, the LibriVox catalog (patch/bknet.c, patch/bknet.h, patch/pcjson.c pj_records / pj_object, docs/modules/audiobooks.md "LibriVox"): the query builder, the docs parser of the Internet
Archive's advancedsearch answer, the files scanner (a metadata/<id>/files answer read from a file in chunks, object by object), and the catalog and preview jobs in pcnet.c's one worker slot against a scripted
libcurl (the request addresses, the thumbnails, the held popular list, every failure, Cancel, the single-thread rule). The compiled payload runs under Unicorn; the card is a dict of paths."""
import json, os, random, re
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'test', 'data', 'librivox')

SE = sibling('pcsearch')
PCN = SE.PCN
PN = dict(SE.PN, NOBOOK=21)
fn = SE.fn


def defs(*names):
    out = {}
    for name in names:
        for line in open(os.path.join(ROOT, 'patch', name)).read().replace('\\\n', ' ').splitlines():
            mm = re.match(r'#define\s+(\w+)\s+(.+?)\s*(?:/\*.*)?$', line.strip())
            if mm and (v := mm.group(2).strip()):
                try: out[mm.group(1)] = v.strip('"') if v.startswith('"') else eval(re.sub(r'(?<=\d)[uU]\b', '', v), {}, out)   # noqa: S307 (this repo's own headers: numbers and strings)
                except Exception: pass   # noqa: S110
    return out


D = defs('books.h', 'bknet.h')
ROWS, ID, AUTHOR, TERM, CAP, OBJ = D['BN_ROWS'], D['BN_ID'], D['BN_AUTHOR'], D['BN_TERM'], D['BN_FILES_CAP'], D['BN_OBJ']
TITLE, FILE, MAXP, DIR = D['BK_TITLE'], D['BK_FILE'], D['BK_MAX_PARTS'], D['BN_DIR']
FILES = DIR + '/files.json'
ROW, PART = ID + TITLE + AUTHOR + 4, FILE + TITLE + 8
HOST = 'https://archive.org'
SEARCH_TAIL = '&fl[]=identifier&fl[]=title&fl[]=creator&fl[]=runtime&sort[]=downloads+desc&rows=25&output=json'
POPULAR = HOST + '/advancedsearch.php?q=collection%3Alibrivoxaudio' + SEARCH_TAIL
PRIDE = 'pride_and_prejudice_librivox'
FILES_URL = f'{HOST}/metadata/{PRIDE}/files'
IMG = HOST + '/services/img/'
SEARCH_RAW = open(os.path.join(DATA, 'search.json'), 'rb').read()
FILES_RAW = open(os.path.join(DATA, 'files.json'), 'rb').read()
THUMB = open(os.path.join(DATA, 'thumb.jpg'), 'rb').read()
REGION, SIZE = 0x30000000, 0x80000
S_IDLE, S_QUERY, S_THUMBS, S_DONE = 0, 1, 2, 3


def sgn(v): return v - (1 << 32) if v >= 1 << 31 else v


class Pure:
    """The pure functions under Unicorn: the input ends at the end of a mapped region and the output too (an unmapped page follows each), so a read or write past either faults."""
    def __init__(self):
        self.m = Machine()
        for base in (REGION, REGION + 0x100000): self.m.u.mem_map(base, SIZE)

    def put(self, data):
        a = REGION + SIZE - len(data)
        self.m.u.mem_write(a, data)
        return a

    def out(self, n):
        a = REGION + 0x100000 + SIZE - n
        self.m.u.mem_write(a, bytes([0xAA]) * n)
        return a

    def clean(self, term, size=TERM):
        if isinstance(term, str): term = term.encode('utf-8')
        o = self.out(size)
        n = sgn(self.m.call(PSYMS['bn_clean_term'], a0=self.put(term + b'\0'), a1=o, a2=size, count=1 << 40))
        raw = bytes(self.m.u.mem_read(o, size))
        return n, raw[:raw.index(0)].decode('utf-8') if 0 in raw else None

    def url(self, term, size=1200):
        if isinstance(term, str): term = term.encode('utf-8')
        o = self.out(size)
        r = sgn(self.m.call(PSYMS['bn_query_url'], a0=self.put(term + b'\0'), a1=o, a2=size, count=1 << 40))
        raw = bytes(self.m.u.mem_read(o, size))
        return r, raw[:raw.index(0)].decode('utf-8') if r >= 0 else None

    def secs(self, text): return self.m.call(PSYMS['bn_secs'], a0=self.put(text.encode('utf-8') + b'\0'), count=1 << 40)

    def idok(self, text): return self.m.call(PSYMS['bn_id_ok'], a0=self.put(text.encode('utf-8') + b'\0'), count=1 << 40)

    def docs(self, data, mx=ROWS):
        o = self.out(mx * ROW)
        for i, v in enumerate((0,)): self.m.setword(STACK + 16 + 4 * i, v)
        n = sgn(self.m.call(PSYMS['bn_parse_docs'], a0=self.put(data), a1=len(data), a2=o, a3=mx, count=1 << 40))
        raw = bytes(self.m.u.mem_read(o, mx * ROW))
        rows = []
        for i in range(max(n, 0)):
            r = raw[i * ROW:(i + 1) * ROW]
            cs = lambda b: b.split(b'\0')[0].decode('utf-8')
            rows.append((cs(r[:ID]), cs(r[ID:ID + TITLE]), cs(r[ID + TITLE:ID + TITLE + AUTHOR]), int.from_bytes(r[ROW - 4:], 'little')))
        return n, rows


def doc(*docs, extra=''):
    return ('{"responseHeader":{"status":0},"response":{"numFound":%d,"start":0,"docs":[%s]%s}}' % (len(docs), ','.join(docs), extra)).encode('utf-8')


def d(**kw): return json.dumps(kw, ensure_ascii=False)


def secs_of(text):
    """The documented reading of a running time: H:MM:SS, MM:SS, seconds or seconds.fraction; anything else 0."""
    mm = re.fullmatch(r'(\d+)(?::(\d+))?(?::(\d+))?(?:\.\d*)?', text or '')
    if not mm: return 0
    g = [min(int(x), 999999) for x in mm.groups() if x is not None]
    if '.' in text and text.count(':') != len(g) - 1: return 0
    return g[0] * 3600 + g[1] * 60 + g[2] if len(g) == 3 else g[0] * 60 + g[1] if len(g) == 2 else g[0]


def nat(s): return [(int(t), '') if t.isdigit() else (0, t) for t in re.split(r'(\d+)', s.lower()) if t]


def oracle_parts(raw, mx=MAXP):
    """What the scanner should give for an answer: json.loads, the 64Kbps MP3 objects, natural order of the name, the documented fallbacks."""
    out = []
    for x in json.loads(raw)['result']:
        if x.get('format') != '64Kbps MP3': continue
        name = x.get('name', '')
        if not name or '/' in name or any(ord(c) < 32 or ord(c) == 127 for c in name) or len(name.encode()) > FILE - 1: continue
        title = cut(x['title'], TITLE) if x.get('title') else cut(name.rsplit('.', 1)[0] if '.' in name[1:] else name, TITLE)
        size = x.get('size', '')
        out.append((name, title, secs_of(x.get('length', '')), int(size) if isinstance(size, str) and size.isdigit() else 0))
    out.sort(key=lambda p: (nat(p[0]), p[0]))
    return out[:mx]


def machine(site=None, **kw):
    m = SE.machine(site=site, **kw)
    m.u.mem_map(REGION, SIZE)   # (the scanner's output ends at the end of this region)
    return m


def scan(m, path, mx=MAXP, limit=0):
    """bn_scan_files over the file at path (its reads at most limit bytes when set): (parts, complete, more) or None for -1."""
    base = REGION + SIZE - mx * PART
    m.u.mem_write(base, bytes([0xAA]) * (mx * PART))
    cp, mp = m.alloc(4), m.alloc(4)
    m.setword(cp, 7), m.setword(mp, 7)
    m.setword(STACK + 16, mp)
    m.read_limit = limit
    n = sgn(m.call(PSYMS['bn_scan_files'], a0=m.cstr(path), a1=base, a2=mx, a3=cp, count=1 << 40))
    if n < 0: return None, m.word(cp), m.word(mp)
    raw = bytes(m.u.mem_read(base, n * PART))
    cs = lambda b: b.split(b'\0')[0].decode('utf-8')
    parts = [(cs(raw[i * PART:i * PART + FILE]), cs(raw[i * PART + FILE:i * PART + FILE + TITLE]),
              int.from_bytes(raw[i * PART + FILE + TITLE:i * PART + FILE + TITLE + 4], 'little'), int.from_bytes(raw[i * PART + FILE + TITLE + 4:(i + 1) * PART], 'little')) for i in range(n)]
    return parts, m.word(cp), m.word(mp)


class LM(PCN.NM):
    """The card machine whose read() returns at most read_limit bytes at a time (a scanner that holds up at every chunk boundary shows)."""
    read_limit = 0

    def _hook(self, u, address, size, _):
        if self.handlers.get(address, '') == 'read' and self.read_limit and u.reg_read(UC_MIPS_REG_A2) > self.read_limit: u.reg_write(UC_MIPS_REG_A2, self.read_limit)
        return super()._hook(u, address, size, _)


def natcmp(m, a, b):
    return sgn(m.call(PSYMS['bk_natcmp'], a0=m.cstr(a), a1=m.cstr(b), count=2000000))


def limited(m):
    m.__class__ = LM
    return m


def obj(**kw): return json.dumps(kw)


def mp3(name, **kw): return obj(name=name, format='64Kbps MP3', source='derivative', size='1000', length='1:00', **kw)


def result(*objs, tail=''): return ('{"result":[%s]%s}' % (','.join(objs), tail)).encode('utf-8')


# ---- The jobs' views

def cstate(m): return dict(state=fn(m, 'bn_catalog_state'), code=fn(m, 'bn_catalog_code'), count=fn(m, 'bn_catalog_count'), search=fn(m, 'bn_catalog_search'), busy=fn(m, 'pn_job_busy'), gen=fn(m, 'bn_gen'))


def row(m, i):
    p = fn(m, 'bn_row', i)
    if not p: return None
    raw = bytes(m.u.mem_read(p, ROW))
    cs = lambda b: b.split(b'\0')[0].decode('utf-8')
    return (cs(raw[:ID]), cs(raw[ID:ID + TITLE]), cs(raw[ID + TITLE:ID + TITLE + AUTHOR]), int.from_bytes(raw[ROW - 4:], 'little'))


def thumb(m, i):
    buf = m.alloc(200)
    return m.read_cstr(buf) if fn(m, 'bn_thumb', i, buf, 200) else None


def catalog(m, term, run=True):
    m.thread = None
    r = fn(m, 'bn_catalog', m.cstr(term))
    th = m.thread
    if run and th: PCN.work(m, th)
    return r, th


def pstate(m): return dict(state=fn(m, 'bn_preview_state'), code=fn(m, 'bn_preview_code'), count=fn(m, 'bn_preview_count'), busy=fn(m, 'pn_job_busy'), gen=fn(m, 'bn_gen'))


def preview(m, ident=PRIDE, run=True):
    m.thread = None
    r = fn(m, 'bn_preview', m.cstr(ident))
    th = m.thread
    if run and th: PCN.work(m, th)
    return r, th


def part(m, i):
    p = fn(m, 'bn_part', i)
    if not p: return None
    raw = bytes(m.u.mem_read(p, PART))
    cs = lambda b: b.split(b'\0')[0].decode('utf-8')
    return (cs(raw[:FILE]), cs(raw[FILE:FILE + TITLE]), int.from_bytes(raw[FILE + TITLE:FILE + TITLE + 4], 'little'), int.from_bytes(raw[FILE + TITLE + 4:], 'little'))


def totals(m):
    ps, ss, bs, ms = (m.alloc(4) for _ in range(4))
    ok = fn(m, 'bn_preview_totals', ps, ss, bs, ms)
    return ok, m.word(ps), m.word(ss), m.word(bs), m.word(ms)


def cover(m):
    buf = m.alloc(200)
    return m.read_cstr(buf) if fn(m, 'bn_preview_cover', buf, 200) else None


def catalog_site(reqs, search=SEARCH_RAW, thumbs=lambda u: {'body': THUMB, 'chunk': 5500}):
    def site(url, o):
        reqs.append(url)
        return {'body': search} if 'advancedsearch' in url else thumbs(url)
    return site


def books_site(reqs, files=FILES_RAW, img=lambda u: {'body': THUMB, 'chunk': 5500}):
    def site(url, o):
        reqs.append(url)
        return {'body': files, 'chunk': 16384} if '/metadata/' in url else img(url)
    return site


# ---------------------------------------------------------------------------
def query_tests(ctx):
    """bn_clean_term and bn_query_url: the Lucene characters, UTF-8, the bounds, the two addresses."""
    expect, P = ctx.expect, Pure()
    for term, want in (('Pride and Prejudice', 'Pride and Prejudice'), ('  holmes  ', 'holmes'), ('', ''), ('   ', ''), ('+-&|!(){}[]^"~*?:\\/', ''), ('Jules-Verne', 'Jules Verne'), ('AC/DC', 'AC DC'),
                       ('a+b', 'a b'), ('"war" (and) peace', 'war and peace'), ('tom  \t sawyer\n', 'tom sawyer'), ('!!hello!!', 'hello'), ('x:y', 'x y'), ('夏目 漱石', '夏目 漱石'), ('こころ', 'こころ'),
                       ('Café Müller', 'Café Müller'), ('émile*', 'émile'), ('a\x01b\x7fc', 'a b c'), ('AND', 'and'), ('Tom AND Jerry', 'Tom and Jerry'), ('NOT OR AND', 'not or and'), ('NOTE ORAL ANDY', 'NOTE ORAL ANDY'),
                       ('and or not', 'and or not'), ('Or', 'Or'), ("Alice's Adventures", "Alice's Adventures"), ('a - b', 'a b'), ('1984', '1984')):
        n, got = P.clean(term)
        expect((n, got) == (len(want.encode()), want), f'bn_clean_term({term!r}) is {want!r}, got {(n, got)}')
    n, got = P.clean('x' * 200)
    expect(n == TERM - 1 and got == 'x' * (TERM - 1), f'a long term is cut at {TERM - 1} bytes')
    n, got = P.clean('x' * (TERM - 2) + '中')
    expect(got == 'x' * (TERM - 2) and n == TERM - 2, 'a character that does not fit is left out whole, never cut')
    n, got = P.clean('中' * 40)
    expect(got == '中' * 31 and n == 93, 'three byte characters: 31 of them fit 95 bytes')
    n, got = P.clean(b'a\xffb\xc3c\xe4\xb8d')
    expect(got == 'abcd', f'bytes that are not UTF-8 are dropped ({got!r})')
    n, got = P.clean(b'\x80\x80ok\xf8')
    expect(got == 'ok', 'stray continuation bytes and an impossible lead byte are dropped')
    n, got = P.clean('abcdef', 4)
    expect(got == 'abc' and n == 3, 'a small buffer takes what fits with its NUL')
    n, got = P.clean('abc', 1)
    expect(got == '' and n == 0, 'a one byte buffer: empty')
    q = lambda s: 'collection%3Alibrivoxaudio%20AND%20%28title%3A%28' + s + '%29%20OR%20creator%3A%28' + s + '%29%29'
    r, u = P.url('')
    expect(r == 0 and u == POPULAR, f'popular: {u}')
    expect(P.url('   ')[0] == 0 and P.url('+-')[0] == 0 and P.url('()')[1] == POPULAR, 'a term with nothing left after cleaning is the popular list')
    r, u = P.url('Sherlock Holmes')
    expect(r == 1 and u == HOST + '/advancedsearch.php?q=' + q('Sherlock%20Holmes') + SEARCH_TAIL, f'a search: {u}')
    r, u = P.url('Jules-Verne: "20,000 Leagues" (1870)!')
    expect(r == 1 and u == HOST + '/advancedsearch.php?q=' + q('Jules%20Verne%2020%2C000%20Leagues%201870') + SEARCH_TAIL, f'the special characters never reach the query: {u}')
    r, u = P.url('夏目漱石')
    expect(r == 1 and q('%E5%A4%8F%E7%9B%AE%E6%BC%B1%E7%9F%B3') in u, 'UTF-8 is kept and percent-encoded')
    r, u = P.url('Tom AND Jerry')
    expect(r == 1 and 'Tom%20and%20Jerry' in u, 'AND inside a term is no operator')
    expect(len(u) < 400, 'an ordinary address is short')
    r, u = P.url('中' * 31)
    expect(r == 1 and len(u) < 1200 and u.endswith(SEARCH_TAIL), f'the longest term fits the buffer ({len(u)} bytes)')
    r, u = P.url('Sherlock Holmes', 60)
    expect(r == -1, 'a buffer that is too small: -1')
    for size in (len(POPULAR), len(POPULAR) + 1):
        r, u = P.url('', size)
        expect((r, u is not None) == ((-1, False) if size == len(POPULAR) else (0, True)), f'the popular address needs its NUL ({size} bytes: {r})')
    expect(all(P.url(t, 120)[0] in (-1, 0, 1) for t in ('a' * 50, '中' * 20, '')), 'tight buffers answer, never fault')


def secs_tests(ctx):
    expect, P = ctx.expect, Pure()
    for text, want in (('10:17:59', 37079), ('2:32:12', 9132), ('38:05', 2285), ('18:52', 1132), ('1132', 1132), ('1132.5', 1132), ('1:02:03', 3723), ('0:00:00', 0), ('0', 0), ('', 0), ('0:07', 7), ('75:03', 4503),
                       ('1132.', 1132), ('1:30.5', 90), ('1:2:3:4', 0), (':30', 0), ('1:', 0), ('abc', 0), ('12a', 0), (' 12', 0), ('12 ', 0), ('-5', 0), ('1e3', 0), ('.5', 0), ('1.5.5', 0), ('99999999999', 999999),
                       ('999999:999999:999999', 999999 * 3600 + 999999 * 60 + 999999), ('1:2:3.9', 3723), ('1.5:30', 0), ('００', 0)):
        got = P.secs(text)
        expect(got == want, f'bn_secs({text!r}) is {want}, got {got}')
        if want or text in ('0', '0:00:00'): expect(secs_of(text) == want or text in ('1.5:30',), f'the test\'s own reading agrees on {text!r}')
    for text, want in (('adventures_holmes', 1), ('A-b.c_9', 1), ('', 0), ('a/b', 0), ('a b', 0), ('a\\b', 0), ('a?b', 0), ('é', 0), ('.', 0), ('..', 0), ('...', 1), ('a' * (ID - 1), 1), ('a' * ID, 0), ('a%2Fb', 0), ('a:b', 0)):
        expect(P.idok(text) == want, f'bn_id_ok({text!r}) is {want}')


def docs_tests(ctx):
    expect, P = ctx.expect, Pure()
    want = [(x['identifier'], x['title'], x['creator'][0] if isinstance(x.get('creator'), list) else x.get('creator', ''), secs_of(x.get('runtime', '')))
            for x in json.loads(SEARCH_RAW)['response']['docs'] if re.fullmatch(r'[A-Za-z0-9._-]+', x['identifier'])]
    n, rows = P.docs(SEARCH_RAW)
    expect(n == len(want) == 7 and rows == want, f'the sample answer: {n} rows, the odd identifier skipped, creator a string / an array / none, runtime in every form ({rows[:3]})')
    expect(rows[0] == ('adventures_holmes', 'The Adventures of Sherlock Holmes', 'Sir Arthur Conan Doyle', 37079) and rows[2][2] == 'Lewis Carroll' and rows[3][2] == '' and rows[5][3] == 0 and rows[6] == ('kokoro_librivox', 'こころ', '夏目 漱石', 1132),
           'a string creator, the first of an array, none; a missing runtime is 0; "1132.5" is 1132; UTF-8 kept')
    n, rows = P.docs(SEARCH_RAW, 3)
    expect(n == 3 and rows == want[:3], 'with room for three it keeps the first three')
    many = [d(identifier=f'book_{i}', title=f'Book {i}', creator='A', runtime='1:00') for i in range(40)]
    n, rows = P.docs(doc(*many))
    expect(n == ROWS and rows[-1][0] == 'book_24', f'a longer list is cut at {ROWS} rows')
    n, rows = P.docs(doc())
    expect(n == 0 and rows == [], 'an empty list: 0 rows (the page says no books)')
    for label, body in (('no response', b'{"error":"x"}'), ('response without docs', b'{"response":{"numFound":0}}'), ('docs of another kind', b'{"response":{"docs":"x"}}'), ('not JSON', b'<html>x</html>'), ('empty', b''),
                        ('docs at the top', b'{"docs":[{"identifier":"a","title":"b"}]}'), ('an array', b'[{"identifier":"a","title":"b"}]')):
        n, rows = P.docs(body)
        expect(n == -1, f'{label}: -1 (not an answer)')
    cases = (('no identifier', d(title='T', creator='C'), None), ('no title', d(identifier='a'), None), ('an empty title', d(identifier='a', title=''), None),
             ('a bad identifier (slash)', d(identifier='a/b', title='T'), None), ('a bad identifier (space)', d(identifier='a b', title='T'), None), ('a bad identifier (dots only)', d(identifier='..', title='T'), None),
             ('an identifier too long', d(identifier='a' * ID, title='T'), None), ('an identifier of the longest length', d(identifier='a' * (ID - 1), title='T'), ('a' * (ID - 1), 'T', '', 0)),
             ('an identifier that decoding would change (a NUL dropped)', '{"identifier":"ab\\u0000c","title":"T"}', None), ('an identifier with a tab', '{"identifier":"ab\\tc","title":"T"}', None),
             ('a numeric identifier', '{"identifier":5,"title":"T"}', None), ('a null title', '{"identifier":"a","title":null}', None),
             ('a title that is an array', '{"identifier":"a","title":["First","Second"]}', ('a', 'First', '', 0)), ('an empty creator array', '{"identifier":"a","title":"T","creator":[]}', ('a', 'T', '', 0)),
             ('creator an array of two', '{"identifier":"a","title":"T","creator":["X","Y"]}', ('a', 'T', 'X', 0)), ('creator an array that starts with a number', '{"identifier":"a","title":"T","creator":[5,"Y"]}', ('a', 'T', '', 0)),
             ('creator null', '{"identifier":"a","title":"T","creator":null}', ('a', 'T', '', 0)), ('creator an object', '{"identifier":"a","title":"T","creator":{"x":"y"}}', ('a', 'T', '', 0)),
             ('runtime a number', '{"identifier":"a","title":"T","runtime":75}', ('a', 'T', '', 75)), ('runtime junk', d(identifier='a', title='T', runtime='long'), ('a', 'T', '', 0)),
             ('escapes', '{"identifier":"a","title":"Q \\"x\\" \\u00e9 \\ud83d\\ude00\\n","creator":"A\\\\B"}', ('a', 'Q "x" é 😀 ', 'A\\B', 0)),
             ('members in any order, extras skipped', '{"x":{"identifier":"no"},"title":"T","n":[1,[2,{"a":"b"}]],"identifier":"a","creator":"C","runtime":"5:00"}', ('a', 'T', 'C', 300)),
             ('the first of two identifiers', '{"identifier":"a","identifier":"b","title":"T"}', ('a', 'T', '', 0)))
    for label, text, want_row in cases:
        n, rows = P.docs(doc(text))
        expect((n, rows) == ((1, [want_row]) if want_row else (0, [])), f'{label}: {rows}')
    long_title, long_author = 'T' * 200, 'é' * 100
    n, rows = P.docs(doc(d(identifier='a', title=long_title, creator=long_author)))
    expect(n == 1 and rows[0][1] == 'T' * (TITLE - 1) and rows[0][2] == 'é' * 31 and len(rows[0][2].encode()) == 62, f'a title and an author over their buffers are cut on a character boundary ({len(rows[0][1])}, {len(rows[0][2].encode())})')
    n, rows = P.docs(doc(d(identifier='a', title='中' * 40)))
    expect(rows[0][1] == '中' * 31, 'a three byte title is cut at 31 characters (93 bytes)')
    n, rows = P.docs(doc(d(identifier='ok', title='T'), '{"identifier":"cut'))
    expect(n == 1 and rows[0][0] == 'ok', 'an object cut short by the end of the text is not kept')
    n, rows = P.docs(doc(d(identifier='a', title='T'), '[1,2]', '"x"', 'null', d(identifier='b', title='U')))
    expect(n == 2 and [r[0] for r in rows] == ['a', 'b'], 'elements that are not objects are skipped')
    # truncation at every length: never a fault, never a row that was not whole in the answer, never more rows than the complete answer's
    bad = []
    for k in range(0, len(SEARCH_RAW) + 1, 7):
        n, rows = P.docs(SEARCH_RAW[:k])
        if not (n <= 7 and (n == -1 or rows == want[:n])): bad.append((k, n))
    expect(not bad, f'every truncation of the sample answer (every 7th byte): rows are a prefix of the real ones, no fault ({bad[:3]})')
    rng = random.Random(1136)
    bad = 0
    for _ in range(150):
        b = bytearray(SEARCH_RAW)
        for _ in range(rng.randint(1, 8)): b[rng.randrange(len(b))] = rng.choice(b'{}[]",:\\\0\xff0a ')
        n, rows = P.docs(bytes(b))
        bad += not (n == -1 or 0 <= n <= ROWS)
    expect(not bad, 'mutated answers (bytes swapped for structure characters): a count in range or -1, no fault')
    deep = b'{"response":{"docs":[{"identifier":"a","title":"T","x":' + b'[' * 200 + b']' * 200 + b'},{"identifier":"b","title":"U"}]}}'
    n, rows = P.docs(deep)
    expect(n in (0, 1) and all(r[0] == 'a' for r in rows) if n else True, 'a value nested far deeper than the walker follows ends the walk, rows before it stay or are dropped')


def files_tests(ctx):
    expect = ctx.expect
    m = machine()
    m.put('/f/real.json', FILES_RAW)
    want = oracle_parts(FILES_RAW)
    parts, complete, more = scan(m, '/f/real.json')
    expect(len(want) == 8 and parts == want and complete == 1 and more == 0, f'the real-shaped answer (21 objects, 8 parts among m4b, jpg, pdf, VBR, ogg, spectrogram, torrent ...): parts, complete ({parts[:2]})')
    expect(parts[0] == ('prideandprejudice_01-03_austen_64kb.mp3', 'Chapters 1-3', 1132, 9064064) and parts[-1][0].startswith('prideandprejudice_60-61'), 'name, title, seconds from "18:52", bytes from "9064064"; natural order puts 59 before 60-61')
    expect(all(natcmp(m, a[0], b[0]) < 0 for a, b in zip(parts, parts[1:])), 'the parts are in bk_natcmp order')
    # every chunk size gives the same answer (an object, a string, an escape or a key may straddle any boundary)
    limits = (1, 2, 3, 5, 7, 64, 100, 331, 4095, 4096, 4097, 100000)
    bad = [limit for limit in limits if scan(limited(m), '/f/real.json', limit=limit) != (want, 1, 0)]
    m.read_limit = 0
    expect(not bad, f'reads of at most {limits} bytes at a time all give the same parts (differing: {bad})')
    # the file order does not matter
    objs = json.loads(FILES_RAW)['result']
    rng = random.Random(5)
    for k in range(4):
        sh = objs[:]; rng.shuffle(sh)
        m.put('/f/shuf.json', json.dumps({'result': sh}).encode())
        expect(scan(m, '/f/shuf.json')[0] == want, f'shuffled objects {k}: the same order')
    m.put('/f/pretty.json', json.dumps({'result': objs}, indent=2).encode())
    expect(scan(limited(m), '/f/pretty.json', limit=3)[0] == want, 'an answer with white space everywhere')
    # natural order, titles, seconds, sizes
    names = ['Part 10.mp3', 'part 2.mp3', 'Part 1.mp3', 'part 100.MP3', 'Part 20.mp3', 'a_9.mp3', 'a_10.mp3', 'a_009.mp3', 'B.mp3', 'a.mp3']
    m.put('/f/nat.json', result(*[mp3(n) for n in names]))
    parts, complete, more = scan(m, '/f/nat.json')
    got = [p[0] for p in parts]
    expect(complete and len(got) == 10 and all(natcmp(m, a, b) < 0 for a, b in zip(got, got[1:])) and got[:5] == ['a.mp3', 'a_009.mp3', 'a_9.mp3', 'a_10.mp3', 'B.mp3'] and got[5:] == ['Part 1.mp3', 'part 2.mp3', 'Part 10.mp3', 'Part 20.mp3', 'part 100.MP3'],
           f'natural, case-insensitive order (bk_natcmp): {got}')
    cases = (('title given', mp3('a.mp3', title='Chapter One'), ('a.mp3', 'Chapter One', 60, 1000)), ('no title: the name without its extension', mp3('Ch 01 - Intro.mp3'), ('Ch 01 - Intro.mp3', 'Ch 01 - Intro', 60, 1000)),
             ('an empty title', mp3('x.mp3', title=''), ('x.mp3', 'x', 60, 1000)), ('a name with two dots', mp3('a.b.mp3'), ('a.b.mp3', 'a.b', 60, 1000)), ('a name without a dot', mp3('abc'), ('abc', 'abc', 60, 1000)),
             ('a dot file', mp3('.mp3'), ('.mp3', '.mp3', 60, 1000)), ('length in seconds', obj(name='a.mp3', format='64Kbps MP3', length='1132.52', size='5'), ('a.mp3', 'a', 1132, 5)),
             ('length "1:02:03"', obj(name='a.mp3', format='64Kbps MP3', length='1:02:03'), ('a.mp3', 'a', 3723, 0)), ('length numeric, size numeric', '{"name":"a.mp3","format":"64Kbps MP3","length":75,"size":2048}', ('a.mp3', 'a', 75, 2048)),
             ('no length, no size', obj(name='a.mp3', format='64Kbps MP3'), ('a.mp3', 'a', 0, 0)), ('junk length and size', obj(name='a.mp3', format='64Kbps MP3', length='soon', size='big'), ('a.mp3', 'a', 0, 0)),
             ('size 4294967295', obj(name='a.mp3', format='64Kbps MP3', size='4294967295'), ('a.mp3', 'a', 0, 4294967295)), ('size past 32 bits', obj(name='a.mp3', format='64Kbps MP3', size='99999999999'), ('a.mp3', 'a', 0, 0xffffffff)),
             ('a UTF-8 title and name', obj(name='章 1.mp3', format='64Kbps MP3', title='第一章'), ('章 1.mp3', '第一章', 0, 0)), ('title with an escape', '{"name":"a.mp3","format":"64Kbps MP3","title":"A \\"B\\" \\u00e9"}', ('a.mp3', 'A "B" é', 0, 0)))
    for label, o, w in cases:
        m.put('/f/c.json', result(o))
        parts, complete, _ = scan(m, '/f/c.json')
        expect(parts == [w] and complete == 1, f'{label}: {parts}')
    m.put('/f/c.json', result(mp3('a.mp3', title='T' * 200), mp3('b' * 123 + '.mp3'), mp3('c' * 124 + '.mp3')))
    parts, _, _ = scan(m, '/f/c.json')
    expect([p[0] for p in parts] == ['a.mp3', 'b' * 123 + '.mp3'] and parts[0][1] == 'T' * (TITLE - 1) and parts[1][1] == cut('b' * 123, TITLE),
           f'a title over its buffer is cut; a 127 byte name fits the {FILE} byte buffer with its NUL, a 128 byte one is skipped ({[len(p[0]) for p in parts]})')
    m.put('/f/c.json', result(mp3('é' * 61 + '.mp3'), mp3('é' * 62 + '.mp3'), mp3('é' * 20 + 'x' * 70 + '.mp3', title='é' * 60)))
    parts, _, _ = scan(m, '/f/c.json')
    expect(len(parts) == 2 and [p[1] for p in parts] == ['é' * 47, 'é' * 47] and len(parts[0][0].encode()) in (126, 114), f'a title from a name or given, over its buffer, ends on a character boundary; a 128 byte name is skipped ({[len(p[0].encode()) for p in parts]})')
    # skipped objects
    m.put('/f/c.json', result(mp3('a/b.mp3'), mp3('c\x01d.mp3'), mp3('e\nf.mp3'), mp3('g\x7fh.mp3'), mp3(''), obj(format='64Kbps MP3', length='1:00'), obj(name='n.mp3', format='VBR MP3'), obj(name='m.mp3', format='64kbps mp3'),
                              obj(name='o.mp3', format='64Kbps MP3 '), obj(name='p.mp3'), obj(name='q.mp3', format=None), '[1,2]', '"x"', '5', 'null', mp3('ok.mp3')))
    parts, complete, _ = scan(m, '/f/c.json')
    expect([p[0] for p in parts] == ['ok.mp3'] and complete == 1, f'names with a slash or a control byte, no name, no format, another format (case and trailing space count): skipped ({[p[0] for p in parts]})')
    m.put('/f/c.json', b'{"result":[{"name":"tab\\there.mp3","format":"64Kbps MP3"},{"name":"raw\tx.mp3","format":"64Kbps MP3"},{"name":"nul\\u0000.mp3","format":"64Kbps MP3"},{"name":"ok.mp3","format":"64Kbps MP3","title":"a\\nb"}]}')
    parts, _, _ = scan(m, '/f/c.json')
    expect([p[0] for p in parts] == ['ok.mp3'] and parts[0][1] == 'a b', f'a tab by escape or raw is a control byte in a name: skipped; in a title it is a space ({parts})')
    # an object over the scanner's size is skipped, the next one is found
    big = obj(name='huge.mp3', format='64Kbps MP3', md5='x' * (OBJ + 100))
    m.put('/f/c.json', result(mp3('a.mp3'), big, mp3('b.mp3')))
    parts, complete, _ = scan(m, '/f/c.json')
    expect([p[0] for p in parts] == ['a.mp3', 'b.mp3'] and complete == 1, f'an object over {OBJ} bytes is skipped, the ones around it are kept')
    almost = obj(name='edge.mp3', format='64Kbps MP3', md5='x' * (OBJ - 100))
    m.put('/f/c.json', result(almost))
    expect(scan(m, '/f/c.json')[0] and len(almost) < OBJ, f'an object just under {OBJ} bytes is read')
    for extra, label in ((-1, 'just under'), (0, 'exactly'), (1, 'just over')):
        head = '{"name":"edge.mp3","format":"64Kbps MP3","md5":"'
        o = head + 'x' * (OBJ + extra - len(head) - 2) + '"}'
        m.put('/f/c.json', result(o, mp3('after.mp3')))
        names_ = [p[0] for p in scan(m, '/f/c.json')[0]]
        expect(names_ == ['after.mp3', 'edge.mp3'] if extra <= 0 else names_ == ['after.mp3'], f'an object {label} {OBJ} bytes: {"kept" if extra <= 0 else "skipped"}, the one after it kept ({names_})')
    # nested members, braces and brackets inside strings, other top-level members before and after the array
    tricky = ('{"created":1,"files":[{"name":"decoy.mp3","format":"64Kbps MP3"}],"note":"{\\"result\\":[","result":[{"name":"a.mp3","format":"64Kbps MP3","extra":{"x":[1,{"y":"]}"}],"z":"}"},"title":"A {\\"] ["},'
              '{"name":"b.mp3","format":"64Kbps MP3","length":"0:30"}],"result2":[{"name":"late.mp3","format":"64Kbps MP3"}],"tail":"]"}').encode()
    m.put('/f/t.json', tricky)
    for limit in (0, 1, 2, 5):
        parts, complete, _ = scan(limited(m), '/f/t.json', limit=limit)
        expect(parts == [('a.mp3', 'A {"] [', 0, 0), ('b.mp3', 'b', 30, 0)] and complete == 1, f'strings with brackets, a decoy array and a decoy key, nested members (chunks of {limit or "all"}): {parts}')
    m.read_limit = 0
    m.put('/f/e.json', b'{"re\\u0073ult":[{"name":"a.mp3","format":"64Kbps MP3"}]}')
    expect(scan(m, '/f/e.json')[0] is None, 'a key spelt with an escape is not "result" (documented: not found)')
    m.put('/f/e.json', b'{"results":[{"name":"a.mp3","format":"64Kbps MP3"}],"resul":[{"name":"b.mp3","format":"64Kbps MP3"}],"resultxx":[{"name":"c.mp3","format":"64Kbps MP3"}]}')
    expect(scan(m, '/f/e.json') == (None, 0, 0), 'no key exactly "result": -1')
    # more than the limit: the first BK_MAX_PARTS in natural order, whatever the file's order
    many = [mp3(f'b{i:04d}.mp3') for i in range(MAXP + 40)]
    m.put('/f/many.json', result(*many))
    parts, complete, more = scan(m, '/f/many.json')
    expect(len(parts) == MAXP and more == 1 and complete == 1 and [p[0] for p in parts] == [f'b{i:04d}.mp3' for i in range(MAXP)], f'{MAXP + 40} parts: the first {MAXP}, more set')
    rev = many[::-1]
    m.put('/f/many.json', result(*rev))
    parts, complete, more = scan(m, '/f/many.json')
    expect(len(parts) == MAXP and more == 1 and [p[0] for p in parts] == [f'b{i:04d}.mp3' for i in range(MAXP)], 'the same from a file in reverse order')
    m.put('/f/many.json', result(*many[:MAXP]))
    parts, complete, more = scan(m, '/f/many.json')
    expect(len(parts) == MAXP and more == 0, f'exactly {MAXP} parts: more is 0')
    parts, complete, more = scan(m, '/f/many.json', mx=10)
    expect(len(parts) == 10 and more == 1 and parts[9][0] == 'b0009.mp3', 'a smaller max keeps the first of them')
    rng = random.Random(77)
    shuffled = many[:]; rng.shuffle(shuffled)
    m.put('/f/many.json', result(*shuffled))
    expect(scan(m, '/f/many.json')[0] == [(f'b{i:04d}.mp3', f'b{i:04d}', 60, 1000) for i in range(MAXP)], 'shuffled: the same first parts')
    # 2 MiB: reading stops at the cap, the array is then not complete
    pad = obj(name='pad.bin', format='Metadata', md5='x' * 3000)
    m.put('/f/cap.json', result(*([mp3('a.mp3')] + [pad] * 800)))
    got = len(m.fs['/f/cap.json'])
    expect(got > CAP, f'the cap test answer is {got} bytes, over {CAP}')
    parts, complete, _ = scan(m, '/f/cap.json')
    expect([p[0] for p in parts] == ['a.mp3'] and complete == 0, 'an answer over 2 MiB: the parts before the cap, not complete')
    # malformed and truncated
    full = result(mp3('a.mp3'), mp3('b.mp3'), mp3('c.mp3'))
    bad = []
    for k in range(len(full) + 1):
        m.put('/f/trunc.json', full[:k])
        parts, complete, _ = scan(m, '/f/trunc.json')
        names = [p[0] for p in parts] if parts is not None else []
        closed = k >= len(full) - 1   # (the array's ']' is the last but one byte)
        if complete != closed or names != ['a.mp3', 'b.mp3', 'c.mp3'][:len(names)] or (parts is None and k >= 11): bad.append((k, complete, names))
    expect(not bad, f'truncated at every byte: the parts whole before the cut, complete only once the array closed, -1 only before the array was entered ({bad[:3]})')
    for label, body, want_n in (('empty file', b'', None), ('not JSON', b'<html></html>', None), ('an array at the top', b'[{"name":"a.mp3","format":"64Kbps MP3"}]', None), ('an empty object', b'{}', None), ('an empty result', b'{"result":[]}', 0),
                                ('result an object', b'{"result":{"name":"a.mp3","format":"64Kbps MP3"}}', None), ('result a string', b'{"result":"x"}', None), ('garbage after the array', b'{"result":[{"name":"a.mp3","format":"64Kbps MP3"}]}}}}garbage', 1),
                                ('unbalanced close', b'{"result":[{"name":"a.mp3","format":"64Kbps MP3"}}]', 1), ('stray closing', b']', None), ('stray text in the array', b'{"result":[{"name":"a.mp3","format":"64Kbps MP3"} oops {"name":"b.mp3","format":"64Kbps MP3"}]}', 2)):
        m.put('/f/bad.json', body)
        parts, complete, _ = scan(m, '/f/bad.json')
        expect((None if parts is None else len(parts)) == want_n, f'{label}: {None if parts is None else len(parts)} parts (wanted {want_n}), complete {complete}')
    m.put('/f/deep.json', b'{"result":[' + b'[' * 100 + b']' * 100 + b',{"name":"a.mp3","format":"64Kbps MP3"}]}')
    parts, complete, _ = scan(m, '/f/deep.json')
    expect(not complete and not parts, 'nesting deeper than 32 is malformed: the scan stops, not complete')
    expect(scan(m, '/f/missing.json') == (None, 0, 0), 'a file that is not there: -1')
    rng = random.Random(3)
    bad = 0
    for k in range(60):
        b = bytearray(FILES_RAW)
        for _ in range(rng.randint(1, 10)): b[rng.randrange(len(b))] = rng.choice(b'{}[]",:\\\0\xff0a ')
        m.put('/f/fuzz.json', bytes(b))
        parts, complete, more = scan(m, '/f/fuzz.json')
        bad += not (parts is None or len(parts) <= 9)
    expect(not bad, '60 mutated answers: no fault, at most the parts there were')
    calls = [c for c in m.calls if c[0] == 'open']
    expect(all(c[1].startswith('/f/') for c in calls), 'only the answer file is opened')
    expect(not [c for c in m.calls if c[0] == 'write'], 'the scanner writes nothing')


# ---------------------------------------------------------------------------
def catalog_tests(ctx):
    expect = ctx.expect
    reqs = []
    m = machine(site=catalog_site(reqs))
    expect(fn(m, 'bn_catalog_state') == S_IDLE and fn(m, 'bn_catalog_count') == 0 and row(m, 0) is None and thumb(m, 0) is None, 'before any job: idle, no rows')
    r, th = catalog(m, '', run=False)
    expect(r == 0 and th and th[0] == PSYMS['bn_cmain'] and ('curl_global_init', 3) in m.calls and [c[0] for c in m.calls].count('pthread_create') == 1, 'the popular list starts one detached worker, curl initialised on the UI thread first')
    st = cstate(m)
    expect(st['state'] == S_QUERY and st['busy'] == 1 and st['search'] == 0 and fn(m, 'pn_busy') == 0 and st['count'] == 0, f'the query runs: state 1, a job is busy, a refresh is not ({st})')
    expect(fn(m, 'bn_catalog', m.cstr('x')) == PN['BUSY'] and fn(m, 'bn_preview', m.cstr(PRIDE)) == PN['BUSY'] and fn(m, 'pn_search', m.cstr('x')) == PN['BUSY'] and fn(m, 'pn_chart', 0) == PN['BUSY'], 'a second job of any kind while it runs: PN_BUSY')
    expect(fn(m, 'pn_refresh', m.cstr(PCN.ROOT_DIR), m.shows()[1], m.alloc(4), 1) == PN['BUSY'] and fn(m, 'pn_dl_start') == 0 and fn(m, 'pn_dl_running') == 0, 'a refresh is refused and the downloads do not start while it runs')
    g0 = st['gen']
    PCN.work(m, th)
    st = cstate(m)
    want = [(x['identifier'], x['title'], x['creator'][0] if isinstance(x.get('creator'), list) else x.get('creator', ''), secs_of(x.get('runtime', ''))) for x in json.loads(SEARCH_RAW)['response']['docs'] if '/' not in x['identifier']]
    expect(st['state'] == S_DONE and st['code'] == 0 and st['count'] == 7 and st['busy'] == 0 and st['gen'] > g0 and st['search'] == 0, f'the worker ends: done, OK, 7 rows ({st})')
    expect(reqs[0] == POPULAR, f'the popular address: {reqs[0]}')
    expect([row(m, i) for i in range(7)] == want and row(m, 7) is None and row(m, -1) is None, 'the rows in order; none past the last')
    expect(reqs[1:] == [IMG + r[0] for r in want], 'the thumbnail of each row one by one, in order, from services/img')
    paths = [thumb(m, i) for i in range(7)]
    expect(all(p == f'{DIR}/p{i}.jpg' for i, p in enumerate(paths)) and all(m.fs.get(p) == THUMB for p in paths), 'each picture is p<n>.jpg in the scratch directory, whole')
    expect(not [p for p in m.fs if p.endswith('.src')] and len(m.curl) == 0 and all(d_ in m.dirs for d_ in ('/mnt/mmc/.m1plus', '/mnt/mmc/.m1plus/audiobooks', DIR)), 'no download file left, every handle cleaned up, the directories made')
    expect(fn(m, 'bn_thumb_state', 0) == 1, 'a picture that arrived is state 1')
    # the options of every request: the firmware CA bundle, verification on, redirects, fail on error, time-outs
    o = None
    m2 = machine(site=lambda u, o_: (reqs.append(dict(o_)), {'body': SEARCH_RAW})[1])
    reqs.clear()
    catalog(m2, '')
    o = reqs[0]
    expect(o[10065] == PCN.CA and o[52] == 1 and o[68] == 16 and o[181] == 3 and o[182] == 3 and o[45] == 1 and o[99] == 1 and o[78] == 20 and o[13] == 120 and o[10018].startswith('M1PlusMusic/') and 64 not in o and 81 not in o,
           'the request carries pcnet.c\'s options: the CA bundle, no switch that turns verification off, 16 redirects, fail on HTTP error, time-outs, a user agent')
    # the popular list is held: entering again fetches nothing, and asks for no Wi-Fi
    reqs.clear(); m.calls = []
    m.wifi = -1
    r, th = catalog(m, '')
    st = cstate(m)
    expect(r == 0 and th is None and not reqs and st['state'] == S_DONE and st['count'] == 7 and st['code'] == 0 and st['search'] == 0 and row(m, 0) == want[0] and 'pthread_create' not in [c[0] for c in m.calls],
           f'the held list: entering again starts no worker and asks nothing, even offline ({st})')
    r, th = catalog(m, '  +- ')
    expect(r == 0 and th is None and not reqs, 'a term with nothing left is the popular list too')
    m.wifi = 2
    # a search replaces the search result only
    reqs.clear()
    r, th = catalog(m, 'Sherlock: Holmes!', run=False)
    st = cstate(m)
    expect(r == 0 and st['state'] == S_QUERY and st['search'] == 1 and st['count'] == 0 and row(m, 0) is None, f'a search: the query runs, the current set is the search ({st})')
    PCN.work(m, th)
    st = cstate(m)
    expect(reqs[0].startswith(HOST + '/advancedsearch.php?q=collection%3Alibrivoxaudio%20AND%20%28title%3A%28Sherlock%20Holmes%29') and st['count'] == 7 and st['search'] == 1 and thumb(m, 0) == f'{DIR}/s0.jpg' and m.fs.get(f'{DIR}/s0.jpg') == THUMB,
           f'the search address, the search rows, thumbnails s<n> ({reqs[0][:110]})')
    expect(f'{DIR}/p0.jpg' in m.fs and f'{DIR}/p6.jpg' in m.fs, 'the popular pictures are untouched')
    reqs.clear()
    r, th = catalog(m, '')
    st = cstate(m)
    expect(r == 0 and th is None and not reqs and st['search'] == 0 and st['count'] == 7 and thumb(m, 0) == f'{DIR}/p0.jpg', 'back to the popular list: held, nothing fetched, its pictures still there')
    # a new search removes the old search pictures at once, and the rows
    r, th = catalog(m, 'twain', run=False)
    expect(r == 0 and not [p for p in m.fs if p.startswith(f'{DIR}/s')] and cstate(m)['count'] == 0 and cstate(m)['search'] == 1 and f'{DIR}/p0.jpg' in m.fs, 'a new search: the old search pictures and rows are gone before it starts, the popular pictures stay')
    PCN.work(m, th)
    reqs.clear()
    # bn_catalog_clean: the pictures go, the search is forgotten, the popular rows stay with their pictures untried
    fn(m, 'bn_catalog_clean')
    expect(not [p for p in m.fs if p.startswith(f'{DIR}/p') or p.startswith(f'{DIR}/s')] and fn(m, 'bn_catalog_count') == 0 and thumb(m, 0) is None, 'clean: every picture removed, the search forgotten')
    r, th = catalog(m, '', run=False)
    expect(r == 0 and th and th[0] == PSYMS['bn_cmain'] and cstate(m)['state'] == S_THUMBS, 'the popular list again after a clean: the answer is held, the pictures are fetched (state 2 at once)')
    PCN.work(m, th)
    expect(reqs == [IMG + r_[0] for r_ in want] and cstate(m)['count'] == 7 and all(thumb(m, i) for i in range(7)), 'only the pictures are asked for, one by one')
    # a term of 63 bytes + a character, and the longest term, are fine; the request is bounded
    r, th = catalog(m, '中' * 200)
    expect(r == 0 and cstate(m)['count'] == 7, 'a term far too long is cut, not refused')
    # the guards
    for label, kw, code in (('no Wi-Fi', dict(wifi=-1), PN['NOWIFI']), ('no card', dict(card_mounted=False), PN['STORAGE']), ('a clock never set', dict(wall=1700000000), PN['NOCLOCK'])):
        mg = machine(site=catalog_site([]), **kw)
        r, th = catalog(mg, '')
        expect(r == code and th is None and 'curl_global_init' not in [c[0] for c in mg.calls] and fn(mg, 'bn_catalog_state') == S_IDLE, f'{label}: the guard answers {code}, nothing starts')
    mg = machine(site=catalog_site([]), ca=False)
    r, th = catalog(mg, 'x')
    expect(r == PN['NOCERT'] and th is None, 'no CA bundle: PN_NOCERT')
    mg = machine(site=catalog_site([]), thread_ok=False)
    r, th = catalog(mg, '')
    expect(r == PN['MEM'] and cstate(mg)['busy'] == 0 and fn(mg, 'bn_catalog_state') == S_IDLE, 'a thread that cannot be made: PN_MEM, not busy, idle')
    mg = machine(site=catalog_site([])); mg.calloc_fail = True
    r, th = catalog(mg, '')
    expect(cstate(mg)['code'] == PN['MEM'] and cstate(mg)['busy'] == 0 and cstate(mg)['state'] == S_DONE and cstate(mg)['count'] == 0, 'no memory for the answer: PN_MEM, done')
    # the offline popular list is not held after a failure: the next entry asks again
    for label, site, code in (('no connection', lambda u, o_: {'rc': 6}, PN['NET']), ('a time-out', lambda u, o_: {'rc': 28}, PN['NET']), ('a certificate error', lambda u, o_: {'rc': 60}, PN['CERT']),
                              ('HTTP 503', lambda u, o_: {'rc': 22, 'code': 503}, PN['HTTP']), ('HTTP 404', lambda u, o_: {'rc': 22, 'code': 404}, PN['HTTP']), ('an HTML page', lambda u, o_: {'body': b'<html>blocked</html>'}, PN['HTTP']),
                              ('an empty answer', lambda u, o_: {'body': b''}, PN['HTTP']), ('JSON without response.docs', lambda u, o_: {'body': b'{"error":"x"}'}, PN['HTTP'])):
        mf = machine(site=site)
        r, th = catalog(mf, '')
        st = cstate(mf)
        expect(r == 0 and st['state'] == S_DONE and st['code'] == code and st['count'] == 0 and st['busy'] == 0 and row(mf, 0) is None, f'{label}: done, code {code}, no rows ({st})')
        seen = []
        mf.curl_site = catalog_site(seen)
        r, th = catalog(mf, '')
        expect(th is not None and cstate(mf)['count'] == 7 and seen[0] == POPULAR, f'{label}: the next entry asks again (nothing was held)')
    mf = machine(site=lambda u, o_: {'body': doc()})
    catalog(mf, '')
    st = cstate(mf)
    expect(st['code'] == 0 and st['count'] == 0 and st['state'] == S_DONE, 'an empty list: OK with 0 rows (the page says no books)')
    # thumbnails: a missing one, an HTML page, a short file, the rest still arrive; those tried are not asked again
    def thumbs(u):
        i = [x['identifier'] for x in json.loads(SEARCH_RAW)['response']['docs'] if '/' not in x['identifier']].index(u.rsplit('/', 1)[1])
        return [{'body': THUMB}, {'rc': 22, 'code': 404}, {'body': b'<html>not a picture</html>'}, {'body': b'\x89PNG\r\n\x1a\n' + bytes(8)}, {'body': THUMB}, {'rc': 6}, {'body': b''}][i]
    reqs.clear()
    mt = machine(site=catalog_site(reqs, thumbs=thumbs))
    catalog(mt, '')
    states = [fn(mt, 'bn_thumb_state', i) for i in range(7)]
    expect(states == [1, 2, 2, 2, 1, 2, 2] and [thumb(mt, i) is not None for i in range(7)] == [True, False, False, False, True, False, False] and not [p for p in mt.fs if p.endswith('.src')],
           f'a picture that is missing, not a picture, too short or empty leaves the placeholder (state 2), the others arrive, no download file ({states})')
    reqs.clear(); r, th = catalog(mt, '')
    expect(r == 0 and th is None and not reqs, 'every picture was tried: entering again fetches nothing')
    # a picture that was not tried (the job was cancelled) is fetched on the next entry, only that one
    ml = machine(site=catalog_site(reqs := []))
    got = []
    def site_cut(u, o_):
        got.append(u)
        if 'advancedsearch' in u: return {'body': SEARCH_RAW}
        if len(got) == 4: SE.cancel(ml)
        return {'body': THUMB, 'chunk': 5500, 'xfer': (lambda url, sent, total: SE.cancel(ml)) if len(got) == 4 else None}
    ml.curl_site = site_cut
    r, th = catalog(ml, '')
    st = cstate(ml)
    expect(len(got) == 4 and st['count'] == 7 and st['busy'] == 0 and st['state'] == S_DONE and st['code'] == 0 and [fn(ml, 'bn_thumb_state', i) for i in range(7)] == [1, 1, 0, 0, 0, 0, 0], f'cancelled during the third thumbnail: the rows are held, the first two pictures stay, the one cut off is untried ({len(got)} requests, {st})')
    got.clear(); ml.curl_site = catalog_site(got)
    r, th = catalog(ml, '')
    expect(r == 0 and th and len(got) == 5 and all('services/img' in u for u in got) and cstate(ml)['count'] == 7 and all(thumb(ml, i) for i in range(7)), f'entering again: the answer is held, only the {len(got)} pictures not tried are fetched')
    # cancelled while the query transfers: nothing kept
    mc = machine(site=lambda u, o_: {'body': SEARCH_RAW, 'xfer': lambda url, sent, total: SE.cancel(mc)})
    catalog(mc, '')
    st = cstate(mc)
    expect(st['state'] == S_DONE and st['code'] == PN['CANCELLED'] and st['count'] == 0 and st['busy'] == 0 and row(mc, 0) is None, f'cancelled during the query: done, PN_CANCELLED, no rows ({st})')
    got = []
    mc.curl_site = catalog_site(got)
    catalog(mc, '')
    expect(got and got[0] == POPULAR and cstate(mc)['count'] == 7, 'nothing was held: the next entry asks again')
    # after a job ended the other workers may start
    expect(fn(mc, 'pn_job_busy') == 0 and fn(mc, 'pn_dl_start') == 0 and fn(mc, 'pn_search', m.cstr('x')) == 0, 'afterwards the other workers may start')
    # the other direction: a worker of the podcasts running refuses the catalog and the preview
    mb = machine(site=lambda u, o_: {'body': SEARCH_RAW})
    mb.thread = None
    expect(fn(mb, 'pn_search', mb.cstr('x')) == 0, 'a podcast search starts')
    expect(fn(mb, 'bn_catalog', mb.cstr('')) == PN['BUSY'] and fn(mb, 'bn_preview', mb.cstr(PRIDE)) == PN['BUSY'], 'the catalog and the preview are refused while another worker runs')
    mh = machine(site=catalog_site([]))
    catalog(mh, '')
    mh.thread = None
    expect(fn(mh, 'pn_search', mh.cstr('x')) == 0, 'the other workers still start with the popular list held')
    g0 = cstate(mh)['gen']
    expect(fn(mh, 'bn_catalog', mh.cstr('')) == 0 and cstate(mh)['state'] == S_DONE and cstate(mh)['count'] == 7 and cstate(mh)['search'] == 0 and cstate(mh)['gen'] > g0 and fn(mh, 'pn_job_busy') == 1,
           'the held list is shown again without a worker even while another worker runs (a book download beside the page): state done, 7 rows')
    expect(fn(mh, 'bn_catalog', mh.cstr('x')) == PN['BUSY'] and cstate(mh)['count'] == 7, 'a search waits while another worker runs (the page asks again); the held list stays')


# ---------------------------------------------------------------------------
def preview_tests(ctx):
    expect = ctx.expect
    reqs = []
    m = machine(site=books_site(reqs))
    expect(pstate(m)['state'] == 0 and fn(m, 'bn_preview_count') == 0 and part(m, 0) is None and cover(m) is None and totals(m)[0] == 0, 'before any preview: none')
    r, th = preview(m, run=False)
    st = pstate(m)
    expect(r == 0 and th and th[0] == PSYMS['bn_pmain'] and st['state'] == 1 and st['busy'] == 1 and fn(m, 'pn_busy') == 0, f'a preview starts one worker ({st})')
    expect(m.read_cstr(fn(m, 'bn_preview_id')) == PRIDE, 'the identifier is held')
    expect(fn(m, 'bn_catalog', m.cstr('')) == PN['BUSY'] and fn(m, 'bn_preview', m.cstr('x')) == PN['BUSY'] and fn(m, 'pn_search', m.cstr('x')) == PN['BUSY'], 'a second job while it runs: PN_BUSY')
    g0 = st['gen']
    PCN.work(m, th)
    st = pstate(m)
    want = oracle_parts(FILES_RAW)
    expect(st['state'] == 2 and st['code'] == 0 and st['count'] == 8 and st['busy'] == 0 and st['gen'] > g0, f'the worker ends: done, OK, 8 parts ({st})')
    expect(reqs == [FILES_URL, IMG + PRIDE], f'the files answer, then the picture: {reqs}')
    expect([part(m, i) for i in range(8)] == want and part(m, 8) is None and part(m, -1) is None, 'the parts in order; none past the last')
    ok, np_, secs, size, more = totals(m)
    expect((ok, np_, secs, size, more) == (1, 8, sum(p[2] for p in want), sum(p[3] for p in want), 0) and secs == 1132 + 865 + 777 + 638 + 819 + 701 + 919 + 1035, f'totals: parts, seconds, bytes ({np_}, {secs}, {size})')
    expect(cover(m) == f'{DIR}/preview.jpg' and m.fs[f'{DIR}/preview.jpg'] == THUMB, 'the picture is preview.jpg')
    expect(FILES not in m.fs and not [p for p in m.fs if p.endswith('.src') or p.endswith('.json')] and len(m.curl) == 0, 'the files answer and the download file are removed, every handle cleaned up')
    expect(all(d_ in m.dirs for d_ in ('/mnt/mmc/.m1plus/audiobooks', DIR)), 'the scratch directory is made')
    # the scratch download is capped at 2 MiB and is the only copy of the answer
    o = {}
    m3 = machine(site=lambda u, o_: (o.update(o_) if '/metadata/' in u else None, {'body': FILES_RAW} if '/metadata/' in u else {'body': THUMB})[1])
    preview(m3)
    expect(o[10065] == PCN.CA and o[45] == 1 and o[99] == 1 and 64 not in o and 81 not in o, 'the same libcurl options as every request of the worker, verification on')
    # drop frees the parts and removes the picture
    m.calls = []
    fn(m, 'bn_preview_drop')
    calls = list(m.calls)
    expect(pstate(m)['state'] == 0 and fn(m, 'bn_preview_count') == 0 and part(m, 0) is None and cover(m) is None and f'{DIR}/preview.jpg' not in m.fs, 'drop: no preview, no parts, the picture gone')
    expect(any(c[0] == 'free' and c[1] for c in calls), f'drop: the parts are freed ({calls})')
    # a new preview drops the old one before it starts
    preview(m)
    reqs.clear()
    r, th = preview(m, 'other_book', run=False)
    expect(r == 0 and pstate(m)['state'] == 1 and part(m, 0) is None and cover(m) is None and f'{DIR}/preview.jpg' not in m.fs, 'a new preview drops the old one when it starts')
    PCN.work(m, th)
    expect(reqs[0] == f'{HOST}/metadata/other_book/files' and pstate(m)['count'] == 8, 'the new identifier is in the address')
    # the picture fails: the book is still shown
    m2 = machine(site=books_site([], img=lambda u: {'rc': 22, 'code': 404}))
    preview(m2)
    expect(pstate(m2)['code'] == 0 and pstate(m2)['count'] == 8 and cover(m2) is None and not [p for p in m2.fs if p.endswith('.src')], 'a picture that cannot be had leaves the placeholder; the parts stay')
    m2 = machine(site=books_site([], img=lambda u: {'body': b'<html>x</html>'}))
    preview(m2)
    expect(pstate(m2)['code'] == 0 and cover(m2) is None, 'an answer that is no picture: no cover')
    # an item with no 64Kbps MP3 part, and answers that are no files list
    for label, body, code in (('only other formats', result(obj(name='a.m4b', format='Audiobook'), obj(name='a.ogg', format='Ogg Vorbis'), obj(name='b.mp3', format='VBR MP3')), PN['NOBOOK']), ('an empty list', b'{"result":[]}', PN['NOBOOK']),
                              ('an empty object (an unknown item)', b'{}', PN['NOBOOK']), ('an HTML page', b'<html>x</html>', PN['NOBOOK']), ('an answer cut short', result(mp3('a.mp3'), mp3('b.mp3'))[:-30], PN['NOTFEED']),
                              ('names the player cannot use', result(mp3('a/b.mp3')), PN['NOBOOK'])):
        mn = machine(site=books_site(reqs := [], files=body))
        r, th = preview(mn)
        st = pstate(mn)
        expect(r == 0 and st['state'] == 2 and st['code'] == code and st['count'] == 0 and part(mn, 0) is None and totals(mn)[0] == 0 and cover(mn) is None and FILES not in mn.fs and reqs == [FILES_URL] and st['busy'] == 0,
               f'{label}: done, code {code}, no parts, no picture asked for, no file left ({st})')
    # the answer over 2 MiB
    big = result(*([mp3('a.mp3')] + [obj(name='pad.bin', format='Metadata', md5='x' * 3000)] * 800))
    mb = machine(site=books_site([], files=big))
    preview(mb)
    st = pstate(mb)
    expect(len(big) > CAP and st['code'] == PN['NOTFEED'] and FILES not in mb.fs and st['count'] == 0, f'an answer over 2 MiB: PN_NOTFEED, nothing kept, no file ({st})')
    # more than 300 parts
    many = result(*[mp3(f'p{i:04d}.mp3') for i in range(MAXP + 20)])
    mm = machine(site=books_site([], files=many))
    preview(mm)
    ok, np_, secs, size, more = totals(mm)
    expect(pstate(mm)['count'] == MAXP and np_ == MAXP and more == 1 and secs == 60 * MAXP and size == 1000 * MAXP and part(mm, MAXP - 1)[0] == f'p{MAXP - 1:04d}.mp3', f'{MAXP + 20} parts: {MAXP} kept, more set')
    # failures
    for label, site, code in (('no connection', lambda u, o_: {'rc': 6}, PN['NET']), ('a time-out', lambda u, o_: {'rc': 28}, PN['NET']), ('a certificate error', lambda u, o_: {'rc': 60}, PN['CERT']),
                              ('HTTP 503', lambda u, o_: {'rc': 22, 'code': 503}, PN['HTTP']), ('HTTP 404', lambda u, o_: {'rc': 22, 'code': 404}, PN['GONE']), ('an empty answer', lambda u, o_: {'body': b''}, PN['NET'])):
        mf = machine(site=site)
        r, th = preview(mf)
        st = pstate(mf)
        expect(r == 0 and st['state'] == 2 and st['code'] == code and st['count'] == 0 and FILES not in mf.fs and part(mf, 0) is None and st['busy'] == 0, f'{label}: done, code {code}, nothing kept, no file ({st})')
    # the guards and the bad identifiers
    for label, kw, code in (('no Wi-Fi', dict(wifi=-1), PN['NOWIFI']), ('no card', dict(card_mounted=False), PN['STORAGE']), ('a clock never set', dict(wall=1700000000), PN['NOCLOCK'])):
        mg = machine(site=books_site([]), **kw)
        r, th = preview(mg)
        expect(r == code and th is None and 'curl_global_init' not in [c[0] for c in mg.calls] and pstate(mg)['state'] == 0, f'{label}: the guard answers {code}, nothing starts')
    mg = machine(site=books_site([]), ca=False)
    expect(preview(mg)[0] == PN['NOCERT'], 'no CA bundle: PN_NOCERT')
    for ident in ('', 'a/b', 'a b', '..', 'x' * ID, 'é', 'a?b=1'):
        mg = machine(site=books_site(reqs := []))
        r, th = preview(mg, ident)
        expect(r == PN['NOBOOK'] and th is None and not reqs and pstate(mg)['state'] == 0 and 'curl_global_init' not in [c[0] for c in mg.calls], f'identifier {ident!r}: PN_NOBOOK at once, nothing started')
    mg = machine(site=books_site([]), thread_ok=False)
    r, th = preview(mg)
    expect(r == PN['MEM'] and pstate(mg)['state'] == 0 and pstate(mg)['busy'] == 0 and mg.read_cstr(fn(mg, 'bn_preview_id')) == '', 'a thread that cannot be made: PN_MEM, no preview, not busy')
    mg = machine(site=books_site([])); mg.calloc_fail = True
    preview(mg)
    st = pstate(mg)
    expect(st['code'] == PN['MEM'] and st['state'] == 2 and st['busy'] == 0 and st['count'] == 0, f'no memory for the parts: PN_MEM, done ({st})')
    # Cancel while the files answer transfers, and while the picture does
    mc = machine(site=lambda u, o_: {'body': FILES_RAW, 'xfer': lambda url, sent, total: SE.cancel(mc)} if '/metadata/' in u else {'body': THUMB})
    preview(mc)
    st = pstate(mc)
    expect(st['state'] == 0 and st['code'] == PN['CANCELLED'] and st['count'] == 0 and st['busy'] == 0 and FILES not in mc.fs and part(mc, 0) is None, f'cancelled during the files answer: no preview, PN_CANCELLED, no file ({st})')
    got = []
    mc2 = machine(site=lambda u, o_: (got.append(u), {'body': FILES_RAW} if '/metadata/' in u else {'body': THUMB, 'xfer': lambda url, sent, total: SE.cancel(mc2)})[1])
    preview(mc2)
    st = pstate(mc2)
    expect(st['state'] == 0 and st['code'] == PN['CANCELLED'] and st['count'] == 0 and cover(mc2) is None and not [p for p in mc2.fs if p.endswith('.src')] and len(got) == 2, f'cancelled during the picture: no preview, PN_CANCELLED, no file ({st})')
    expect(fn(mc2, 'pn_job_busy') == 0 and fn(mc2, 'pn_dl_start') == 0, 'afterwards the other workers may start')
    # the held preview is the one whose job ended last; a catalog job beside it does not disturb it
    mk = machine(site=lambda u, o_: {'body': SEARCH_RAW} if 'advancedsearch' in u else {'body': FILES_RAW} if '/metadata/' in u else {'body': THUMB})
    preview(mk)
    catalog(mk, '')
    expect(pstate(mk)['count'] == 8 and cstate(mk)['count'] == 7 and part(mk, 0) == oracle_parts(FILES_RAW)[0] and row(mk, 0)[0] == 'adventures_holmes', 'a preview and the catalog are held side by side')


SECTIONS = [query_tests, secs_tests, docs_tests, files_tests, catalog_tests, preview_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
