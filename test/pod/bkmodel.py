"""Audiobooks, the book model (patch/bkmodel.c, patch/books.h, docs/modules/audiobooks.md): the books on the card (folders, subfolders, loose files, dot files, the folder's
spelling), the natural order of the parts, the progress and the current part from the resume ring, and the MP4 memory guard on synthetic MP4 byte strings. The compiled
payload runs under Unicorn with the stock calls mocked (the card is Podcasts' mock: a dict of paths)."""
import importlib.util, os, random, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


PCP = sibling('podcasts')
DEFS = {}
for _line in open(os.path.join(ROOT, 'patch', 'books.h')).read().replace('\\\n', ' ').splitlines():
    _m = re.match(r'#define\s+(\w+)\s+(.+?)\s*(?:/\*.*)?$', _line.strip())
    if _m:
        _v = _m.group(2).strip()
        try: DEFS[_m.group(1)] = _v.strip('"') if _v.startswith('"') else eval(_v, {}, {})   # noqa: S307 (this repo's own header: numbers, (16 * 1024), 0xffffffffu)
        except Exception: pass   # noqa: S110
BAD = 0xffffffff
SAMPLE, SPARE = DEFS['BK_MP4_SAMPLE_BYTES'], DEFS['BK_MP4_SPARE_KB']
BOOK, PART = DEFS['BK_BOOK_SIZE'], DEFS['BK_PART_SIZE']
MAXB, MAXP, FILE, REL = DEFS['BK_MAX_BOOKS'], DEFS['BK_MAX_PARTS'], DEFS['BK_FILE'], DEFS['BK_REL']
ROOT_DIR = '/mnt/mmc/Audiobooks'
RING = PCP.RING
pc_hash = PCP.pc_hash
NOT_STARTED, IN_PROGRESS, FINISHED = 0, 1, 2
MEMINFO = '/proc/meminfo'


class BM(PCP.PM):
    """Podcasts' card machine plus the model's records."""
    def book(self, a):
        raw = bytes(self.u.mem_read(a, BOOK))
        cs = lambda b: b.split(b'\0', 1)[0].decode('utf-8', 'replace')
        parts, kb, h, loose = struct.unpack_from('<4I', raw, 352)
        return dict(dir=cs(raw[:FILE]), title=cs(raw[FILE:224]), cover=cs(raw[224:352]), parts=parts, kb=kb, hash=h, loose=loose)

    def part(self, a):
        raw = bytes(self.u.mem_read(a, PART))
        cs = lambda b: b.split(b'\0', 1)[0].decode('utf-8', 'replace')
        kb, h = struct.unpack_from('<2I', raw, 288)
        return dict(rel=cs(raw[:REL]), title=cs(raw[REL:288]), kb=kb, hash=h)

    def books(self, mx=MAXB):
        out = self.alloc(MAXB * BOOK); self.u.mem_write(out, bytes(MAXB * BOOK))
        n = self.call(PSYMS['bk_scan_books'], a0=out, a1=mx, count=400000000)
        return [self.book(out + i * BOOK) for i in range(n)], out

    def parts(self, book_addr, mx=MAXP):
        out = self.alloc(MAXP * PART); self.u.mem_write(out, bytes(MAXP * PART))
        n = self.call(PSYMS['bk_load_parts'], a0=book_addr, a1=out, a2=mx, count=400000000)
        return [self.part(out + i * PART) for i in range(n)]

    def natcmp(self, a, b):
        r = self.call(PSYMS['bk_natcmp'], a0=self.cstr(a), a1=self.cstr(b), count=2000000)
        return (r - (1 << 32)) if r >= 1 << 31 else r

    def mp4_kb(self, path):
        return self.call(PSYMS['bk_mp4_index_kb'], a0=self.cstr(path), count=20000000)

    def fits(self, path):
        return self.call(PSYMS['bk_mp4_fits'], a0=self.cstr(path), count=20000000)


def ring_file(slots):
    """The resume ring: (hash, pos, len, flags), most recent first."""
    return b'PCR1' + struct.pack('<I', len(slots)) + b''.join(struct.pack('<4I', *s) for s in slots)


