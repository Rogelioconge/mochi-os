"""Up Next: Play Next / Play After (patch/upnext.c, pod_queue_insert in patch/shuffle.c; docs/modules/queue.md "Up Next: Play Next / Play After"). The compiled payload under Unicorn;
the player is the machine's queue (the deque at PLAY_QUEUE), its position and mode, the Shuffle flag file, and the gapless preload state. The stock calls are modelled as read from the
disassembly: mclSetGaplessMode(0) with a preload open sends closegapless and stores -1 (harness), mclSetPlayPos stores the position, _deque_push_back copies a record, start_player copies
the queue. Sections: the insert in each mode, Shuffle's saved order kept as a permutation (Shuffle off after Play Next / Play After), the gapless cancel, the refusals, nothing playing,
the payload lock (taken around the insert; interleavings with a reorder, a load and a clear)."""
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
from unicorn.mips_const import UC_MIPS_REG_PC as PC_, UC_MIPS_REG_SP as SP_, UC_MIPS_REG_RA as RA_, UC_MIPS_REG_T9 as T9_

SHM = sibling('shuffle')
D = pod.DATA
PRELOAD, GSET, PLAY_Q, CLASS = (D[n][0] for n in ('MCL_PRELOAD', 'MCL_GAPLESS', 'PLAY_QUEUE', 'G_CLASS_TYPE'))
SH, OR, RO, RA = O['MODE_SHUFFLE'], O['MODE_ORDER'], O['MODE_REPEAT_ONE'], O['MODE_REPEAT_ALL']
ADDED, STARTED, EMPTY, STREAM, FOLDER, PODCAST, MISSING, FULL, MEMORY, DLNA = 1, 2, -1, -2, -3, -4, -5, -6, -7, -8
KILL = '/mnt/mmc/m1plus-off'
NEG = 0xffffffff
MAX = O['SHUFFLE_MAX']


class UM(SHM.HookedMachine):
    """The Shuffle machine plus what Up Next calls: the play type, _deque_push_back that copies a record (libcstl deep-copies it), start_player that copies the queue."""
    ptype = 0
    radio = 0   # rd_running (patch/radio.h): a station connects, plays or is paused

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.handlers[PSYMS['rd_running']] = 'rd_running'
        for n in ('mclGetPlayType', 'start_player'): self.handlers[pod.FUNCTIONS[n][2]] = n   # (_deque_push_back is a libc-style stub, already trapped)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        if name not in ('mclGetPlayType', 'start_player', '_deque_push_back', 'rd_running'): return super()._hook(u, address, size, _)
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        ret = 0
        if name == 'mclGetPlayType': ret = self.ptype
        elif name == 'rd_running': ret = self.radio
        elif name == 'start_player':   # (queue, index, class, mode): the player's queue is a copy
            self.calls.append(('start_player', a1, a2, a3, len(self.deques[a0])))
            copies = []
            for r in self.deques[a0]:
                c = self.alloc(REC_SIZE); u.mem_write(c, bytes(u.mem_read(r, REC_SIZE))); copies.append(c)
            self.setword(PLAY_Q, self.new_deque(copies)); self.play_pos = a1
        else:
            copy = self.alloc(REC_SIZE); u.mem_write(copy, bytes(u.mem_read(a1, REC_SIZE))); self.deques.setdefault(a0, []).append(copy)
            self.calls.append(('_deque_push_back', a0, a1))
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))


def machine(n=12, pos=3, mode=0, flag=False, boot=True):
    """The player on n songs (/mnt/mmc/q/00.flac ...) at pos; the Gapless setting on."""
    m = UM()
    m.mode = mode
    if flag: m.fs[SHM.FLAG_FILE] = b'1\n'
    m.play([SHM.song(m, f'/mnt/mmc/q/{i:02d}.flac', f'Album {i // 4}', i % 4 + 1) for i in range(n)], pos)
    if boot: m.call(PSYMS['sh_set_mode'], a0=mode, count=900000000)
    m.u.mem_write(GSET, b'\1')
    m.calls = []
    return m


def shuffled(n=12, pos=3, repeat=None):
    """The same with Shuffle on (the songs after pos reordered, the original order kept), and Repeat all or one when asked."""
    m = machine(n, pos)
    SHM.hook(m, SH)
    if repeat is not None: m.call(PSYMS['pod_set_repeat'], a0=repeat, count=900000000)
    m.calls = []
    return m


def signed(r): return r if r < 0x80000000 else r - 2 ** 32
def qpaths(m): return [m.read_cstr(m.word(r + O['REC_PATH'])) for r in m.deques[m.word(PLAY_Q)]]
def names(m, kind): return [c for c in m.calls if c[0] == kind]
def orig_of(m):
    """(the pointer, n, the words) of the saved order: the payload's `sh` struct (loaded, on, keep, fresh, booted, pad; orig at +8, n at +12). The compiler splits the struct into
    sh.0 .. sh.6 (field by field), so the symbols of the two fields are used, or the struct's own when it is kept whole."""
    p, n = m.word(PSYMS['sh.5'] if 'sh.5' in PSYMS else PSYMS['sh'] + 8), m.word(PSYMS['sh.6'] if 'sh.6' in PSYMS else PSYMS['sh'] + 12)
    return p, n, ([m.word(p + 4 * i) for i in range(n)] if p else None)
def is_perm(o, size): return o is not None and sorted(o) == list(range(size))
ORIG = lambda n=12: [f'/mnt/mmc/q/{i:02d}.flac' for i in range(n)]
X = lambda *tags: [f'/mnt/mmc/x/{t}.flac' for t in tags]


def new_rows(m, tags, base='/mnt/mmc/x'):
    """A deque of stSongInfo rows (their files exist on the card)."""
    recs = []
    for t in tags:
        recs.append(m.record(album='X', artist='X', path=f'{base}/{t}.flac', title=t, name=f'{t}.flac', rid=900))
        m.present.add(f'{base}/{t}.flac')
    return m.new_deque(recs)


def add(m, rows, after=0): return signed(m.call(PSYMS['upnext_add'], a0=rows, a1=after, count=900000000))
def expected_off(playing, adds, n=12):
    """The original order with the adds applied the way Apple does: Play Next right after the playing song (newest first), Play After at the end."""
    exp = ORIG(n)
    for tags, after in adds:
        rows = X(*tags)
        if after: exp = exp + rows
        else: i = exp.index(playing) + 1; exp[i:i] = rows
    return exp


