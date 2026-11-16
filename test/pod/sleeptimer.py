"""The Sleep Timer page (patch/sleeptimer.c, docs/modules/sleeptimer.md): our page of check rows for stock's Sleep Timer. The state is stock's own (the byte sleepflag and the word sleep_time, the seconds left) and
is written the way stock's Power page writes it, which the tests check by running stock's own switch (0x4a9ae0) and Back (0x4a91d0) handlers under the emulator on the same state and comparing the stored values and the
calls; stock's own refresh (0x4a9924) is then run on the state ours left, to see what the Power page would show. The entries (More sheet row, Control Center tile) are tested in playmore.py and pdtiles.py."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_ui

FLAG, TIME = (pod.DATA[n][0] for n in ('SLEEP_FLAG', 'SLEEP_TIME'))
SWITCH, BACK, REFRESH = 0x4a9ae0, 0x4a91d0, 0x4a9924      # stock's systemset/powermanager_page: the Sleep Timer switch, Back (btn_return0), and the page's refresh from the two words
GET_VALUE, SET_VALUE, SET_ENABLE = 0x61e014, 0x61e384, 0x669320   # leaves of those: text_selector_get_value / text_selector_set_value / widget_set_enable
WIN = 0x30000000
LEAVES = {GET_VALUE: 'text_selector_get_value', SET_VALUE: 'text_selector_set_value', SET_ENABLE: 'widget_set_enable'}
SECS = (0, 900, 1800, 2700, 3600, 5400, 7200)
STATES = [(0, 0), (0, 1234), (1, 0), (1, 900), (1, 1800), (1, 2700), (1, 3600), (1, 5400), (1, 7200), (1, 333), (1, 14399)]   # (byte, word): off, on and counting down, on with no time, a time stock's selectors made


class SM(Machine):
    """Stock's handlers and refresh run for real, with the three leaves recorded; the selectors hold hour / minute (what the user spun them to)."""
    def __init__(self, flag=0, secs=0, hour=0, minute=0):
        super().__init__()
        for a, n in LEAVES.items(): self.handlers[a] = n
        self.u.mem_write(FLAG, bytes([flag])); self.setword(TIME, secs)
        self.hour, self.minute = self.widget('tselector_hour'), self.widget('tselector_min')
        self.sel = {self.hour: hour, self.minute: minute}
        for n in ('imgswitch_sleep', 'view_selectors'): self.widget(n)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name not in LEAVES.values(): return super()._hook(u, address, size, _)
        a0, a1 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1))
        ret = 0
        if name == 'text_selector_get_value': ret = self.sel[a0]
        elif name == 'text_selector_set_value': self.calls.append((name, a0, a1)); self.sel[a0] = a1
        else: self.calls.append((name, a0, a1))
        u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def byte(self, a): return self.u.mem_read(a, 1)[0]
    def state(self): return (self.byte(FLAG), self.word(TIME))


def saves(m):
    """What would save or re-arm anything: stock's two handlers and ours make none of these calls."""
    return [c for c in m.calls if c[0] in ('write_int_config', 'reset_poweroptions_timer', 'system', 'popen', 'fopen')]


def stock_choose(m, v):
    """What a user does on stock's page to get row v: Off is the switch while it is on; a time is the switch while it is off, the selectors spun to hours and minutes, then Back."""
    calls = []

    def run(h):
        m.call(h, a0=WIN, count=3000000); calls.extend(m.calls)
    if v == 0:
        if m.byte(FLAG): run(SWITCH)
    else:
        if not m.byte(FLAG): run(SWITCH)
        m.sel[m.hour], m.sel[m.minute] = SECS[v] // 3600, SECS[v] % 3600 // 60
        run(BACK)
    m.calls = calls
    return m