def card():
    m = BM()
    for f, n in (('Part 10.mp3', 3000), ('Part 2.mp3', 2048), ('Part 1.MP3', 1025)): m.put(f'{ROOT_DIR}/The Hobbit/{f}'); m.sizes[f'{ROOT_DIR}/The Hobbit/{f}'] = n
    for f in ('cover.JPG', 'folder.png', 'notes.txt', '._Part 1.mp3', '.DS_Store'): m.put(f'{ROOT_DIR}/The Hobbit/{f}', b'x')
    for f in ('CD1/10.mp3', 'CD1/2.mp3', 'CD2/01.mp3', 'CD1/.hidden.mp3', '.trash/x.mp3', 'CD1/deep/z.mp3', 'cover.png'): m.put(f'{ROOT_DIR}/Dune/{f}', b'x')
    m.put(f'{ROOT_DIR}/alpha book/a.m4b'); m.sizes[f'{ROOT_DIR}/alpha book/a.m4b'] = 5 * 1024 * 1024
    m.put(f'{ROOT_DIR}/Zen.mp3'); m.sizes[f'{ROOT_DIR}/Zen.mp3'] = 1
    m.put(f'{ROOT_DIR}/loose story.M4B', b'x'); m.put(f'{ROOT_DIR}/.hidden/h.mp3'); m.put(f'{ROOT_DIR}/._Zen.mp3', b'x'); m.put(f'{ROOT_DIR}/Docs/readme.txt', b'x')
    m.put(f'{ROOT_DIR}/x.txt', b'x'); m.folder(f'{ROOT_DIR}/empty')
    return m


def header_tests(ctx):
    expect = ctx.expect
    expect(BOOK == 368 and PART == 296 and MAXB == 100 and MAXP == 300 and SAMPLE == 28 and SPARE == 16384 and BAD == 0xffffffff and DEFS['BK_KEY_PREFIX'] == 'audiobooks/',
           'books.h numbers: the records, the limits, 28 bytes a sample, 16 MiB spare, the key prefix')
    m = BM()
    h = m.cstr('x')
    expect(m.call(PSYMS['pc_hash'], a0=m.cstr('audiobooks/The Hobbit'), count=200000) == pc_hash('audiobooks/The Hobbit') == pc_hash('Audiobooks/THE HOBBIT'), 'the key is pc_hash (case-folded) of "audiobooks/<dir>"')
    expect(h != 0, 'the mock works')


def scan_tests(ctx):
    expect = ctx.expect
    m = card()
    books, _ = m.books()
    expect([b['dir'] for b in books] == ['alpha book', 'Dune', 'The Hobbit', 'loose story.M4B', 'Zen.mp3'],
           f'books: folders and loose files, sorted by title (case-insensitive, "The " aside); no dot folder, no folder without audio, no text file: {[b["dir"] for b in books]}')
    by = {b['dir']: b for b in books}
    expect(by['The Hobbit'] == dict(dir='The Hobbit', title='The Hobbit', cover='cover.JPG', parts=3, kb=3 + 2 + 2, hash=pc_hash('audiobooks/The Hobbit'), loose=0),
           f'a folder book: its parts (the ._ file out), its KB rounded up per file, the best cover (cover.* before folder.*), the key: {by["The Hobbit"]}')
    expect(by['Dune']['parts'] == 3 and by['Dune']['cover'] == 'cover.png' and by['Dune']['kb'] == 3 and by['Dune']['loose'] == 0,
           'subfolders count (CD1, CD2) but not dot entries and not a second level')
    expect(by['alpha book']['kb'] == 5 * 1024 and by['alpha book']['parts'] == 1 and by['alpha book']['cover'] == '', 'one big file: 5120 KB, no cover')
    expect(by['Zen.mp3'] == dict(dir='Zen.mp3', title='Zen', cover='', parts=1, kb=1, hash=pc_hash('audiobooks/Zen.mp3'), loose=1), f'a loose file: a one-part book titled by its name: {by["Zen.mp3"]}')
    expect(by['loose story.M4B']['title'] == 'loose story' and by['loose story.M4B']['loose'] == 1, 'a loose file with an upper-case extension')
    expect(len(m.books(2)[0]) == 2, 'max limits the count')
    # the folder's spelling
    m2 = BM(); m2.put('/mnt/mmc/AUDIOBOOKS/B/b.mp3', b'x')
    out = m2.alloc(160)
    expect(m2.call(PSYMS['bk_root'], a0=out, count=2000000) == 1 and m2.read_cstr(out) == '/mnt/mmc/AUDIOBOOKS' and [b['dir'] for b in m2.books()[0]] == ['B'], 'the root is found case-insensitively')
    b2 = m2.books()[0][0]
    expect(b2['hash'] == pc_hash('audiobooks/B'), 'the key does not depend on the root folder\'s spelling')
    m3 = BM(); m3.put('/mnt/mmc/Music/a.mp3', b'x')
    expect(m3.call(PSYMS['bk_root'], a0=out, count=2000000) == 0 and m3.read_cstr(out) == ROOT_DIR and m3.books()[0] == [], 'no Audiobooks folder: no root, no books')
    m4 = BM()
    for i in range(120): m4.put(f'{ROOT_DIR}/b{i:03}.mp3', b'x')
    expect(len(m4.books()[0]) == MAXB, 'at most BK_MAX_BOOKS books')
    m5 = BM(); m5.put(f'{ROOT_DIR}/' + 'n' * 130 + '.mp3', b'x'); m5.put(f'{ROOT_DIR}/' + 'd' * 130 + '/a.mp3', b'x'); m5.put(f'{ROOT_DIR}/ok.mp3', b'x')
    expect([b['dir'] for b in m5.books()[0]] == ['ok.mp3'], 'a name too long for the buffers is skipped')
    m6 = BM(); m6.put(f'{ROOT_DIR}/Bk/a.mp3', b'x'); m6.fail.add(('__xstat', f'{ROOT_DIR}/Bk/a.mp3'))
    expect(m6.books()[0] == [], 'a file stat cannot see does not make a book')