def snapshot(m):
    p, n, o = orig_of(m)
    return (qpaths(m), p, n, o, m.play_pos, m.word(PRELOAD), bytes(m.u.mem_read(GSET, 1)), m.mode, SHM.flag_on(m))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def insert_tests(ctx):
    """1. The insert in List play, Repeat one and Repeat all: Play Next at the play position + 1 (newest first, a call's rows in order), Play After at the end; copies, the class stamp."""
    expect = ctx.expect
    for mode in (OR, RO, RA):
        m = machine(n=6, pos=1, mode=mode)
        for r in m.deques[m.word(PLAY_Q)]: m.setword(r + O['REC_CLASS'], 0xf001)
        rows = new_rows(m, ['a'])
        expect(add(m, rows) == ADDED and qpaths(m) == ORIG(6)[:2] + X('a') + ORIG(6)[2:], f'mode {mode}, Play Next: the row is at pos + 1, the rest moved up ({qpaths(m)})')
        expect(m.word(m.deques[m.word(PLAY_Q)][2] + O['REC_CLASS']) == 0xf001, f'mode {mode}: the new row carries the queue\'s class (what loadSongList stamps)')
        expect(m.deques[rows][0] != m.deques[m.word(PLAY_Q)][2] and m.word(m.deques[rows][0] + O['REC_CLASS']) == 0, 'the caller\'s row is copied: it keeps its own record')
        expect(m.play_pos == 1 and m.mode == mode and orig_of(m)[0] == 0, 'the play position and the mode stay; no saved order outside Shuffle')
        add(m, new_rows(m, ['b']))
        expect(qpaths(m)[1:5] == [ORIG(6)[1]] + X('b', 'a') + [ORIG(6)[2]], f'mode {mode}: a second Play Next goes in front of the first ({qpaths(m)[:5]})')
        add(m, new_rows(m, ['z']), after=1)
        expect(qpaths(m)[-1] == X('z')[0] and len(qpaths(m)) == 9, f'mode {mode}: Play After appends')
    m = machine(n=6, pos=1)
    expect(add(m, new_rows(m, ['a', 'b', 'c'])) == ADDED and qpaths(m) == ORIG(6)[:2] + X('a', 'b', 'c') + ORIG(6)[2:], f'Play Next of three rows keeps their order ({qpaths(m)})')
    m = machine(n=6, pos=1)
    expect(add(m, new_rows(m, ['a', 'b']), after=1) == ADDED and qpaths(m) == ORIG(6) + X('a', 'b'), 'Play After appends the rows in order')
    add(m, new_rows(m, ['c']), after=1)
    expect(qpaths(m)[-3:] == X('a', 'b', 'c'), 'and a second Play After goes behind the first')
    m = machine(n=6, pos=5)
    expect(add(m, new_rows(m, ['a'])) == ADDED and qpaths(m) == ORIG(6) + X('a'), 'Play Next on the last song is the end of the queue')
    m = machine(n=6, pos=0)
    expect(add(m, new_rows(m, ['a'])) == ADDED and qpaths(m)[:3] == [ORIG(6)[0]] + X('a') + [ORIG(6)[1]], 'Play Next on the first song')
    m = machine(n=6, pos=1)
    add(m, new_rows(m, ['a']))
    expect(not [c for c in m.calls if c[0] in ('stock_setmode', 'mclSetPlayMode', 'mclSetPlayPos', 'start_player')], 'the insert sets no mode and no position')


def shuffle_tests(ctx):
    """2. Shuffle on (the payload's flag; stock plays the shuffled queue in order): the rows go at pos + 1 / the end of the shuffled queue, the saved order stays a permutation,
    and Shuffle off puts the original order back with the added songs right after the playing song."""
    expect = ctx.expect
    for rep, label in ((None, 'Repeat off'), (RA, 'Repeat all'), (RO, 'Repeat one')):
        m = shuffled(repeat=rep)
        s = qpaths(m); p = s[3]
        expect(add(m, new_rows(m, ['a', 'b'])) == ADDED and qpaths(m) == s[:4] + X('a', 'b') + s[4:], f'Shuffle + {label}, Play Next of two rows: after the playing song of the shuffled queue ({qpaths(m)})')
        ptr, n, o = orig_of(m)
        expect(n == 14 and is_perm(o, 14) and m.play_pos == 3, f'the saved order grew to 14 and is a permutation ({o})')
        expect(add(m, new_rows(m, ['c'])) == ADDED and qpaths(m)[4] == X('c')[0] and is_perm(orig_of(m)[2], 15), 'a second Play Next goes in front of the first; still a permutation')
        expect(add(m, new_rows(m, ['d']), after=1) == ADDED and qpaths(m)[-1] == X('d')[0] and is_perm(orig_of(m)[2], 16) and orig_of(m)[1] == 16, 'Play After appends; still a permutation')
        SHM.hook(m, OR)
        exp = expected_off(p, [(('a', 'b'), 0), (('c',), 0), (('d',), 1)])
        expect(qpaths(m) == exp and qpaths(m)[m.play_pos] == p and not SHM.flag_on(m), f'Shuffle + {label} then Shuffle off: the original order, c a b right after the playing song, d last, the play position on it ({qpaths(m)})')
        expect(orig_of(m)[0] == 0 and len(set(m.word(r + O['REC_PATH']) for r in m.deques[m.word(PLAY_Q)])) == 16, 'the order is dropped after the restore; every record owns its path string')
    # the playing position moved on before Shuffle off: the playing song stays, whichever it is
    for step, label in ((1, 'the added song'), (2, 'a song of the queue')):
        m = shuffled()
        p0 = qpaths(m)[3]
        add(m, new_rows(m, ['a']))
        m.play_pos = 3 + step
        p = qpaths(m)[m.play_pos]
        SHM.hook(m, OR)
        expect(qpaths(m) == expected_off(p0, [(('a',), 0)]) and qpaths(m)[m.play_pos] == p, f'playing {label} when Shuffle goes off: the original order with the row after the song that was playing, the playing song kept ({m.play_pos})')
    # Shuffle on after the adds: the new size is shuffled again from the playing song
    m = machine(); add(m, new_rows(m, ['a', 'b'])); before = qpaths(m)
    SHM.hook(m, SH)
    expect(qpaths(m)[:4] == before[:4] and sorted(qpaths(m)) == sorted(before) and is_perm(orig_of(m)[2], 14) and orig_of(m)[1] == 14, 'Shuffle turned on after an add shuffles the 14 songs after the playing one')
    SHM.hook(m, OR)
    expect(qpaths(m) == before, 'and off again restores the queue as it was with the adds')
    # Shuffle on with a one-song queue keeps no order: the add still works, off keeps the order
    m = machine(n=1, pos=0); SHM.hook(m, SH)
    expect(orig_of(m)[0] == 0 and add(m, new_rows(m, ['a'])) == ADDED and orig_of(m)[0] == 0 and qpaths(m) == ORIG(1) + X('a'), 'a one-song queue under Shuffle keeps no order and takes the row')
    # a stale order (the queue changed size since) is dropped by the insert, not trusted
    m = shuffled(); m.deques[m.word(PLAY_Q)].pop()
    expect(add(m, new_rows(m, ['a'])) == ADDED and orig_of(m)[0] == 0 and len(qpaths(m)) == 12, 'a saved order of another size is dropped (the queue is 11 + 1 = 12 again, the size must not look valid)')
    SHM.hook(m, OR)
    expect(not [c for c in m.calls if c[0] == 'mclSetPlayPos'], 'and Shuffle off then has nothing to restore')
    # the queue holds the allocations a shuffle makes: one array of 4 bytes a song, the old one freed
    m = shuffled(); old = orig_of(m)[0]; m.calls = []
    add(m, new_rows(m, ['a']))
    expect([c[1] for c in names(m, 'calloc')] == [4 * 13] and ('free', old) in m.calls and orig_of(m)[0] != old, 'one new array of 4 bytes a song; the old one is freed')