def state_tests(ctx):
    """st_choice / st_set against stock's switch and Back, run for real on the same state."""
    expect = ctx.expect
    expect(pod.DATA['SLEEP_FLAG'] == (0xa05a94, 'sleepflag') and pod.DATA['SLEEP_TIME'] == (0xa05a90, 'sleep_time'), 'the byte and the word are stock\'s (checked against demo\'s dynsym by the build)')
    pins = {a: w for a, w, _ in pod.SLEEPTIMER_PINS}
    expect(all(a in pins for a in (0x4a9b0c, 0x4a9b14, 0x4a9b18, 0x4a9260, 0x4a926c, 0x4a9274, 0x4a9284, 0x4a8f84, 0x4a8ffc, 0x4a99f4, 0x4a9a34, 0x4ce794, 0x4ce7a0, 0x4ce7a8, 0x4ce7b4, 0x4ce7b8)),
           'the switch\'s store and word, Back\'s arithmetic and store, the selectors\' ranges, the refresh and the countdown are pinned')
    m0 = Machine()
    expect(all(m0.word(a) == w for a, w, _ in pod.SLEEPTIMER_PINS), 'every pinned word is the stock demo\'s')
    # (the page's selectors hold hours 0 .. 3 and minutes 0 .. 59, so every time of ours is one stock's page can show)
    expect(all(s // 3600 <= 3 and s % 3600 // 60 <= 59 for s in SECS) and pod_pages.SLEEP_SECONDS == SECS, 'the six times are within stock\'s selectors (hours 0 .. 3, minutes 0 .. 59)')
    # the check: Off while the byte is 0, a time only when the word is exactly that time, else no row
    for flag, secs, want in ((0, 0, 0), (0, 1800, 0), (0, 99999, 0), (1, 900, 1), (1, 1800, 2), (1, 2700, 3), (1, 3600, 4), (1, 5400, 5), (1, 7200, 6), (1, 0, 0xffffffff), (1, 899, 0xffffffff), (1, 1, 0xffffffff),
                             (1, 14399, 0xffffffff), (2, 900, 1), (0xff, 7200, 6), (1, -1 & 0xffffffff, 0xffffffff)):
        expect(SM(flag=flag, secs=secs).call(PSYMS['st_choice'], count=200000) == want, f'byte {flag}, word {secs}: row {want if want != 0xffffffff else "none"} checked')
    # a picked row stays checked while its timer counts down; another timer, the end or Off forgets it
    C, S = PSYMS['st_choice'], PSYMS['st_set']
    NONE = 0xffffffff
    m = SM(flag=0, secs=0); m.call(S, a0=2, count=200000)
    seq = []
    for w in (1800, 1799, 1200, 59):
        m.setword(TIME, w); seq.append(m.call(C, count=200000))
    expect(seq == [2, 2, 2, 2], f'30 minutes picked, the word counting down: row 2 stays checked ({seq})')
    m.setword(TIME, 2000)
    expect(m.call(C, count=200000) == NONE, 'the word raised above the last seen one: another timer, no row')
    m.setword(TIME, 59)
    expect(m.call(C, count=200000) == NONE, 'the pick stays forgotten after that')
    m.setword(TIME, 900)
    expect(m.call(C, count=200000) == 1, 'without a pick an exact preset still checks its row')
    m = SM(); m.call(S, a0=3, count=200000); m.setword(TIME, 0)
    expect(m.call(C, count=200000) == NONE, 'the word at 0 with the byte on: no row, pick forgotten')
    m.setword(TIME, 2700)
    expect(m.call(C, count=200000) == 3, 'an exact preset checks its row again')
    m = SM(); m.call(S, a0=2, count=200000); m.u.mem_write(FLAG, bytes([0]))
    expect(m.call(C, count=200000) == 0, 'the byte off: Off checked')
    m.u.mem_write(FLAG, bytes([1])); m.setword(TIME, 1000)
    expect(m.call(C, count=200000) == NONE, 'a time set elsewhere after Off, not a preset: no row')
    m = SM(); m.call(S, a0=2, count=200000); m.call(S, a0=0, count=200000)
    expect(m.call(C, count=200000) == 0, 'Off picked: Off checked')
    m.u.mem_write(FLAG, bytes([1])); m.setword(TIME, 1000)
    expect(m.call(C, count=200000) == NONE, 'Off forgets the pick')
    m = SM(); m.call(S, a0=2, count=200000); m.call(S, a0=5, count=200000); m.setword(TIME, 5000)
    expect(m.call(C, count=200000) == 5, 'a second pick replaces the first')
    # every row from every state: the final state is stock's, and nothing is saved or re-armed (stock's handlers do neither)
    for flag, secs in STATES:
        for v in range(7):
            ms = stock_choose(SM(flag=flag, secs=secs), v)
            mo = SM(flag=flag, secs=secs); r = mo.call(PSYMS['st_set'], a0=v, count=200000)
            expect(r == 0 and mo.state() == ms.state() and saves(mo) == saves(ms) == [], f'({flag}, {secs}) -> row {v}: state {mo.state()} / stock {ms.state()}, answers {r}, saves {saves(mo)} / {saves(ms)}')
            # what stock's own page then shows: the refresh runs on the words ours left
            mo.calls = []; mo.call(REFRESH, a0=WIN, count=3000000)
            img = [c[2] for c in mo.calls if c[0] == 'image_base_set_image']
            shown = {c[1]: c[2] for c in mo.calls if c[0] == 'text_selector_set_value'}
            on = mo.byte(FLAG) != 0
            expect(img == [('sset_on' if on else 'sset_off')] and (not on or (shown.get(mo.hour), shown.get(mo.minute)) == (mo.word(TIME) // 3600, mo.word(TIME) % 3600 // 60)),
                   f'({flag}, {secs}) -> row {v}: stock\'s Power page shows the switch {"on" if on else "off"} and {mo.word(TIME) // 3600}:{mo.word(TIME) % 3600 // 60:02d} ({img}, {shown})')
    # the words spelled out
    for (flag, secs, v), want in {(0, 0, 3): (1, 2700), (1, 1800, 0): (0, 0), (1, 1800, 6): (1, 7200), (0, 1234, 0): (0, 1234), (1, 333, 1): (1, 900), (1, 900, 1): (1, 900), (0, 0, 5): (1, 5400)}.items():
        m = SM(flag=flag, secs=secs); m.call(PSYMS['st_set'], a0=v, count=200000)
        expect(m.state() == want, f'({flag}, {secs}) -> row {v}: {m.state()}, wanted {want}')
    for bad in (-1, 7, 100):
        m = SM(flag=1, secs=1800)
        expect(m.call(PSYMS['st_set'], a0=bad & 0xffffffff, count=200000) == 0xffffffff and m.state() == (1, 1800) and not saves(m), f'row {bad}: refused, nothing written')
    # nothing in the payload keeps a Sleep Timer of its own
    expect('m1_open_sleep' not in PSYMS and 'm1_open_stock' in PSYMS, 'no payload code opens stock\'s Power page for the Sleep Timer any more')


def page_tests(ctx):
    """The page: its rows, its checks as the state changes, the taps, the refresh on return to the front, no stock page, the texts and the asset."""
    expect, P = ctx.expect, pod_pages
    SP = P.SLEEP_PAGE
    expect(P.PAGES[P.SLEEPTIMER_PAGE_INDEX] is SP and (SP.key, SP.title, SP.kind) == ('m1plus_sleeptimer', 'Sleep Timer', 'cards'), 'the page: m1plus_sleeptimer, titled Sleep Timer')
    ch = SP.rows[:7]
    expect([(r.label, r.action, r.arg) for r in ch] == [(t, P.ACT_SLEEPSET, i) for i, t in enumerate(('Off', '15 minutes', '30 minutes', '45 minutes', '1 hour', '1.5 hours', '2 hours'))] and P.SLEEP_VALUES == tuple(r.label for r in ch)
           and all(P.row_kind(r) == 'check' for r in ch), 'one card of seven check rows: Off and the six times, the argument the row')
    notes = [x for x in SP.layout if isinstance(x, P.Note)]
    expect(len(notes) == 1 and notes[0].text == P.SLEEP_NOTE and SP.layout[-2] is notes[0] and len(SP.layout) == 9, 'a grey note under the card')
    tl = SP.rows[7]
    expect(len(SP.rows) == 8 and SP.layout[-1] is tl and (tl.label, tl.action) == ('Time Left', P.ACT_SLEEPLEFT) and P.ACT_SLEEPLEFT == 171 and P.row_kind(tl) == 'info', 'a card of its own under the note: one information row, Time Left (ACT 146)')
    expect(P.ACT_SLEEPSET == 170 and P.ACT_SLEEPSET in P.CHECK_ACTIONS and 'm1plus_sleeptimer' in P.PAGE_ORDER, 'the action id and the page registered')
    expect(not any(r.action == P.ACT_STOCK for r in SP.rows) and not any(n.split('/')[-1] == 'powermanager_page' for n, *_ in P.STOCK_PAGES), 'no row opens a stock page')
    expect(not any(getattr(r, 'arg', None) == P.SLEEPTIMER_PAGE_INDEX and r.action == P.ACT_PAGE for p in P.PAGES for r in p.rows), 'no Settings row opens it: the More sheet and the Control Center tile do')
    import pod_i18n
    expect(pod_i18n.key_for('Sleep Timer') == 'powerm_sleep' and pod_i18n.key_for('Off') == 'Off', 'the title is the stock key powerm_sleep (the translation the Power page and the More sheet row use), Off is the existing key')
    for loc in pod_i18n.LOCALES:
        expect(all(pod_i18n.TEXT[k][loc] for k in ('15 minutes', '30 minutes', '45 minutes', '1 hour', '1.5 hours', '2 hours', P.SLEEP_NOTE, 'Off')), f'the page texts have a translation in {loc}')

    def page(**state):
        m = SM(**state)
        m.widgets.update({n: 0x30000000 + 0x100 * i for i, n in enumerate(['btn_return', 'btn_backtoplayer'] + [f'{k}{i}' for k in ('pod_row', 'pod_check', 'pod_label', 'pod_value') for i in range(8)])})
        row = m.alloc(12)
        m.setword(row, m.cstr('pod_row0')); m.setword(row + 4, P.ACT_PAGE); m.setword(row + 8, P.SLEEPTIMER_PAGE_INDEX)
        m.call(PSYMS['on_row'], a0=row, count=6000000)
        return m

    def checks(m):
        out = []
        for i in range(7):
            v = [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] == m.widgets[f'pod_check{i}']]
            out.append(v[-1] if v else None)
        return out
    for flag, secs, want in ((0, 0, 0), (0, 5400, 0), (1, 900, 1), (1, 7200, 6), (1, 5400, 5), (1, 1000, None), (1, 0, None)):
        m = page(flag=flag, secs=secs)
        expect(('window_open', SP.key) in m.calls and checks(m) == [int(i == want) for i in range(7)] and not saves(m), f'byte {flag}, word {secs}: the check {checks(m)}, nothing written')
    # a tap writes stock's words and moves the check
    m = page(flag=0, secs=0)
    m.click('pod_row3')
    expect(m.state() == (1, 2700) and checks(m) == [0, 0, 0, 1, 0, 0, 0] and not saves(m), f'a tap on 45 minutes from Off: the byte on, the word 2700, the check follows ({m.state()}, {checks(m)})')
    m.calls = []; m.click('pod_row6')
    expect(m.state() == (1, 7200) and checks(m) == [0, 0, 0, 0, 0, 0, 1], 'another time while it runs: the word alone')
    m.calls = []; m.click('pod_row0')
    expect(m.state() == (0, 0) and checks(m) == [1, 0, 0, 0, 0, 0, 0] and not saves(m), 'Off: the byte and the word cleared, the check on Off')
    m.calls = []; m.click('pod_row0')
    expect(m.state() == (0, 0) and checks(m) == [1, 0, 0, 0, 0, 0, 0], 'Off while off: nothing changes')
    # back in front: the state is read again (stock's Power page, a countdown tick, the poweroff clear)
    m = page(flag=0, secs=0)
    m.u.mem_write(FLAG, b'\1'); m.setword(TIME, 1800); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(checks(m) == [0, 0, 1, 0, 0, 0, 0] and not saves(m), f'back in front: the check follows the words stock\'s page set ({checks(m)})')
    m.setword(TIME, 1799); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(checks(m) == [0] * 7, 'one tick later no time is exactly a row: no check')
    m.u.mem_write(FLAG, b'\0'); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(checks(m) == [1, 0, 0, 0, 0, 0, 0], 'the byte cleared (Off in stock\'s page, or the countdown ending): Off is checked')
    # Time Left: its own card, shown (and always insensitive) only while a timer runs; the value is H:MM rounded up to the minute
    def left(m):
        """(visible, sensitive, value text) as the page last set them for the Time Left row."""
        row, val = m.widgets['pod_row7'], m.widgets['pod_value7']
        vis = [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] == row]
        sen = [c[2] for c in m.calls if c[0] == 'widget_set_sensitive' and c[1] == row]
        txt = [c[2] for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == val]
        return (vis[-1] if vis else None, sen[-1] if sen else None, txt[-1] if txt else None)
    for secs, want in ((59, '0:01'), (60, '0:01'), (61, '0:02'), (1, '0:01'), (900, '0:15'), (1380, '0:23'), (3600, '1:00'), (3601, '1:01'), (5400, '1:30'), (7200, '2:00'), (14340, '3:59'), (14399, '4:00')):
        m = page(flag=1, secs=secs)
        expect(left(m) == (1, 0, want) and not saves(m), f'word {secs}: Time Left shows {want} ({left(m)})')
    for flag, secs in ((0, 0), (0, 1800), (1, 0)):
        m = page(flag=flag, secs=secs)
        v = left(m)
        expect(v[0] == 0 and v[1] == 0 and v[2] is None, f'byte {flag}, word {secs}: the Time Left card is hidden and insensitive, no value written ({v})')
    m = page(flag=0, secs=0)
    m.calls = []; m.click('pod_row3')
    expect(left(m) == (1, 0, '0:45'), f'a choice from Off shows the card at once ({left(m)})')
    m.calls = []; m.click('pod_row5')
    expect(left(m) == (1, 0, '1:30'), f'another time: the value follows ({left(m)})')
    m.calls = []; m.click('pod_row0')
    expect(left(m)[:2] == (0, 0), 'Off: the card is hidden again')
    m = page(flag=1, secs=1380)
    m.setword(TIME, 700); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(left(m) == (1, 0, '0:12'), f'back in front: the value is read again ({left(m)})')
    m.u.mem_write(FLAG, b'\0'); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(left(m)[:2] == (0, 0), 'the countdown ended or Off on stock\'s page: the card is hidden when the page is back in front')
    # the page's own refresh timer: one of 4 s added when the window opens, followed while in front, stopped in the background and with the window
    m = page(flag=1, secs=1380)
    tick = [t for t in m.timers if t[1] == 4000]
    expect(len(tick) == 1 and ('timer_add', tick[0][0], 4000) in m.calls, f'one 4 s timer added with the window ({m.timers})')
    m.setword(TIME, 1319); m.calls = []; again = m.call(tick[0][0], a0=0, count=3000000)
    expect(left(m) == (1, 0, '0:22') and checks(m) == [0] * 7 and again != 0, f'a tick reads the words again ({left(m)}) and asks to repeat ({again})')
    m.calls = []; m.fire(O['EVT_WINDOW_TO_BG'])
    expect(m.names().count('timer_remove') == 1 and 'timer_add' not in m.names(), 'in the background the timer is removed')
    m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    added = m.names().count('timer_add')
    m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(added == 1 and 'timer_add' not in m.names(), f'back in front it is added once, a second event adds none ({added}, {m.names().count("timer_add")})')
    m.calls = []; m.fire(O['EVT_DESTROY'])
    expect(m.names().count('timer_remove') == 1 and 'timer_add' not in m.names(), 'with the window it is removed')
    # the asset
    raw =os.path.join(WORK, 'rootfs/release/assets/default/raw/ui')
    t = awtk_ui.parse(open(os.path.join(raw, 'm1plus_sleeptimer.bin'), 'rb').read())
    expect(t.find('label_title').get('tr_text') == 'powerm_sleep' and [t.find(f'pod_label{i}').get('tr_text') for i in range(7)] == ['Off', '15 minutes', '30 minutes', '45 minutes', '1 hour', '1.5 hours', '2 hours'],
           'the asset: the title is the stock key, the row labels are our keys')
    expect(all(t.find(f'pod_check{i}').get('visible') == 'false' and t.find(f'pod_check{i}').get('sensitive') == 'false' for i in range(7)), 'a hidden insensitive check per row')


SECTIONS = [state_tests, page_tests]