NAT = [('Part 2', 'Part 10', -1), ('Part 10', 'Part 2', 1), ('CD1/10.mp3', 'CD2/01.mp3', -1), ('CD1/2.mp3', 'CD1/10.mp3', -1), ('Chapter 9 b', 'Chapter 10', -1),
       ('a', 'a1', -1), ('abc', 'ABD', -1), ('x99999999999999999999', 'x100000000000000000000', -1), ('CD1', 'CD1/a', -1), ('CD1/a', 'CD1 b/a', -1),
       ('track 007', 'track 8', -1), ('b', 'a', 1), ('Same', 'Same', 0), ('1', '2', -1), ('10', '9', 1), ('a0b', 'a00b', 0)]


def natural_tests(ctx):
    expect = ctx.expect
    m = BM()
    for a, b, want in NAT:
        got = m.natcmp(a, b)
        if want == 0 and a != b: expect(got != 0 or a == b, f'{a!r} vs {b!r}: equal numbers are told apart by a plain compare')
        else: expect(got == want, f'natcmp({a!r}, {b!r}) is {want}, got {got}')
        expect(m.natcmp(b, a) == -got, f'natcmp is antisymmetric for {a!r}, {b!r}')
    expect(m.natcmp('file01', 'file1') != 0 and m.natcmp('a', 'A') != 0 and m.natcmp('A', 'a') == -m.natcmp('a', 'A'), 'case and leading zeros: never equal, always ordered')
    names = ['Part 10.mp3', 'part 2.mp3', 'Part 1.mp3', 'Part 100.mp3', 'Part 9.mp3', 'Intro.mp3', 'CD1/01.mp3', 'CD1/10.mp3', 'CD2/01.mp3']
    want = ['CD1/01.mp3', 'CD1/10.mp3', 'CD2/01.mp3', 'Intro.mp3', 'Part 1.mp3', 'part 2.mp3', 'Part 9.mp3', 'Part 10.mp3', 'Part 100.mp3']
    rnd = random.Random(7)
    ok = True
    for _ in range(5):
        shuffled = names[:]; rnd.shuffle(shuffled)
        ok &= sorted(shuffled, key=__import__('functools').cmp_to_key(m.natcmp)) == want
    expect(ok, 'a shuffled list sorts into reading order')