def gapless_tests(ctx):
    """3. The one gapless cancel (patch/shuffle.c cancel_preload): mclSetGaplessMode(0) then (old), only when the insert is at pos + 1 and a preload is open; never a stock mode call."""
    expect = ctx.expect
    seq = lambda m: [c for c in m.calls if c[0] in ('mclSetGaplessMode', 'closegapless', 'stock_setmode', 'mclSetPlayMode')]
    for label, after, pos, n in (('Play Next', 0, 1, 6), ('Play After on the last song', 1, 5, 6), ('Play Next on the last song', 0, 5, 6)):
        m = machine(n=n, pos=pos); m.setword(PRELOAD, 1); m.calls = []
        expect(add(m, new_rows(m, ['a']), after) == ADDED and seq(m) == [('mclSetGaplessMode', 0), ('closegapless',), ('mclSetGaplessMode', 1)], f'{label}, preload open: closed through the Gapless setter, 0 then the old value ({seq(m)})')
        expect(m.s32(PRELOAD) == -1 and m.u.mem_read(GSET, 1)[0] == 1, f'{label}: the state is -1 (closed) and the Gapless setting is back on')
        c = [x[0] for x in m.calls]
        expect(c.index('lock') < c.index('mclSetGaplessMode') < c.index('unlock'), f'{label}: the cancel runs under the payload lock')
    m = machine(n=6, pos=1); m.setword(PRELOAD, 1); m.calls = []
    add(m, new_rows(m, ['a']), after=1)
    expect(not seq(m) and m.word(PRELOAD) == 1, 'Play After in the middle of the queue leaves the open preload alone (it is of pos + 1)')
    for state in (0, NEG):
        m = machine(n=6, pos=1); m.setword(PRELOAD, state); m.calls = []
        add(m, new_rows(m, ['a']))
        expect(not seq(m) and m.word(PRELOAD) == state, f'preload state {signed(state)}: nothing to cancel, nothing called')
    m = machine(n=6, pos=1); m.setword(PRELOAD, 1); m.u.mem_write(GSET, b'\0'); m.calls = []
    add(m, new_rows(m, ['a']))
    expect(m.u.mem_read(GSET, 1)[0] == 0 and [c for c in m.calls if c[0] == 'mclSetGaplessMode'] == [('mclSetGaplessMode', 0), ('mclSetGaplessMode', 0)], 'an off Gapless setting stays off')
    for rep in (None, RA, RO):   # Shuffle plus any repeat: the same
        m = shuffled(repeat=rep); m.setword(PRELOAD, 1); m.calls = []
        add(m, new_rows(m, ['a']))
        expect(seq(m) == [('mclSetGaplessMode', 0), ('closegapless',), ('mclSetGaplessMode', 1)] and m.s32(PRELOAD) == -1, f'Shuffle with repeat {rep}: cancelled the same way')
    # the shuffle reorders use the same helper (the existing shuffle tests pin the whole sequence); no insert cancel without a change of the next song
    m = machine(n=6, pos=1); m.setword(PRELOAD, 1)
    SHM.hook(m, SH)
    expect(('mclSetGaplessMode', 0) in m.calls and ('stock_setmode', RO) not in m.calls, 'a shuffle reorder cancels through the same helper (the mode word never becomes Repeat one)')


def refusal_tests(ctx):
    """4. Every refusal leaves the queue, the saved order, the preload, the mode and the flag as they were, and calls nothing that changes the queue."""
    expect = ctx.expect

    def refuse(label, want, prepare=lambda m: None, rows_of=lambda m: new_rows(m, ['a']), m=None):
        m = m or shuffled()
        prepare(m)
        rows = rows_of(m)
        before = snapshot(m); m.calls = []
        r = add(m, rows)
        expect(r == want and snapshot(m) == before, f'{label}: refused with {want} and nothing changed ({r})')
        expect(not [c for c in m.calls if c[0] in ('_deque_push_back', 'start_player', 'mclSetGaplessMode', 'closegapless', 'mclSetPlayPos', 'calloc', 'free')], f'{label}: no queue, player or allocation call')
        return m
    refuse('an empty rows deque', EMPTY, rows_of=lambda m: m.new_deque([]))
    refuse('no rows deque', EMPTY, rows_of=lambda m: 0)
    for t in (2, 3, 0xf0, 0xf1): refuse(f'a stream (play type {t:#x})', STREAM, lambda m, t=t: setattr(m, 'ptype', t))
    refuse('Radio running with a retained local queue (no stock play type)', STREAM, lambda m: setattr(m, 'radio', 1))
    refuse('Radio running, Shuffle off, a retained local queue', STREAM, lambda m: setattr(m, 'radio', 1), m=machine())
    for label, prep in (('an empty queue', lambda m: m.setword(PLAY_Q, m.new_deque([]))), ('no position', lambda m: setattr(m, 'play_pos', -1))):
        refuse(f'Radio running, {label}: the song does not start', STREAM, lambda m, p=prep: (p(m), setattr(m, 'radio', 1)), m=machine(n=6, pos=1))
    refuse('Radio running with an empty rows deque: EMPTY first', EMPTY, lambda m: setattr(m, 'radio', 1), rows_of=lambda m: m.new_deque([]))
    m = machine(n=6, pos=1); m.play_pos = -1; m.radio = 0
    expect(add(m, new_rows(m, ['a'])) == STARTED, 'Radio not running: nothing playing still starts the song')
    m = machine(); m.radio = 0
    expect(add(m, new_rows(m, ['a'])) == ADDED, 'Radio not running: the insert is unchanged')
    refuse('folder playback (play type 1)', FOLDER, lambda m: setattr(m, 'ptype', 1))
    refuse('a podcast episode', PODCAST, rows_of=lambda m: new_rows(m, ['ep'], base='/mnt/mmc/Podcasts/show'))
    refuse('a podcast episode in another case', PODCAST, rows_of=lambda m: new_rows(m, ['ep'], base='/mnt/mmc/PODCASTS/show'))
    refuse('a missing file', MISSING, rows_of=lambda m: (lambda d: (m.present.discard(X('a')[0]), d)[1])(new_rows(m, ['a'])))
    refuse('one bad row among good ones: none is added', MISSING, rows_of=lambda m: (lambda d: (m.present.discard(X('b')[0]), d)[1])(new_rows(m, ['a', 'b', 'c'])))
    refuse('a podcast row last among good ones', PODCAST, rows_of=lambda m: m.new_deque(m.deques[new_rows(m, ['a'])] + m.deques[new_rows(m, ['e'], base='/mnt/mmc/Podcasts/s')]))
    refuse('a row with no path', MISSING, rows_of=lambda m: m.new_deque([m.record(path='', title='none', name='n.flac', rid=1)]))
    # allocation failure: the new order cannot be made (Shuffle on, an order kept): the insert is refused whole, the preload untouched
    for fail in ('all', 'exact'):
        m = shuffled(); m.setword(PRELOAD, 1)
        if fail == 'all': m.calloc_fail = True
        else: m.calloc_fail_size = 4 * 13
        before = snapshot(m); rows = new_rows(m, ['a']); m.calls = []
        r = add(m, rows)
        expect(r == MEMORY and snapshot(m) == before and not names(m, '_deque_push_back') and m.word(PRELOAD) == 1 and not names(m, 'mclSetGaplessMode'), f'no memory for the new order ({fail}): refused with {MEMORY}, queue, order and preload unchanged ({r})')
        c = [x[0] for x in m.calls]
        expect(c.count('lock') == c.count('unlock') == 1, 'the lock is released on the refusal')
    m = machine(); m.calloc_fail = True
    expect(add(m, new_rows(m, ['a'])) == ADDED, 'without a saved order nothing is allocated, so a failing calloc does not matter')
    # SHUFFLE_MAX: size + n over the cap is refused, with the order kept untouched (its n stands for the shuffled queue, which is replaced here by a long one)
    m = shuffled(); one = qpaths(m) and m.deques[m.word(PLAY_Q)][0]
    m.deques[m.word(PLAY_Q)] = [one] * MAX
    before = snapshot(m); m.calls = []
    expect(add(m, new_rows(m, ['a'])) == FULL and snapshot(m) == before and not names(m, '_deque_push_back') and not names(m, 'calloc'), f'{MAX} songs + 1: refused with FULL, queue and saved order unchanged')
    m.deques[m.word(PLAY_Q)] = [one] * (MAX - 1); m.play_pos = 5
    expect(add(m, new_rows(m, ['a', 'b'])) == FULL and len(m.deques[m.word(PLAY_Q)]) == MAX - 1, f'{MAX - 1} songs + 2 refused (the cap is on the sum)')
    m = machine(); m.deques[m.word(PLAY_Q)] = [m.deques[m.word(PLAY_Q)][0]] * (MAX - 1); m.play_pos = 5
    expect(add(m, new_rows(m, ['a']), after=1) == ADDED and len(m.deques[m.word(PLAY_Q)]) == MAX, f'{MAX - 1} songs + 1 reaches the cap exactly and is taken')


def idle_tests(ctx):
    """5. Nothing playing: the rows become the queue and the first one plays, with Shuffle off and on; the flag and the repeat mode are not touched."""
    expect = ctx.expect
    for label, prep in (('the player at no position', lambda m: setattr(m, 'play_pos', -1)), ('no queue object', lambda m: m.setword(PLAY_Q, 0)), ('an empty queue', lambda m: m.setword(PLAY_Q, m.new_deque([])))):
        for flag in (False, True):
            m = machine(n=6, pos=1, mode=RA, flag=flag); prep(m)
            rows = new_rows(m, ['a', 'b', 'c']); m.calls = []
            r = add(m, rows)
            sp = names(m, 'start_player')
            what = f'{label}, Shuffle {"on" if flag else "off"}'
            expect(r == STARTED and sp == [('start_player', 0, 0xf001, O['PLAY_MODE'], 3)], f'{what}: start_player(rows, 0, class, PLAY_MODE) with all rows, STARTED ({r}, {sp})')
            expect(m.word(CLASS) == 0xf001 and (m.word(D['FORCE_REFRESH'][0]) & 0xff) == 1 and qpaths(m) == X('a', 'b', 'c') and m.play_pos == 0, f'{what}: class, refresh flag, the queue and the position')
            expect(m.mode == RA and SHM.flag_on(m) == flag and not [c for c in m.calls if c[0] in ('stock_setmode', 'mclSetPlayMode', 'write_int_config', 'write')], f'{what}: the repeat mode and the Shuffle flag stay as they were')
            expect(len(m.deques[rows]) == 3 and not names(m, 'deque_destroy') and not names(m, 'pthread_mutex_lock'), f'{what}: the caller\'s rows deque is not destroyed')
            if flag:   # the load hook (start_player's mclLoadPlayList) shuffles the rows with the first one first
                h = m.new_deque(list(m.deques[m.word(PLAY_Q)]))
                SHM.load(m, h, 0)
                expect(qpaths(m)[0] == X('a')[0] and sorted(qpaths(m)) == sorted(X('a', 'b', 'c')) and m.play_pos == 0, f'{what}: the load hook shuffles them, the first row first ({qpaths(m)})')
    m = machine(n=6, pos=1); m.play_pos = -1
    rows = new_rows(m, ['a']); m.setword(m.deques[rows][0] + O['REC_CLASS'], 0xff10)
    add(m, rows)
    expect(names(m, 'start_player')[0][2] == 0xff10 and m.word(CLASS) == 0xff10, 'the first row\'s own class is used when it has one')
    m = machine(n=6, pos=1); m.play_pos = -1; m.ptype = 2
    expect(add(m, new_rows(m, ['a'])) == STARTED, 'with nothing playing a stale stream play type does not refuse')
    m = machine(n=6, pos=1); m.play_pos = -1; rows = new_rows(m, ['a']); m.present.discard(X('a')[0])
    expect(add(m, rows) == MISSING and not names(m, 'start_player'), 'a missing file is refused when nothing plays too')