def parts_tests(ctx):
    expect = ctx.expect
    m = card()
    books, addr = m.books()
    at = {b['dir']: addr + i * BOOK for i, b in enumerate(books)}
    ps = m.parts(at['The Hobbit'])
    expect([p['rel'] for p in ps] == ['Part 1.MP3', 'Part 2.mp3', 'Part 10.mp3'] and [p['title'] for p in ps] == ['Part 1', 'Part 2', 'Part 10'] and [p['kb'] for p in ps] == [2, 2, 3],
           f'parts in natural order, titles without extension, sizes: {ps}')
    expect([p['hash'] for p in ps] == [pc_hash(f'{ROOT_DIR}/The Hobbit/{p["rel"]}') for p in ps], 'the ring key of a part is pc_hash of its full path')
    ds = m.parts(at['Dune'])
    expect([p['rel'] for p in ds] == ['CD1/2.mp3', 'CD1/10.mp3', 'CD2/01.mp3'] and [p['title'] for p in ds] == ['2', '10', '01'], f'subfolders: CD1 before CD2, numbers by value: {[p["rel"] for p in ds]}')
    ls = m.parts(at['Zen.mp3'])
    expect(len(ls) == 1 and ls[0]['rel'] == 'Zen.mp3' and ls[0]['title'] == 'Zen' and ls[0]['hash'] == pc_hash(f'{ROOT_DIR}/Zen.mp3') and ls[0]['kb'] == 1, f'a loose book has one part: its file: {ls}')
    expect(len(m.parts(at['The Hobbit'], 2)) == 2, 'max limits the count')
    out = m.alloc(400); part = addr + 0   # (any part record: the loose path ignores rel)
    pa = m.alloc(PART); m.u.mem_write(pa, bytes(PART)); m.u.mem_write(pa, b'Part 2.mp3\0')
    ok = m.call(PSYMS['bk_part_path'], a0=at['The Hobbit'], a1=pa, a2=out, a3=400, count=2000000)
    expect(ok == 1 and m.read_cstr(out) == f'{ROOT_DIR}/The Hobbit/Part 2.mp3', 'the full path of a part')
    expect(m.call(PSYMS['bk_part_path'], a0=at['The Hobbit'], a1=pa, a2=out, a3=20, count=2000000) == 0, 'a path that does not fit is refused')
    expect(m.call(PSYMS['bk_part_path'], a0=at['Zen.mp3'], a1=pa, a2=out, a3=400, count=2000000) == 1 and m.read_cstr(out) == f'{ROOT_DIR}/Zen.mp3', 'a loose book\'s path is its file')
    del part
    m2 = BM()
    for i in range(320): m2.put(f'{ROOT_DIR}/Big/{i:03}.mp3', b'x')
    m2.put(f'{ROOT_DIR}/Big/' + 'q' * 140 + '.mp3', b'x'); m2.put(f'{ROOT_DIR}/Big/' + 'q' * 200 + '/a.mp3', b'x')
    b2, a2 = m2.books()
    expect(b2[0]['parts'] == 320 + 0 and len(m2.parts(a2)) == MAXP, f'a book of 320 files: counted whole ({b2[0]["parts"]}), loaded up to BK_MAX_PARTS')
    m3 = BM(); m3.put(f'{ROOT_DIR}/B/' + 'p' * 100 + '/' + 'f' * 100 + '.mp3', b'x'); m3.put(f'{ROOT_DIR}/B/a.mp3', b'x')
    b3, a3 = m3.books()
    expect([p['rel'] for p in m3.parts(a3)] == ['a.mp3'], 'a path too long for a part is skipped')


def progress(m, parts, slots=None):
    """(state, permille, current) of parts [(kb, hash)] against a ring."""
    if slots is not None: m.fs[RING] = ring_file(slots)
    arr = m.alloc(max(len(parts), 1) * PART); m.u.mem_write(arr, bytes(max(len(parts), 1) * PART))
    for i, (kb, h) in enumerate(parts): m.u.mem_write(arr + i * PART + 288, struct.pack('<2I', kb, h))
    pm, cur = m.alloc(4), m.alloc(4)
    r = m.call(PSYMS['bk_progress'], a0=arr, a1=len(parts), a2=pm, a3=cur, count=20000000)
    c = m.s32(cur)
    return r, m.word(pm), c