def lock_tests(ctx):
    """6. The payload lock (docs/modules/shuffle.md, Locking): the insert takes it once around the whole operation, calls nothing hooked inside, and excludes a reorder, a load and a clear."""
    expect = ctx.expect
    HOOKED = ('stock_setmode', 'mclSetPlayMode', 'stock_loadplaylist', 'toast', 'write_int_config')

    def balanced(label, m):
        depth, bad, taken = 0, '', 0
        for c in m.calls:
            if c[0] == 'lock': depth += 1; taken += 1; bad = bad or ('taken twice' if depth > 1 else '')
            elif c[0] == 'unlock': depth -= 1; bad = bad or ('released unheld' if depth < 0 else '')
            elif depth and c[0] in HOOKED: bad = bad or f'{c[0]} under the lock'
        expect(not bad and depth == 0 and taken == 1, f'lock path "{label}": taken once, released, nothing hooked inside ({bad or taken})')
    for label, m, after in (('Play Next', machine(), 0), ('Play After', machine(), 1), ('Play Next, Shuffle', shuffled(), 0), ('Play Next, Shuffle, preload open', None, 0)):
        if m is None: m = shuffled(); m.setword(PRELOAD, 1)
        m.calls = []; add(m, new_rows(m, ['a', 'b']), after); balanced(label, m)
    m = shuffled(); m.calloc_fail = True; m.calls = []; add(m, new_rows(m, ['a'])); balanced('no memory', m)
    m = shuffled(); m.deques[m.word(PLAY_Q)] = [m.deques[m.word(PLAY_Q)][0]] * MAX; m.calls = []; add(m, new_rows(m, ['a'])); balanced('full', m)

    def sched(m): m.sched, m.events, m.loads_held, m.clears_held, m.limit, m.calls, m.copies = True, [], [], [], 10 ** 9, [], 0
    def spawn(m, name, sym, sp, a0=0, a1=0, a2=0):
        for r, v in ((SP_, sp), (RA_, RET), (T9_, PSYMS[sym]), (UC_MIPS_REG_A0, a0), (UC_MIPS_REG_A1, a1), (UC_MIPS_REG_A2, a2), (PC_, PSYMS[sym])): m.u.reg_write(r, v & 0xffffffff)
        return {'name': name, 'ctx': m.u.context_save(), 'done': False}
    def go(m, th):
        m.cur, m.blocked = th['name'], None
        m.u.context_restore(th['ctx']); m.u.emu_start(m.u.reg_read(PC_), RET)
        th['ctx'] = m.u.context_save(); th['done'] = m.u.reg_read(PC_) == RET
    # (a) DLNA's Shuffle request holds the lock paused mid-permutation: the insert waits, queue untouched; then it applies to the finished reorder with the order grown.
    m = machine(); sched(m); rows = new_rows(m, ['a']); q0 = m.word(PLAY_Q)
    dl = spawn(m, 'dlna', 'sh_set_mode', STACK, a0=SH); m.yield_thread, m.yield_at = 'dlna', 2
    go(m, dl); mid = qpaths(m)
    expect(not dl['done'] and m.owner == 'dlna' and len(set(mid)) < len(mid), 'interleaving A: the reorder is paused mid-permutation, lock held, records duplicated')
    ui = spawn(m, 'ui', 'upnext_add', STACK - 0x4000, a0=rows, a1=0); go(m, ui)
    expect(m.blocked == 'ui' and not ui['done'] and qpaths(m) == mid and not names(m, '_deque_push_back'), 'interleaving A: the insert waits at the lock; the queue is untouched')
    m.yield_at = 0; go(m, dl); done = qpaths(m)
    expect(dl['done'] and m.owner is None and sorted(done) == sorted(ORIG()) and len(names(m, '_deque_push_back')) == 0, 'interleaving A: the reorder finishes whole and releases the lock, still no insert')
    go(m, ui)
    unl = max(i for i, e in enumerate(m.events) if e == ('dlna', 'pthread_mutex_unlock'))
    expect(max(i for i, e in enumerate(m.events) if e == ('ui', 'pthread_mutex_lock')) > unl, 'interleaving A: the insert got the lock only after the reorder released it')
    expect(ui['done'] and m.owner is None and qpaths(m) == done[:4] + X('a') + done[4:] and is_perm(orig_of(m)[2], 13) and orig_of(m)[1] == 13, f'interleaving A: after the reorder the row goes in after the playing song and the order has 13 entries ({qpaths(m)})')
    m.sched = False; SHM.hook(m, OR)
    expect(qpaths(m) == expected_off(ORIG()[3], [(('a',), 0)]), 'interleaving A: Shuffle off then restores the original order with the row after the playing song')
    # (b) the insert is paused mid-rotation (lock held): a queue load on DLNA's thread waits; stock's loader does not run until the insert released the lock.
    m = machine(); sched(m); rows = new_rows(m, ['a', 'b']); q0 = m.word(PLAY_Q)
    ui = spawn(m, 'ui', 'upnext_add', STACK - 0x4000, a0=rows, a1=0); m.yield_thread, m.yield_at = 'ui', 2
    go(m, ui); mid = qpaths(m)
    expect(not ui['done'] and m.owner == 'ui' and len(mid) == 14 and len(set(mid)) < 14, 'interleaving B: the insert is paused mid-rotation, lock held')
    new = [SHM.song(m, f'/mnt/mmc/n/{i}.flac', 'New', i + 1) for i in range(5)]; h = m.new_deque(new)
    dl = spawn(m, 'dlna', 'sh_load_playlist', STACK, a0=h, a1=2, a2=0xf001); go(m, dl)
    expect(m.blocked == 'dlna' and not dl['done'] and 'stock_loadplaylist' not in m.names() and m.word(PLAY_Q) == q0 and qpaths(m) == mid, 'interleaving B: the load waits at the lock; stock\'s loader has not run and the deque is untouched')
    m.yield_at = 0; go(m, ui)
    expect(ui['done'] and m.owner is None and qpaths(m) == ORIG()[:4] + X('a', 'b') + ORIG()[4:], f'interleaving B: the insert finishes whole ({qpaths(m)})')
    go(m, dl)
    expect(dl['done'] and m.owner is None and m.loads_held == [True] and sorted(qpaths(m)) == sorted(f'/mnt/mmc/n/{i}.flac' for i in range(5)), 'interleaving B: the load then runs under the lock on the finished queue')
    # (c) a clear (dmr_serverstart) against an insert paused mid-rotation: waits, then clears; the order was grown and is dropped by the clear.
    m = shuffled(); sched(m); rows = new_rows(m, ['a', 'b']); q0 = m.word(PLAY_Q)
    ui = spawn(m, 'ui', 'upnext_add', STACK - 0x4000, a0=rows, a1=0); m.yield_thread, m.yield_at = 'ui', 2
    go(m, ui)
    dl = spawn(m, 'dlna', 'sh_clear_queue', STACK, a0=q0); go(m, dl)
    expect(not ui['done'] and m.blocked == 'dlna' and 'deque_clear' not in m.names(), 'interleaving C: the clear waits for the insert')
    m.yield_at = 0; go(m, ui); go(m, dl)
    expect(ui['done'] and dl['done'] and m.owner is None and m.clears_held == [True] and m.deques[q0] == [] and orig_of(m)[0] == 0, 'interleaving C: the insert finishes, then the clear runs under the lock and drops the order')


def pinned_tests(ctx):
    """7. The pinned addresses the insert relies on."""
    ctx.expect(O['SHUFFLE_MAX'] == 65536 and pod.FUNCTIONS['mclSetGaplessMode'][2] == 0x5d28ac and D['MCL_PRELOAD'][0] == 0xa0abd0 and D['MCL_GAPLESS'][0] == 0xa0ab89, 'the pinned addresses')


def clear_tests(ctx):
    """8. The insert and Queue Clear (patch/shuffle.c pod_clear_upnext) together: both under the payload lock, both through the one cancel helper, both drop or keep Shuffle's order
    consistently; the insert is refused while the DLNA renderer service runs, as Clear is."""
    expect = ctx.expect
    DMR = D['DMR_SERVERFLAG'][0]
    clear = lambda m: signed(m.call(PSYMS['pod_clear_upnext'], count=900000000))

    # DLNA: refused under the lock with nothing changed (also the preload and the Gapless setter), taken again when the service stops
    for label, make in (('List play', machine), ('Shuffle', shuffled)):
        m = make(); m.install_libcstl(); m.setword(PRELOAD, 1); m.setword(DMR, 1)
        rows = new_rows(m, ['a']); before = snapshot(m); m.calls = []
        for after in (0, 1):
            r = add(m, rows, after)
            expect(r == DLNA and snapshot(m) == before, f'{label}, DLNA running, after={after}: refused with {DLNA} and nothing changed ({r})')
        expect(not [c for c in m.calls if c[0] in ('_deque_push_back', 'start_player', 'mclSetGaplessMode', 'closegapless', 'mclSetPlayPos', 'calloc', 'free')], f'{label}: no queue, player or allocation call')
        c = [x[0] for x in m.calls]
        expect(c.count('lock') == c.count('unlock') == 1, f'{label}: the lock is released on the refusal')
        m.setword(DMR, 0)
        expect(add(m, rows) == ADDED and len(qpaths(m)) == 13, f'{label}: the service stopped, the insert works')

    # insert, then Clear, then Shuffle off: Clear takes the grown order with it (the flag stays on until the off), the queue keeps the playing song and the history
    m = shuffled(); m.install_libcstl(); m.setword(PRELOAD, 1)
    keep = qpaths(m)[:4]
    expect(add(m, new_rows(m, ['a'])) == ADDED and is_perm(orig_of(m)[2], 13), 'insert: Shuffle on, the saved order grown to 13')
    expect([c for c in m.calls if c[0] == 'mclSetGaplessMode'] == [('mclSetGaplessMode', 0), ('mclSetGaplessMode', 1)] and m.s32(PRELOAD) == -1, 'insert: the one cancel closed the preload')
    m.calls = []
    expect(clear(m) == 1 and qpaths(m) == keep and orig_of(m)[0] == 0 and m.play_pos == 3 and SHM.flag_on(m), 'then Clear: the playing song and the history stay, the order is dropped, the flag stays on')
    expect(not names(m, 'mclSetGaplessMode'), 'Clear finds the preload already closed: the cancel helper does not touch the setter again')
    c = [x[0] for x in m.calls]
    expect(c.count('lock') == c.count('unlock') == 1, 'Clear takes the payload lock once')
    SHM.hook(m, OR)
    expect(qpaths(m) == keep and m.play_pos == 3 and not SHM.flag_on(m), 'Shuffle off after insert + Clear: the queue stays as Clear left it, the playing song plays on')

    # Clear, then insert, then Shuffle off: there is no order to grow; the new row sits after the playing song and stays
    m = shuffled(); m.install_libcstl(); m.setword(PRELOAD, 1)
    keep = qpaths(m)[:4]
    expect(clear(m) == 1 and m.s32(PRELOAD) == -1 and qpaths(m) == keep and orig_of(m)[0] == 0, 'Clear first: the preload closed through the setter, the order dropped')
    m.calls = []
    expect(add(m, new_rows(m, ['a'])) == ADDED and qpaths(m) == keep + X('a') and orig_of(m)[0] == 0 and not names(m, 'calloc') and not names(m, 'mclSetGaplessMode'), 'then Play Next: no order to grow, nothing allocated, no second cancel')
    SHM.hook(m, OR)
    expect(qpaths(m) == keep + X('a') and m.play_pos == 3 and not SHM.flag_on(m), 'Shuffle off: the queue is the playing song, the history and the added song')

    # Play Next, then Clear in List play with a preload open: the playing song plays on (position unchanged, nothing started)
    m = machine(); m.install_libcstl(); m.setword(PRELOAD, 1)
    add(m, new_rows(m, ['a'])); m.calls = []
    expect(clear(m) == 1 and m.play_pos == 3 and len(qpaths(m)) == 4 and not names(m, 'start_player') and not names(m, 'mclSetPlayPos'), 'Play Next then Clear: the position is the playing song and nothing is restarted')


def edit_tests(ctx):
    """9. The edit engine (patch/shuffle.c queue_edit: pod_queue_move, pod_queue_remove; docs/modules/queue.md "Edit engine: move / remove"): an Up Next row moves or is removed in
    place, the saved Shuffle order follows, the gapless preload is cancelled only when the next song changes, every refusal changes nothing, and the lock is taken once."""
    expect = ctx.expect
    DMR, PRE_NEXT = D['DMR_SERVERFLAG'][0], D['MCL_PRELOAD_NEXT'][0]
    OK, RANGE, DL, LIB = 1, -1, -2, -3
    mv = lambda m, f, t: signed(m.call(PSYMS['pod_queue_move'], a0=f, a1=t, count=900000000))
    rm = lambda m, i: signed(m.call(PSYMS['pod_queue_remove'], a0=i, count=900000000))
    recs = lambda m: list(m.deques[m.word(PLAY_Q)])
    strs = lambda m, rs: [m.word(r + O[f]) for r in rs for f in ('REC_TITLE', 'REC_ARTIST', 'REC_ALBUM', 'REC_PATH', 'REC_NAME')]
    raw = lambda m, rs: [bytes(m.u.mem_read(r, O['REC_SIZE'])) for r in rs]
    seq = lambda m: [c for c in m.calls if c[0] in ('mclSetGaplessMode', 'closegapless', 'stock_setmode', 'mclSetPlayMode')]
    CLOSE = [('mclSetGaplessMode', 0), ('closegapless',), ('mclSetGaplessMode', 1)]
    BAD = ('calloc', 'strdup', 'memcpy', 'memset', '_deque_push_back', 'start_player', 'mclSetPlayPos', 'stock_setmode', 'mclSetPlayMode', 'deque_assign', 'deque_destroy', 'deque_clear')
    made = lambda f, **kw: (lambda m: (m.install_libcstl(), m)[1])(f(**kw))
    locked = lambda m: (lambda c: c.count('lock') == c.count('unlock') == 1)([x[0] for x in m.calls])
    movedl = lambda l, f, t: (lambda l: (l.insert(t, l.pop(f)), l)[1])(list(l))

    def consistent(m, removed=()):
        """Shuffle's order describes the queue: slot j holds the song whose original position is orig[j], and orig is a permutation of the surviving songs."""
        p, n, o = orig_of(m)
        keep = [x for x in ORIG() if x not in removed]
        return o is not None and n == len(qpaths(m)) and is_perm(o, n) and all(qpaths(m)[j] == keep[o[j]] for j in range(n))

    # List play: forward, backward, adjacent, far, the first and last Up Next row, a no-op; records and strings stay, nothing allocated or copied
    for f, t in ((6, 9), (9, 6), (4, 5), (5, 4), (4, 11), (11, 4), (7, 7), (4, 4)):
        m = made(machine, n=12, pos=3); rs, ps, head, rw = recs(m), qpaths(m), raw(m, recs(m)[:4]), raw(m, recs(m)); m.calls = []
        r = mv(m, f, t)
        expect(r == OK and qpaths(m) == movedl(ps, f, t) and recs(m) == rs and raw(m, rs) == movedl(rw, f, t), f'List play, move {f} -> {t}: the row is at {t}, the rows between shifted by one, every record in its own slot ({qpaths(m)})')
        expect(raw(m, recs(m)[:4]) == head and recs(m)[:4] == rs[:4] and m.play_pos == 3 and orig_of(m)[0] == 0 and not [c for c in m.calls if c[0] in BAD or c[0] in ('free', 'pop_back')],
               f'move {f} -> {t}: the rows 0..pos untouched, the position kept, no allocation, copy, free, restart or pop')
        expect(locked(m) and m.mode == OR, f'move {f} -> {t}: the payload lock is taken once and released')
    m = made(machine, n=12, pos=3); m.setword(PRE_NEXT, 4); mv(m, 7, 9)
    expect(m.word(PRE_NEXT) == 4 and m.mode == OR, 'a move leaves the remembered preload target and the mode alone')

    # Shuffle on: the saved order is carried with the rows and stays a permutation; Shuffle off restores the original order (a manual order is dropped), the position on the playing song
    for f, t in ((6, 9), (9, 6), (4, 5), (5, 4), (4, 11), (11, 4), (8, 8)):
        m = made(shuffled, n=12, pos=3); playing = qpaths(m)[3]; before = qpaths(m); o0 = orig_of(m)[2]; m.calls = []
        r = mv(m, f, t)
        expect(r == OK and qpaths(m) == movedl(before, f, t) and consistent(m) and orig_of(m)[2] == (movedl(o0, f, t)), f'Shuffle on, move {f} -> {t}: queue and saved order rotated together, still a permutation')
        expect(orig_of(m)[0] and not [c for c in m.calls if c[0] in ('calloc', 'free', '_deque_push_back', 'mclSetPlayPos')] and locked(m), f'move {f} -> {t}: the order is the same array (no allocation), the lock once')
        SHM.hook(m, OR)
        expect(qpaths(m) == ORIG() and qpaths(m)[m.play_pos] == playing and m.play_pos == 3 and not SHM.flag_on(m), f'move {f} -> {t}, then Shuffle off: the original order, the position on the playing song')

    # remove: first / middle / last Up Next row, the record destroyed once (libcstl's pop_back, the last slot), nothing else freed, copied or allocated
    for label, make in (('List play', machine), ('Shuffle on', shuffled)):
        for i in (4, 7, 11):
            m = made(make, n=12, pos=3); rs, ps = recs(m), qpaths(m); gone = rs[-1]; rw = raw(m, rs); gone_s = strs(m, [rs[i]]); keepers = strs(m, rs[:i] + rs[i + 1:]); head = raw(m, rs[:4]); q = m.word(PLAY_Q); m.calls = []
            r = rm(m, i)
            pops = [c for c in m.calls if c[0] == 'pop_back']; freed = [c[1] for c in m.calls if c[0] == 'free' and c[1]]
            expect(r == OK and qpaths(m) == ps[:i] + ps[i + 1:] and recs(m) == rs[:-1] and raw(m, recs(m)) == rw[:i] + rw[i + 1:] and m.word(PLAY_Q) == q and m.play_pos == 3, f'{label}, remove {i}: the row is gone, the rest in order, the same deque, the position kept ({qpaths(m)})')
            expect(len(pops) == 1 and pops[0][2] == gone and sorted(freed) == sorted(gone_s) and not set(freed) & set(keepers) and raw(m, [gone]) == [bytes(O['REC_SIZE'])],
                   f'{label}, remove {i}: one pop_back of the last slot (the row rotated there), its strings freed exactly once, no other string freed')
            expect(recs(m)[:4] == rs[:4] and raw(m, recs(m)[:4]) == head and not [c for c in m.calls if c[0] in BAD or c[0] == 'calloc'] and locked(m), f'{label}, remove {i}: rows 0..pos untouched, no allocation or copy, lock once')
            if make is shuffled:
                expect(consistent(m, removed=(ps[i],)) and orig_of(m)[1] == 11 and orig_of(m)[0], f'remove {i}: the saved order lost the entry and is a permutation of 11, shrunk in place')
                SHM.hook(m, OR)
                expect(qpaths(m) == [x for x in ORIG() if x != ps[i]] and m.play_pos == 3 and qpaths(m)[3] == ps[3], f'remove {i}, then Shuffle off: the original order without that song, the playing song at the position')
    # remove of the song that is first in the original order of the Up Next rows and of the one right after the playing song, with Shuffle on
    m = made(shuffled, n=12, pos=3); lo = min(range(4, 12), key=lambda j: orig_of(m)[2][j]); p0 = qpaths(m)[lo]
    expect(rm(m, lo) == OK and consistent(m, removed=(p0,)), 'Shuffle on: removing the up-next song with the lowest original position keeps the order a permutation')

    # every refusal: nothing changed (queue, order, preload, mode, flag), no queue / player / allocation call, the lock released
    def refuse(label, want, op, prepare=lambda m: None, make=shuffled):
        m = made(make, n=12, pos=3); prepare(m); m.setword(PRELOAD, 1); before = snapshot(m); keep = raw(m, recs(m)); m.calls = []
        r = op(m)
        expect(r == want and snapshot(m) == before and raw(m, recs(m)) == keep, f'{label}: refused with {want}, queue, order, preload, mode and flag unchanged ({r})')
        expect(not [c for c in m.calls if c[0] in BAD or c[0] in ('free', 'pop_back', 'mclSetGaplessMode', 'closegapless')] and locked(m), f'{label}: nothing called that changes the queue, the lock released')
    for make in (machine, shuffled):
        for label, op in (('move from the playing row', lambda m: mv(m, 3, 8)), ('move to the playing row', lambda m: mv(m, 8, 3)), ('move from the history', lambda m: mv(m, 1, 8)), ('move to the history', lambda m: mv(m, 8, 0)),
                          ('move from past the end', lambda m: mv(m, 12, 5)), ('move to past the end', lambda m: mv(m, 5, 12)), ('move from -1', lambda m: mv(m, 0xffffffff, 5)),
                          ('remove the playing row', lambda m: rm(m, 3)), ('remove a history row', lambda m: rm(m, 0)), ('remove past the end', lambda m: rm(m, 12)), ('remove -1', lambda m: rm(m, 0xffffffff)),
                          ('a no-op move on the playing row', lambda m: mv(m, 3, 3))):
            refuse(f'{make.__name__}, {label}', RANGE, op, make=make)
        refuse(f'{make.__name__}, nothing playing', RANGE, lambda m: mv(m, 5, 6), lambda m: setattr(m, 'play_pos', -1), make)
        refuse(f'{make.__name__}, nothing playing (remove)', RANGE, lambda m: rm(m, 5), lambda m: setattr(m, 'play_pos', -1), make)
        refuse(f'{make.__name__}, the last song playing', RANGE, lambda m: mv(m, 5, 6), lambda m: setattr(m, 'play_pos', 11), make)
        refuse(f'{make.__name__}, DLNA running (move)', DL, lambda m: mv(m, 5, 8), lambda m: m.setword(DMR, 1), make)
        refuse(f'{make.__name__}, DLNA running (remove)', DL, lambda m: rm(m, 5), lambda m: m.setword(DMR, 1), make)
        refuse(f'{make.__name__}, DLNA running (no-op move)', DL, lambda m: mv(m, 5, 5), lambda m: m.setword(DMR, 1), make)
        m = made(make, n=12, pos=3); m.setword(DMR, 1); mv(m, 5, 8); m.setword(DMR, 0)
        expect(mv(m, 5, 8) == OK and rm(m, 5) == OK, f'{make.__name__}: the service stopped, the edits work (the lock was released)')
    # libcstl not as pinned: remove refused with nothing changed (and before any rotation); move needs no libcstl
    m = machine(n=12, pos=3); m.install_libcstl(bound=False); m.setword(PRELOAD, 1); before = snapshot(m); m.calls = []
    expect(rm(m, 5) == LIB and snapshot(m) == before and not [c for c in m.calls if c[0] in BAD or c[0] in ('free', 'pop_back', 'mclSetGaplessMode')] and locked(m) and m.call(PSYMS['pod_clear_ready'], count=900000000) == 0,
           f'libcstl unbound: remove refused with {LIB}, nothing rotated, not ready')
    expect(mv(m, 5, 8) == OK and qpaths(m)[8] == ORIG()[5], 'and a move works without libcstl')
    m = made(shuffled, n=12, pos=3); base = m.CSTL_BASE; m.setword(base + pod.CSTL_POP, 0); before = snapshot(m)
    expect(rm(m, 5) == LIB and snapshot(m) == before, 'a changed deque_pop_back word: refused, order untouched')
    m = made(machine, n=12, pos=3)
    expect(m.call(PSYMS['pod_clear_ready'], count=900000000) == 1, 'pod_clear_ready is the one readiness test (pinned libcstl, no DLNA)')

    # the queue, size and position are read under the lock
    m = made(machine, n=12, pos=3); before = qpaths(m)
    def moved(): m.play_pos = 8; m.on_lock = None
    m.on_lock = moved
    expect(mv(m, 6, 9) == RANGE and qpaths(m) == before, 'the position moved to 8 while the lock was waited for: the move is refused (the row 6 is history now)')
    m = made(machine, n=12, pos=3); q = m.word(PLAY_Q); before = qpaths(m)
    def shrank(): m.deques[q] = m.deques[q][:8]; m.on_lock = None
    m.on_lock = shrank
    expect(rm(m, 9) == RANGE and len(m.deques[q]) == 8, 'the queue shrank to 8 while the lock was waited for: index 9 is refused')

    # a stale saved order (its size is not the queue's) is dropped, the edit goes ahead
    m = made(shuffled, n=12, pos=3); m.deques[m.word(PLAY_Q)].append(m.deques[m.word(PLAY_Q)][0]); ps = qpaths(m); m.calls = []
    expect(mv(m, 5, 8) == OK and qpaths(m) == movedl(ps, 5, 8) and orig_of(m)[0] == 0 and orig_of(m)[1] == 0 and SHM.flag_on(m), 'a stale order: dropped (freed), the move done, the flag stays')
    m = made(shuffled, n=12, pos=3); m.deques[m.word(PLAY_Q)].append(m.deques[m.word(PLAY_Q)][0])
    expect(rm(m, 5) == OK and orig_of(m)[0] == 0 and len(qpaths(m)) == 12, 'a stale order with a remove: dropped, the row removed')

    # gapless: the cancel fires exactly when the row at pos + 1 changes
    for label, op, fires in (('move away from pos + 1', lambda m: mv(m, 4, 9), True), ('move to pos + 1', lambda m: mv(m, 9, 4), True), ('move across, pos + 1 unchanged', lambda m: mv(m, 6, 9), False),
                             ('move 5 -> 4 (swap with pos + 1)', lambda m: mv(m, 5, 4), True), ('no-op move at pos + 1', lambda m: mv(m, 4, 4), False), ('remove pos + 1', lambda m: rm(m, 4), True),
                             ('remove another row', lambda m: rm(m, 8), False), ('remove the last row', lambda m: rm(m, 11), False)):
        for make in (machine, shuffled):
            m = made(make, n=12, pos=3); m.setword(PRELOAD, 1); m.calls = []
            r = op(m); c = [x[0] for x in m.calls]
            expect(r == OK and (seq(m) == CLOSE and m.s32(PRELOAD) == -1 and c.index('lock') < c.index('mclSetGaplessMode') < c.index('unlock') if fires else not seq(m) and m.word(PRELOAD) == 1) and m.u.mem_read(GSET, 1)[0] == 1,
                   f'{make.__name__}, {label}: the preload is {"closed through the Gapless setter under the lock" if fires else "left open"}')
    m = made(machine, n=12, pos=3); m.setword(PRELOAD, 0); m.calls = []; mv(m, 4, 9); rm(m, 4)
    expect(not seq(m), 'no preload open: the setter is not touched')
    m = made(machine, n=12, pos=3); m.setword(PRELOAD, 1); m.u.mem_write(GSET, b'\0'); m.calls = []; mv(m, 4, 9)
    expect([c for c in m.calls if c[0] == 'mclSetGaplessMode'] == [('mclSetGaplessMode', 0), ('mclSetGaplessMode', 0)] and m.u.mem_read(GSET, 1)[0] == 0, 'an off Gapless setting stays off')
    # the remembered target past the new end is dropped by a remove (Clear's rule), one that is still in the queue stays
    for nxt, want in ((11, 0xffffffff), (10, 10), (4, 4), (0xffffffff, 0xffffffff)):
        m = made(machine, n=12, pos=3); m.setword(PRE_NEXT, nxt); rm(m, 11 if nxt == 11 else 7)
        expect(m.word(PRE_NEXT) == want, f'remove with the preload target {signed(nxt)}: now {signed(want)}')

    # with insert and Clear
    m = made(shuffled, n=12, pos=3); playing = qpaths(m)[3]
    for fs in (False, True):
        m = made(shuffled if fs else machine, n=12, pos=3); playing = qpaths(m)[3]
        expect(add(m, new_rows(m, ['a', 'b'])) == ADDED and qpaths(m)[4:6] == X('a', 'b'), f'Shuffle {fs}: Play Next of a, b')
        expect(rm(m, 4) == OK and qpaths(m)[4] == X('b')[0] and len(qpaths(m)) == 13 and (not fs or is_perm(orig_of(m)[2], 13)), f'Shuffle {fs}: remove the first added row')
        expect(mv(m, 4, 9) == OK and qpaths(m)[9] == X('b')[0] and (not fs or is_perm(orig_of(m)[2], 13)), f'Shuffle {fs}: move the other one')
        SHM.hook(m, OR)
        want = ORIG(); want.insert(want.index(playing) + 1, X('b')[0])
        expect(qpaths(m) == want if fs else len(qpaths(m)) == 13, f'Shuffle {fs}, insert, remove, move, then Shuffle off: ' + ('the original order with b after the playing song' if fs else 'the queue as edited'))
    m = made(shuffled, n=12, pos=3); keep = qpaths(m)[:4]
    expect(rm(m, 6) == OK and mv(m, 5, 9) == OK, 'remove then move, Shuffle on')
    m.calls = []
    expect(signed(m.call(PSYMS['pod_clear_upnext'], count=900000000)) == 1 and qpaths(m) == keep and orig_of(m)[0] == 0 and m.play_pos == 3 and SHM.flag_on(m), 'then Clear: the playing song and the history stay, the order dropped')
    expect(mv(m, 4, 5) == RANGE and rm(m, 4) == RANGE, 'after Clear nothing follows: the edits are refused')
    SHM.hook(m, OR)
    expect(qpaths(m) == keep and m.play_pos == 3, 'Shuffle off after remove + move + Clear: the queue as Clear left it')