def progress_tests(ctx):
    expect = ctx.expect
    P = [(100, 11), (100, 12), (200, 13), (600, 14)]
    H = [h for _, h in P]
    cases = [
        ('no ring file: not started', None, (NOT_STARTED, 0, 0)),
        ('first part done: the second is next, 10 % of the bytes', [(H[0], 0, 60, 1)], (IN_PROGRESS, 100, 1)),
        ('the second part half played, the first done', [(H[1], 30, 60, 0), (H[0], 0, 60, 1)], (IN_PROGRESS, 150, 1)),
        ('the most recent is a done part: the one after it; the older place counts', [(H[2], 0, 60, 1), (H[0], 10, 100, 0)], (IN_PROGRESS, 210, 3)),
        ('the last part done, earlier ones not: back to the first one not done', [(H[3], 0, 60, 1)], (IN_PROGRESS, 600, 0)),
        ('the last part done, the first two done: the third', [(H[3], 0, 60, 1), (H[1], 0, 60, 1), (H[0], 0, 60, 1)], (IN_PROGRESS, 800, 2)),
        ('the most recent is a place in the first part (the last one done long ago): the first', [(H[0], 20, 100, 0), (H[3], 0, 60, 1)], (IN_PROGRESS, 620, 0)),
        ('a done part, then the next done too: the one after both', [(H[0], 0, 60, 1), (H[1], 0, 60, 1)], (IN_PROGRESS, 200, 2)),
        ('every part done: finished', [(H[i], 0, 60, 1) for i in (3, 2, 1, 0)], (FINISHED, 1000, 4)),
        ('a slot with no place and no mark is not touched (pc_state: new)', [(H[2], 0, 0, 0)], (NOT_STARTED, 0, 0)),
        ('a place past its length counts the whole part', [(H[1], 90, 60, 0)], (IN_PROGRESS, 100, 1)),
        ('keys of another book change nothing', [(999, 5, 60, 0)], (NOT_STARTED, 0, 0)),
    ]
    for what, slots, want in cases:
        m = BM(); got = progress(m, P, slots)
        expect(got == want, f'{what}: {got} (want {want})')
    m = BM()
    expect(progress(m, [], None) == (NOT_STARTED, 0, 0), 'no parts: not started')
    big = [(4000000, 21), (4000000, 22), (4000000, 23)]
    expect(progress(m, big, [(21, 0, 60, 1)]) == (IN_PROGRESS, 333, 1), 'three 4 GB parts, one done: a third, no 32-bit overflow')
    expect(progress(BM(), [(0, 31), (0, 32)], [(31, 0, 60, 1)]) == (IN_PROGRESS, 500, 1), 'parts without a size weigh one unit each')
    expect(progress(BM(), [(1000, 41)], [(41, 3000000, 4000000, 0)]) == (IN_PROGRESS, 750, 0), 'a place deep in a very long file')
    m = BM(); m.call(PSYMS['pc_mark'], a0=H[1], a1=1, count=30000000); m.call(PSYMS['pc_mark'], a0=H[0], a1=1, count=30000000)
    expect(progress(m, P) == (IN_PROGRESS, 200, 2), 'the live ring (pc_mark): the most recent mark is the first part, then the second; the third is next')
    m = BM(); m.call(PSYMS['pc_mark'], a0=H[0], a1=1, count=30000000); m.call(PSYMS['pc_mark'], a0=H[1], a1=1, count=30000000)
    expect(progress(m, P) == (IN_PROGRESS, 200, 2), 'the live ring: marks in the other order give the same next part (both done)')
    m = BM(); m.call(PSYMS['pc_mark'], a0=H[2], a1=1, count=30000000); m.call(PSYMS['pc_mark'], a0=H[0], a1=1, count=30000000)
    expect(progress(m, P) == (IN_PROGRESS, 300, 1), 'the live ring: the most recent done is the first: the second is next')


def box(kind, payload=b''):
    return struct.pack('>I', 8 + len(payload)) + kind + payload


def stsz(count, kind=b'stsz'):
    return box(kind, struct.pack('>III', 0, 0, count))


def moov(*stbl_children, traks=1):
    stbl = box(b'stbl', b''.join(stbl_children))
    trak = box(b'trak', box(b'tkhd', bytes(20)) + box(b'mdia', box(b'minf', stbl)))
    return box(b'moov', box(b'mvhd', bytes(20)) + trak * traks)


FTYP = box(b'ftyp', b'M4B \0\0\0\0M4B ')
MDAT = box(b'mdat', bytes(64))


def kb_of(samples): return (samples * SAMPLE + 1023) >> 10