def navidrome_tests(ctx):
    """7. A Navidrome row's queue record (patch/sbsrc.c queue_row, docs/modules/subsonic.md): its REC_PATH is a stream address, so there is no file to find; the row is taken when sba_queue_add
    noted its id (the queue map), refused as missing when the address is not one the map knows, and a local path is still checked."""
    expect = ctx.expect
    url = 'http://nd.example:4533/rest/stream.view?id='

    def note(m, tid):
        t = m.alloc(1200); m.u.mem_write(t, tid.encode() + b'\0')
        return signed(m.call(PSYMS['sba_queue_add'], a0=t, count=900000000))
    for after, label in ((0, 'Play Next'), (1, 'Play After')):
        m = machine()
        rid = note(m, 't9')
        expect(rid <= -2 and note(m, 't9') == rid and note(m, 't8') != rid, f'sba_queue_add: an id <= -2, the same one for the same track, another for another ({rid})')
        row = m.record(album='A', artist='A', path=url + 't9', title='Nine', name='Nine.flac', rid=rid)
        before = qpaths(m)
        r = add(m, m.new_deque([row]), after)
        got = qpaths(m)
        expect(r == ADDED and len(got) == len(before) + 1 and url + 't9' in got and (got[-1] == url + 't9' if after else got[4] == url + 't9')
               and not [c for c in m.calls if c[0] == 'access' and c[1].startswith('http')], f'{label}: a noted stream-address row is inserted ({r}, at {got.index(url + "t9") if url + "t9" in got else None} of {len(got)}), no file test on the address')
    m = machine()
    row = m.record(album='A', artist='A', path=url + 't7', title='Seven', name='Seven.flac', rid=-123456)
    before = snapshot(m)
    expect(add(m, m.new_deque([row])) == MISSING and snapshot(m) == before, 'an address whose id the queue map does not know is refused like a missing file')
    rid = note(m, 't6')
    row = m.record(album='A', artist='A', path='/mnt/mmc/Subsonic/gone.flac', title='Six', name='gone.flac', rid=rid)
    expect(add(m, m.new_deque([row])) == MISSING, 'a local file path is still tested even for a noted id')
    m = machine(n=6, pos=1); m.play_pos = -1
    rid = note(m, 't5')
    row = m.record(album='A', artist='A', path=url + 't5', title='Five', name='Five.flac', rid=rid)
    expect(add(m, m.new_deque([row])) == STARTED and not [c for c in m.calls if c[0] == 'access' and c[1].startswith('http')], 'nothing playing: a stream-address row starts the queue')


SECTIONS = [insert_tests, shuffle_tests, gapless_tests, refusal_tests, idle_tests, lock_tests, clear_tests, edit_tests, pinned_tests, navidrome_tests]   # tools/check.py runs each as its own task