def mp4_tests(ctx):
    expect = ctx.expect
    P = '/mnt/mmc/Audiobooks/Long/book.m4b'

    def machine(data, path=P, avail=None, path_fail=False):
        m = BM(); m.put(path, data)
        if avail is not None: m.fs[MEMINFO] = f'MemTotal:  120000 kB\nMemFree:   9999 kB\nMemAvailable:  {avail} kB\nBuffers: 1 kB\n'.encode()
        return m
    small = FTYP + MDAT + moov(stsz(1000))
    expect(machine(small).mp4_kb(P) == kb_of(1000) == 28, 'a small book: 1000 samples, 28 bytes each, 28 KB')
    expect(machine(FTYP + moov(stsz(1000)) + MDAT).mp4_kb(P) == 28, 'moov before mdat')
    expect(machine(small, avail=60000).fits(P) == 1, 'a small book fits 60000 KB available')
    huge = 4_000_000_000
    mh = machine(FTYP + MDAT + moov(stsz(huge)), avail=60000)
    expect(mh.mp4_kb(P) == min(kb_of(huge), BAD - 1) or mh.mp4_kb(P) == BAD, 'a huge sample count: its index in KB (or too big)')
    expect(mh.fits(P) == 0, 'a huge sample count is refused')
    count = 1_000_000
    need = kb_of(count)
    expect(machine(FTYP + MDAT + moov(stsz(count)), avail=need + SPARE).fits(P) == 1, 'exactly MemAvailable less 16 MiB fits')
    expect(machine(FTYP + MDAT + moov(stsz(count)), avail=need + SPARE - 1).fits(P) == 0, 'one KB less does not fit')
    expect(machine(FTYP + MDAT + moov(stsz(10)), avail=SPARE + 1).fits(P) == 1 and machine(FTYP + MDAT + moov(stsz(10)), avail=SPARE).fits(P) == 0, 'a tiny book (1 KB of index, rounded up) fits when MemAvailable covers it and the spare')
    expect(machine(FTYP + MDAT + moov(stsz(10)), avail=SPARE - 1).fits(P) == 0, 'below the spare nothing fits')
    expect(machine(FTYP + MDAT + moov(stsz(777, b'stz2'))).mp4_kb(P) == kb_of(777), 'stz2 counts like stsz')
    expect(machine(FTYP + MDAT + moov(stsz(300), traks=2)).mp4_kb(P) == kb_of(600), 'every track adds its samples')
    big64 = struct.pack('>I', 1) + b'moov' + struct.pack('>Q', 16 + len(moov(stsz(5))) - 8) + moov(stsz(5))[8:]
    expect(machine(FTYP + big64).mp4_kb(P) == kb_of(5), 'a 64-bit box size')
    to_end = struct.pack('>I', 0) + b'moov' + moov(stsz(9))[8:]
    expect(machine(FTYP + MDAT + to_end).mp4_kb(P) == kb_of(9), 'a box with size 0 runs to the end of the file')
    expect(machine(FTYP + MDAT + moov(stsz(3)), path='/mnt/mmc/Audiobooks/Long/BOOK.M4A').mp4_kb('/mnt/mmc/Audiobooks/Long/BOOK.M4A') == kb_of(3)
           and machine(FTYP + MDAT + moov(stsz(3)), path='/mnt/mmc/Audiobooks/x.mp4').mp4_kb('/mnt/mmc/Audiobooks/x.mp4') == kb_of(3), '.M4A and .mp4 are guarded too')
    # not an MP4: nothing to guard, nothing read
    for other in ('/mnt/mmc/Audiobooks/a.mp3', '/mnt/mmc/Audiobooks/a.flac', '/mnt/mmc/Audiobooks/x.m4b/track', '/mnt/mmc/Audiobooks/m4b'):
        m = machine(b'junk', path=other)
        expect(m.mp4_kb(other) == 0 and m.fits(other) == 1 and not any(c[0] in ('open', 'read') for c in m.calls), f'{other}: not an MP4, not read')
    # refused
    junk = random.Random(3).randbytes(300)
    refused = {
        'a missing file': None, 'an empty file': b'', 'garbage': junk, 'text': b'ID3\3\0\0\0\0\0\0' * 20,
        'no sample table': FTYP + MDAT + box(b'moov', box(b'mvhd', bytes(20))),
        'a box smaller than its header': FTYP + struct.pack('>I', 4) + b'free' + bytes(8),
        'a box larger than the file': FTYP + struct.pack('>I', 5000) + b'mdat' + bytes(64),
        'moov larger than the file': FTYP + MDAT + moov(stsz(5))[:-6],
        'a nested box past its parent': FTYP + box(b'moov', box(b'trak', struct.pack('>I', 500) + b'mdia' + bytes(20))),
        'a short stsz': FTYP + moov(box(b'stsz', bytes(8))),
        'a 64-bit size with high bits': FTYP + struct.pack('>I', 1) + b'moov' + struct.pack('>Q', 1 << 40) + bytes(8),
        'a 64-bit size cut short': FTYP + struct.pack('>I', 1) + b'moov' + bytes(3),
        'half a header': FTYP + b'\0\0\0',
        'a 64-bit size smaller than its header': FTYP + struct.pack('>I', 1) + b'moov' + struct.pack('>Q', 8),
    }
    for what, data in refused.items():
        m = BM()
        if data is not None: m.put(P, data)
        m.fs[MEMINFO] = b'MemAvailable: 99999999 kB\n'
        expect(m.mp4_kb(P) == BAD and m.fits(P) == 0, f'refused: {what}')
    m = machine(small, avail=99999999); m.fail.add(('open', P))
    expect(m.mp4_kb(P) == BAD and m.fits(P) == 0, 'refused: a file that cannot be opened (a 2 GB file, EOVERFLOW)')
    tiny = b''.join(box(b'free') for _ in range(100000))
    m = machine(FTYP + tiny + moov(stsz(1)))
    expect(m.mp4_kb(P) == BAD and len([c for c in m.calls if c[0] == 'read']) <= DEFS['BK_MP4_MAX_READS'] + 4, 'refused: more boxes than the read budget, and the reads are bounded')
    # every proper prefix of a valid file is refused unless it ends on a box boundary after moov
    full = FTYP + moov(stsz(40)) + MDAT
    after = len(FTYP) + len(moov(stsz(40)))
    edges = set(range(after, after + 8)) | {len(full)}   # (fewer than 8 bytes after a box cannot be a box header: ignored, as the demuxer does)
    seen = 0
    m = BM()
    for cut in range(len(full) + 1):
        m.put(P, full[:cut])
        got = m.mp4_kb(P)
        seen += (got == BAD) == (cut not in edges)
    expect(seen == len(full) + 1, f'every truncation of a valid file is refused, except after moov ({seen} of {len(full) + 1} as expected)')
    rnd = random.Random(11)
    ok = True
    for _ in range(120):
        d = bytearray(full)
        for _ in range(rnd.randint(1, 6)): d[rnd.randrange(len(d))] = rnd.randrange(256)
        m.put(P, bytes(d))
        got = m.mp4_kb(P)
        ok &= got == BAD or got < (1 << 31)
    expect(ok, 'random corruption never crashes the walk and never yields an absurd value')
    # MemAvailable
    parse = lambda text: m.call(PSYMS['bk_parse_meminfo'], a0=m.cstr(text), count=2000000)
    expect(parse('MemTotal: 1 kB\nMemFree: 77 kB\nMemAvailable:   123456 kB\nBuffers: 1 kB\n') == 123456, 'MemAvailable is the one line read (not MemFree)')
    expect(parse('MemAvailable:\t 5 kB') == 5 and parse('MemAvailable:7') == 7, 'blanks and a missing unit')
    expect(parse('MemFree: 5 kB\n') == 0 and parse('') == 0 and parse('MemAvailable: kB') == 0 and parse('MemAvailable:  \n') == 0 and parse('MemAvailabl') == 0, 'no line, no number: 0')
    expect(parse('MemAvailable: 99999999999999999999 kB') == 0, 'an absurd number is no estimate')
    m = machine(small); m.put(MEMINFO, b'MemTotal: 5 kB\n')
    expect(m.fits(P) == 0, 'no MemAvailable line: refused')
    m = machine(small)
    expect(m.fits(P) == 0, 'no /proc/meminfo: refused')


SECTIONS = [header_tests, scan_tests, natural_tests, parts_tests, progress_tests, mp4_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
