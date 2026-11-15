"""Settings > General > Date & Time (patch/datetime.c, docs/modules/datetime.md): our page for stock's Set Automatically, Time Zone, manual date and time and 24-Hour Time. Every state is stock's own and is written the way
stock's own handlers write it, which the tests check by running stock's click handlers under the emulator on the same state and comparing the stored words, the saves and the calls, in order, with ours."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_ui
import timezones as tzmod

AUTO, NEED, H24, TZ = (pod.DATA[n][0] for n in ('AUTO_TIME', 'SYNC_NEED', 'TIME_24H', 'TIME_ZONE'))
ZONE_CLICK, H24_CLICK, CONFIRM = 0x4a25b8, 0x4aeb50, 0x4a576c   # stock's autosynctime_page click handler (the row item in a0; its name is the row number), the typedatetime_page 24-hour switch, datetime_page's confirm
WIN = 0x30000000
SEL = {'tselector_hour': 0x31000010, 'tselector_min': 0x31000020, 'tselector_year': 0x31000030, 'tselector_month': 0x31000040, 'tselector_day': 0x31000050}
LEAVES = {0x742da0: 'memset', 0x70f8d8: 'tk_snprintf', 0x7435b0: 'atoi'}   # (the PLT stubs stock's code calls through)
SAVES = ('write_int_config', 'select_timezone', 'change_time24h_12h', 'set_systime')


class DM(Machine):
    """Stock's handlers run for real, with the leaves above and the clock mocked. Every save and call records the state words as they are at that moment: the order of the stores and the saves."""
    def __init__(self, auto=1, need=0, tz=22, h24=1, clock=(2026, 11, 15, 14, 5)):
        super().__init__()
        for a, n in LEAVES.items(): self.handlers[a] = n
        self.handlers[0x61e014] = 'text_selector_get_value'   # (stock's text selector: the confirm handler reads its five)
        self.snap = []
        self.clock = clock   # year, month, day, hour, minute
        self.sel = {}
        self.u.mem_write(AUTO, bytes([auto])); self.u.mem_write(NEED, bytes([need])); self.u.mem_write(H24, bytes([h24])); self.setword(TZ, tz)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name in SAVES: self.snap.append(self.state())
        if name == 'select_timezone':
            self.calls.append(('select_timezone', self.word(TZ))); ret = 0
        elif name == 'change_time24h_12h':
            self.calls.append(('change_time24h_12h', u.reg_read(UC_MIPS_REG_A0))); ret = 0
        elif name == 'get_systime':
            sp = u.reg_read(UC_MIPS_REG_SP); y, mo, d, h, mi = self.clock
            for reg, v in ((UC_MIPS_REG_A0, mi), (UC_MIPS_REG_A1, h), (UC_MIPS_REG_A2, d), (UC_MIPS_REG_A3, mo)): self.setword(u.reg_read(reg), v)
            self.setword(self.word(sp + 16), y); self.calls.append(('get_systime',)); ret = 0
        elif name == 'set_systime':   # (year, month, day, hour, minute): stock's date -s and hwclock -wu
            sp = u.reg_read(UC_MIPS_REG_SP)
            self.calls.append(('set_systime',) + tuple(u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3)) + (self.word(sp + 16),)); ret = 0
        elif name == 'text_selector_get_value':
            ret = self.sel[u.reg_read(UC_MIPS_REG_A0)]
        elif name == 'tk_snprintf':
            a0, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
            text = self.read_cstr(a2) % a3
            u.mem_write(a0, text.encode() + b'\0'); ret = len(text)
        else:
            return super()._hook(u, address, size, _)
        u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def byte(self, a): return self.u.mem_read(a, 1)[0]
    def state(self): return (self.byte(AUTO), self.byte(NEED), self.byte(H24), self.word(TZ))


def calls_of(m):
    """What reaches stock's state, in order."""
    return [c for c in m.calls if c[0] in SAVES]


def same(expect, mo, ms, what):
    """Ours against stock's: the final state, the saves and calls in order, and the state at each of them."""
    expect(mo.state() == ms.state() and calls_of(mo) == calls_of(ms) and mo.snap == ms.snap, f'{what}: state {mo.state()} / {ms.state()}, calls {calls_of(mo)} / {calls_of(ms)}, at each call {mo.snap} / {ms.snap}')


def run_row(m, number):
    """Stock's autosynctime_page click handler on the row item named `number`."""
    node = m.alloc(0x40); m.setword(node + 0x10, m.cstr(str(number)))
    m.call(ZONE_CLICK, a0=node, count=3000000)
    return m


def auto_tests(ctx):
    """dt_auto / dt_auto_toggle against stock's switch row (row 0 of the autosynctime page), run for real on the same state."""
    expect = ctx.expect
    expect(pod.DATA['AUTO_TIME'] == (0xa05ab1, 'auto_sync_nettime') and pod.DATA['SYNC_NEED'] == (0xa05a66, 'sync_nettime_flag') and pod.DATA['TIME_24H'] == (0xa05ab0, 'time24hflag'),
           'the bytes are stock\'s (checked against demo\'s dynsym by the build)')
    pins = {a: w for a, w, _ in pod.DATETIME_PINS}
    expect(all(a in pins for a in (0x4a2610, 0x4a2618, 0x4a2620, 0x4a2628, 0x4a262c, 0x4a2640, 0x4a2644, 0x4a2688, 0x4a2690, 0x4a2468, 0x4a2474, 0x4aec74, 0x4aec7c)),
           'the switch\'s stores and save, the page builder\'s row count and the Manual row\'s gate are pinned')
    for auto in (0, 1):
        for need in (0, 1):
            ms = run_row(DM(auto=auto, need=need), 0)
            mo = DM(auto=auto, need=need); r = mo.call(PSYMS['dt_auto_toggle'], count=200000)
            expect(r == 1 - auto and mo.byte(AUTO) == 1 - auto and mo.byte(NEED) == 1 - auto, f'Set Automatically from ({auto}, {need}): the new state, the sync wanted exactly when on')
            same(expect, mo, ms, f'Set Automatically from ({auto}, {need})')
            expect(calls_of(mo) == [('write_int_config', 1 - auto, 'SYSSET', 'AUTOSYNCTIME')] and not [c for c in mo.calls if c[0] in ('system', 'popen', 'toolsGetNetworkTime')],
                   f'from ({auto}, {need}): one save, and no network call, no system() (networktime_adjust_thd syncs, on its thread)')
    for v, want in ((0, 0), (1, 1), (2, 1)):
        expect(DM(auto=v).call(PSYMS['dt_auto'], count=20000) == want, f'the byte {v}: the switch shows {want} (non-zero, as stock tests it)')


def h24_tests(ctx):
    """dt_24h / dt_24h_toggle against stock's switch on the typedatetime page."""
    expect = ctx.expect
    for h in (0, 1):
        ms = DM(h24=h); ms.widget('img_switch'); ms.call(H24_CLICK, a0=WIN, count=3000000)
        mo = DM(h24=h); r = mo.call(PSYMS['dt_24h_toggle'], count=200000)
        expect(r == 1 - h and mo.byte(H24) == 1 - h, f'24-Hour Time from {h}: the new state')
        same(expect, mo, ms, f'24-Hour Time from {h}')
        expect(calls_of(mo) == [('change_time24h_12h', 1 - h), ('write_int_config', 1 - h, 'SYSSET', 'TIME24H')] and mo.snap[0][2] == 1 - h, f'from {h}: the byte first, the clock format, then the save')
    for v, want in ((0, 0), (1, 1), (7, 1)):
        expect(DM(h24=v).call(PSYMS['dt_24h'], count=20000) == want, f'the byte {v}: the switch shows {want}')


def zone_tests(ctx):
    """dt_zone / dt_zone_set against stock's zone rows (row n is the zone n - 2), for every zone of our table."""
    expect = ctx.expect
    expect(pod.DATA['TIME_ZONE'] == (0xa05ab4, 'time_zone') and tzmod.COUNT == 43, 'the word is stock\'s; our table has 43 zones')
    pins = {a: w for a, w, _ in pod.DATETIME_PINS}
    expect(all(a in pins for a in (0x4a269c, 0x4a26a4, 0x4a2790, 0x4a2794, 0x4a2798, 0x4a279c)), 'the zone click\'s index, the same-zone test, the store, the save are pinned (select_timezone\'s call is a TIMEZONE_PINS word)')
    for cur in (22, 0, 29, 42):
        for new in range(tzmod.COUNT):
            ms = run_row(DM(tz=cur), new + 2)
            mo = DM(tz=cur); r = mo.call(PSYMS['dt_zone_set'], a0=new, count=200000)
            expect(r == 0, f'zone {cur} -> {new}: answers 0')
            same(expect, mo, ms, f'zone {cur} -> {new}')
    m = DM(tz=22); m.call(PSYMS['dt_zone_set'], a0=5, count=200000)
    expect(m.calls == [('write_int_config', 5, 'SYSSET', 'TIMEZONE'), ('select_timezone', 5)], f'a zone: the word, the save, then select_timezone: {m.calls}')
    m = DM(tz=22); m.call(PSYMS['dt_zone_set'], a0=22, count=200000)
    expect(m.calls == [], 'the zone that is chosen already does nothing, as stock')
    for bad in (-1, 43, 99):
        m = DM(tz=22)
        expect(m.call(PSYMS['dt_zone_set'], a0=bad & 0xffffffff, count=200000) == 0xffffffff and m.word(TZ) == 22 and not m.calls, f'zone {bad}: refused, nothing written')
    for v, want in ((0, 0), (22, 22), (42, 42), (43, 22), (0xffffffff, 22)):
        expect(DM(tz=v).call(PSYMS['dt_zone'], count=20000) == want, f'the word {v}: the row shows zone {want} (the default for a word we do not know)')


def text(m, which):
    buf = m.alloc(64); m.call(PSYMS['dt_text'], a0=which, a1=buf, a2=64, count=200000)
    return m.read_cstr(buf)


def clock_tests(ctx):
    """The Date and Time values, the date being typed and Set Date / Set Time against stock's confirm handler."""
    expect = ctx.expect
    expect(text(DM(clock=(2026, 11, 5, 14, 5)), 0) == '2026-11-05', 'the date: ISO, two digits')
    for h24, clock, want in ((1, (2026, 1, 1, 14, 5), '14:05'), (1, (2026, 1, 1, 0, 7), '00:07'), (0, (2026, 1, 1, 14, 5), '2:05 PM'), (0, (2026, 1, 1, 0, 7), '12:07 AM'), (0, (2026, 1, 1, 12, 30), '12:30 PM'),
                             (0, (2026, 1, 1, 9, 0), '9:00 AM')):
        expect(text(DM(h24=h24, clock=clock), 1) == want, f'24h {h24}, {clock[3]}:{clock[4]}: the time reads {want}')

    def edit(clock):
        m = DM(auto=0, clock=clock); m.call(PSYMS['dt_edit_start'], count=200000)
        out = []
        for f in range(5):
            buf = m.alloc(32); m.call(PSYMS['dt_field_text'], a0=f, a1=buf, a2=32, count=200000); out.append(m.read_cstr(buf))
        return m, out
    expect(edit((2026, 11, 15, 14, 5))[1] == ['2026', '11', '15', '14', '05'], 'the pickers start from the clock')
    expect(edit((1970, 0, 40, 3, 9))[1] == ['2022', '1', '1', '03', '09'], 'a clock stock\'s selectors cannot show (year before 2022, month 0, day 40): 2022, 1, 1, as stock\'s init clamps')
    expect(edit((2051, 2, 31, 3, 9))[1] == ['2022', '2', '28', '03', '09'], 'year above 2050 is 2022; a day the month does not have becomes its last')
    m, _ = edit((2026, 11, 15, 14, 5))

    def chosen(f, v): return m.call(PSYMS['dt_chosen'], a0=f * 4096 + v, count=20000)
    expect(chosen(0, 2026) == 1 and chosen(0, 2027) == 0 and chosen(1, 11) == 1 and chosen(2, 15) == 1 and chosen(3, 14) == 1 and chosen(4, 5) == 1 and chosen(4, 6) == 0 and chosen(7, 0) == 0, 'the chosen row follows the date being typed')

    def setv(f, v): return m.call(PSYMS['dt_set'], a0=f * 4096 + v, count=200000) & 0xffffffff
    expect(setv(2, 31) == 0 and chosen(2, 30) == 1 and chosen(2, 31) == 0, 'November: the 31st becomes the 30th (stock\'s day selector holds 30 days then)')
    expect(setv(1, 2) == 0 and chosen(2, 28) == 1, 'February 2026: day 30 becomes 28')
    expect(setv(0, 2028) == 0 and setv(2, 29) == 0 and chosen(2, 29) == 1, '2028 is a leap year: the 29th stays')
    expect(setv(0, 2026) == 0 and chosen(2, 28) == 1, '2026 is not: 28')
    expect(setv(0, 2024) == 0 and setv(1, 2) == 0 and setv(2, 29) == 0 and chosen(2, 29) == 1, '2024 February 29')
    expect(setv(1, 4) == 0 and chosen(2, 29) == 1, 'April has 30 days: the 29th stays')
    for f, v in ((0, 2021), (0, 2051), (1, 0), (1, 13), (2, 0), (2, 32), (3, 24), (4, 60), (5, 1), (7, 3)):
        before = [m.call(PSYMS['dt_chosen'], a0=ff * 4096 + vv, count=20000) for ff, vv in ((0, 2024), (1, 4), (2, 29), (3, 14), (4, 5))]
        expect(setv(f, v) == 0xffffffff and before == [m.call(PSYMS['dt_chosen'], a0=ff * 4096 + vv, count=20000) for ff, vv in ((0, 2024), (1, 4), (2, 29), (3, 14), (4, 5))], f'field {f} value {v}: refused, nothing changes')
    # Set Date: the same set_systime(year, month, day, hour, minute) stock's confirm makes, with the clock's own time of day; Set Time likewise with the clock's date
    for date, tm in (((2027, 3, 9), (23, 59)), ((2022, 12, 31), (0, 0)), ((2050, 2, 28), (12, 30))):
        ms = DM(auto=0, clock=(2026, 11, 15, tm[0], tm[1])); ms.widgets = dict(SEL)
        ms.sel = {SEL['tselector_year']: date[0], SEL['tselector_month']: date[1], SEL['tselector_day']: date[2], SEL['tselector_hour']: tm[0], SEL['tselector_min']: tm[1]}
        ms.call(CONFIRM, a0=WIN, count=3000000)
        mo = DM(auto=0, clock=(2026, 11, 15, tm[0], tm[1])); mo.call(PSYMS['dt_edit_start'], count=200000)
        for f, v in ((0, date[0]), (1, date[1]), (2, date[2])): mo.call(PSYMS['dt_set'], a0=f * 4096 + v, count=200000)
        r = mo.call(PSYMS['dt_apply'], a0=0, count=2000000)
        rtc = lambda m: [c for c in m.calls if c[0] == 'set_systime']
        expect(r == 0 and rtc(mo) == rtc(ms) == [('set_systime', date[0], date[1], date[2], tm[0], tm[1])], f'Set Date {date}: set_systime(0, minute, hour, day, month, year) as stock\'s confirm: {rtc(mo)} / {rtc(ms)}')
        expect('navigator_back' in ms.names(), 'stock\'s confirm goes back')
    mo = DM(auto=0, clock=(2026, 11, 15, 8, 0)); mo.call(PSYMS['dt_edit_start'], count=200000)
    mo.call(PSYMS['dt_set'], a0=3 * 4096 + 21, count=200000); mo.call(PSYMS['dt_set'], a0=4 * 4096 + 45, count=200000); mo.call(PSYMS['dt_set'], a0=1 * 4096 + 1, count=200000)
    mo.clock = (2026, 11, 16, 8, 3)   # the clock moved on while the page was open: Set Time takes the date it has now, and the typed time
    expect(mo.call(PSYMS['dt_apply'], a0=1, count=2000000) == 0 and [c for c in mo.calls if c[0] == 'set_systime'] == [('set_systime', 2026, 11, 16, 21, 45)], 'Set Time: the typed hour and minute, the date of now, seconds 0')
    mo = DM(auto=1, clock=(2026, 11, 15, 8, 0)); mo.call(PSYMS['dt_edit_start'], count=200000)
    expect(mo.call(PSYMS['dt_apply'], a0=0, count=2000000) == 0xffffffff and not [c for c in mo.calls if c[0] == 'set_systime'], 'Set Date is refused while Set Automatically is on (stock disables its Manual row)')
    pins = {a: w for a, w, _ in pod.DATETIME_PINS}
    expect(all(a in pins for a in (0x4a5970, 0x4a5aa8, 0x4a5aac, 0x4a5acc, 0x4a5aec, 0x4a58c0, 0x4a58cc, 0x4a58d8, 0x4d77bc, 0x4d77cc)), 'the manual page\'s init clamps, its confirm\'s call and set_systime\'s call are pinned')


def settings_tests(ctx):
    """The Settings row, the pages, their rows and kinds, the dimming, the values, the pickers, the Set rows and the assets."""
    expect, P = ctx.expect, pod_pages
    V = P.GENERAL_PAGE
    labels = [r.label for r in V.rows]
    di = labels.index('Date & Time')
    expect(V.rows[di].action == P.ACT_PAGE and V.rows[di].arg == P.DATETIME_PAGE_INDEX and P.row_kind(V.rows[di]) == 'link' and labels[di - 1] == 'About' and labels[di + 1] == 'Keyboards' and P.PAGES[P.DATETIME_PAGE_INDEX] is P.DATETIME_PAGE,
           'Settings > General > Date & Time: after About, opens our page')
    D, Z, DD, DT = P.DATETIME_PAGE, P.PAGES[P.TIMEZONE_PAGE_INDEX], P.PAGES[P.DTDATE_PAGE_INDEX], P.PAGES[P.DTTIME_PAGE_INDEX]
    expect([(r.label, r.action) for r in D.rows] == [('Set Automatically', P.ACT_DTAUTO), ('Time Zone', P.ACT_DTZONE), ('Date', P.ACT_DTDATE), ('Time', P.ACT_DTTIME), ('24-Hour Time', P.ACT_DT24)]
           and [P.row_kind(r) for r in D.rows] == ['switch', 'value', 'value', 'value', 'switch'] and D.title == 'Date & Time' and D.key == 'm1plus_datetime', 'the page\'s rows and their kinds')
    expect([r.arg for r in D.rows[1:4]] == [P.TIMEZONE_PAGE_INDEX, P.DTDATE_PAGE_INDEX, P.DTTIME_PAGE_INDEX], 'Time Zone, Date and Time open our pages')
    expect(len(Z.rows) == 43 and [r.arg for r in Z.rows] == list(tzmod.ORDER) and [r.label for r in Z.rows] == [tzmod.TIMEZONES[i][0] for i in tzmod.ORDER] and all(r.action == P.ACT_DTZONESET and P.row_kind(r) == 'check' for r in Z.rows),
           'the zone picker: one check row per zone of our table, in its order, the argument is the saved index')
    expect([(r.label, r.action, r.arg) for r in DD.rows] == [('Year', P.ACT_DTFIELD, P.DTFIELD_PAGES[0]), ('Month', P.ACT_DTFIELD, P.DTFIELD_PAGES[1]), ('Day', P.ACT_DTFIELD, P.DTFIELD_PAGES[2]), ('Set Date', P.ACT_DTAPPLY, 0)]
           and [(r.label, r.action, r.arg) for r in DT.rows] == [('Hour', P.ACT_DTFIELD, P.DTFIELD_PAGES[3]), ('Minute', P.ACT_DTFIELD, P.DTFIELD_PAGES[4]), ('Set Time', P.ACT_DTAPPLY, 1)]
           and [P.row_kind(r) for r in DD.rows] == ['value'] * 3 + ['action'], 'the Date and Time pages')
    sizes = [len(P.PAGES[i].rows) for i in P.DTFIELD_PAGES]
    expect(sizes == [29, 12, 31, 24, 60] and [r.label for r in P.PAGES[P.DTFIELD_PAGES[3]].rows][:3] == ['00', '01', '02'] and P.PAGES[P.DTFIELD_PAGES[0]].rows[0].arg == 2022
           and P.PAGES[P.DTFIELD_PAGES[2]].rows[30].arg == 2 * 4096 + 31, 'the field pickers: 2022 .. 2050, 12 months, 31 days, 24 hours, 60 minutes; arg = field * 4096 + value')
    expect((P.ACT_DTAUTO, P.ACT_DTZONE, P.ACT_DTZONESET, P.ACT_DTDATE, P.ACT_DTTIME, P.ACT_DT24, P.ACT_DTFIELD, P.ACT_DTSET, P.ACT_DTAPPLY) == tuple(range(157, 166)) and {P.ACT_DTAUTO, P.ACT_DT24} <= set(P.SWITCH_ACTIONS)
           and {P.ACT_DTZONE, P.ACT_DTDATE, P.ACT_DTTIME, P.ACT_DTFIELD} <= set(P.VALUE_ACTIONS) and {P.ACT_DTZONESET, P.ACT_DTSET} <= set(P.CHECK_ACTIONS), 'the actions 157 .. 165')
    expect(not any(r.action == P.ACT_STOCK for p in (D, Z, DD, DT) for r in p.rows) and not any(n.split('/')[-1] in ('typedatetime_page', 'datetime_page', 'autosynctime_page') for n, *_ in P.STOCK_PAGES), 'no row opens a stock page')
    import pod_i18n
    import mod_icons
    for loc in pod_i18n.LOCALES:
        expect(all(pod_i18n.TEXT[k][loc] for k in ('Date & Time', 'Set Automatically', 'Time Zone', 'Date', 'Time', '24-Hour Time', 'Year', 'Month', 'Day', 'Hour', 'Minute', 'Set Date', 'Set Time')), f'the page texts have a translation in {loc}')
    expect(all(pod_i18n.key_for(t) is None for t in tzmod.TIMEZONES[0][:1] + ('2026', '07', '31')), 'zone names and numbers are plain texts')
    expect([mod_icons.CARD_GLYPHS[k] for k in ('Date & Time', 'Set Automatically', 'Time Zone', 'Date', 'Time', '24-Hour Time')] == ['calendar-clock', 'refresh-cw', 'globe', 'calendar', 'clock', 'sun-moon'], 'the glyphs')

    def open_on(m, index, kinds=('pod_value', 'pod_switch', 'pod_check', 'pod_label')):
        n = len(P.PAGES[index].rows)
        m.widgets = {nm: 0x30000000 + 0x100 * i for i, nm in enumerate(['btn_return', 'btn_backtoplayer'] + [f'{k}{i}' for k in ('pod_row',) + tuple(kinds) for i in range(n)])}
        row = m.alloc(12)
        m.setword(row, m.cstr('pod_row0')); m.setword(row + 4, P.ACT_PAGE); m.setword(row + 8, index)
        m.call(PSYMS['on_row'], a0=row, count=8000000)
        return m

    def page(index, **state): return open_on(DM(**state), index)

    def value(m, i):
        return [c[2] for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == m.widgets[f'pod_value{i}']]

    def dim(m, i):
        o = [c[2] for c in m.calls if c[0] == 'widget_set_opacity' and c[1] == m.widgets[f'pod_row{i}']]
        s = [c[2] for c in m.calls if c[0] == 'widget_set_sensitive' and c[1] == m.widgets[f'pod_row{i}']]
        return (o[-1], s[-1]) if o and s else None

    def sw(m, i): return [c[2] for c in m.calls if c[0] == 'image_base_set_image' and c[1] == m.widgets[f'pod_switch{i}']]

    def saves(m): return [c for c in m.calls if c[0] in ('write_int_config', 'select_timezone', 'change_time24h_12h', 'set_systime')]
    m = page(P.DATETIME_PAGE_INDEX, auto=1, tz=40, h24=1, clock=(2026, 11, 5, 9, 7))
    expect(('window_open', D.key) in m.calls and value(m, 1)[-1] == 'GMT+5:30 Kolkata' and value(m, 2)[-1] == '2026-11-05' and value(m, 3)[-1] == '09:07' and sw(m, 0) == ['sset_on'] and sw(m, 4) == ['sset_on'] and not saves(m),
           f'auto on: the zone\'s label, the date, the time, both switches on, nothing written ({[value(m, i) for i in (1, 2, 3)]})')
    expect(dim(m, 1) in (None, (255, 1)) and dim(m, 2)[1] == 0 and dim(m, 3)[1] == 0 and dim(m, 2)[0] < 255, f'auto on: Time Zone is live (never touched), Date and Time are dimmed and take no tap ({dim(m, 1)}, {dim(m, 2)}, {dim(m, 3)})')
    m = page(P.DATETIME_PAGE_INDEX, auto=0, tz=22, h24=0, clock=(2026, 11, 5, 21, 7))
    expect(value(m, 1)[-1] == 'GMT+8 Shanghai' and value(m, 3)[-1] == '9:07 PM' and sw(m, 0) == ['sset_off'] and sw(m, 4) == ['sset_off'] and dim(m, 1) in (None, (255, 1)) and dim(m, 2) == (255, 1) and dim(m, 3) == (255, 1),
           'auto off: Time Zone, Date and Time all live; 12-hour time')
    m = page(P.DATETIME_PAGE_INDEX, auto=0, need=0)
    m.calls = []; m.click('pod_row0')
    expect(m.state()[:2] == (1, 1) and saves(m) == [('write_int_config', 1, 'SYSSET', 'AUTOSYNCTIME')] and sw(m, 0)[-1] == 'sset_on' and dim(m, 1) in (None, (255, 1)) and dim(m, 2)[1] == 0 and dim(m, 3)[1] == 0,
           'a tap turns Set Automatically on: the byte, the sync request, the save; the switch and the dimming follow at once')
    m.click('pod_row0')
    expect(m.state()[:2] == (0, 0) and sw(m, 0)[-1] == 'sset_off' and dim(m, 1) in (None, (255, 1)) and dim(m, 2)[1] == 1, 'and off again')
    m.calls = []; m.click('pod_row4')
    expect(m.byte(H24) == 0 and saves(m) == [('change_time24h_12h', 0), ('write_int_config', 0, 'SYSSET', 'TIME24H')] and sw(m, 4)[-1] == 'sset_off', '24-Hour Time off: stock\'s two calls')
    m = page(P.DATETIME_PAGE_INDEX, auto=1, tz=22, h24=1, clock=(2026, 11, 5, 21, 7))
    m.u.mem_write(AUTO, b'\0'); m.setword(TZ, 0); m.clock = (2026, 12, 25, 1, 2); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
    expect(value(m, 1)[-1] == 'GMT-12 Baker Island' and value(m, 2)[-1] == '2026-12-25' and value(m, 3)[-1] == '01:02' and sw(m, 0) == ['sset_off'] and dim(m, 2)[1] == 1 and not saves(m),
           'back in front: the zone, the clock and the switch follow stock\'s pages (a change under All System Settings shows)')
    # the zone picker: the check follows the word, a tap saves as stock's row does
    m = page(P.TIMEZONE_PAGE_INDEX, tz=40)
    checks = [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] in [m.widgets[f'pod_check{i}'] for i in range(43)]]
    visible = {i: [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] == m.widgets[f'pod_check{i}']][-1] for i in range(43)}
    expect(('window_open', Z.key) in m.calls and [i for i in visible if visible[i]] == [tzmod.ORDER.index(40)] and checks and not saves(m), 'the picker checks the saved zone\'s row (Kolkata), nothing written')
    m.calls = []; m.click('pod_row0')
    expect(m.word(TZ) == tzmod.ORDER[0] and saves(m) == [('write_int_config', tzmod.ORDER[0], 'SYSSET', 'TIMEZONE'), ('select_timezone', tzmod.ORDER[0])], 'the top row (the westernmost zone) is chosen: the word, the save, select_timezone')
    for auto in (0, 1):   # stock's zone click tests no auto byte: the zone is chosen with Set Automatically off as well as on
        m = page(P.TIMEZONE_PAGE_INDEX, auto=auto, tz=40)
        m.calls = []; m.click('pod_row5')
        z = tzmod.ORDER[5]
        expect(m.word(TZ) == z and saves(m) == [('write_int_config', z, 'SYSSET', 'TIMEZONE'), ('select_timezone', z)], f'a zone is chosen with auto={auto}: exactly stock\'s zone-click writes')
    # the Date page and a field picker
    m = page(P.DTDATE_PAGE_INDEX, auto=0, clock=(2026, 11, 15, 14, 5))
    expect([value(m, i)[-1] for i in range(3)] == ['2026', '11', '15'], 'the Date page starts from the clock')
    m.calls = []; m.click('pod_row0')
    expect([c[1] for c in m.calls if c[0] == 'window_open'] == [P.PAGES[P.DTFIELD_PAGES[0]].key] and 'navigator_to' not in m.names(), 'Year opens our picker')
    m = open_on(page(P.DTDATE_PAGE_INDEX, auto=0, clock=(2026, 1, 31, 14, 5)), P.DTFIELD_PAGES[1])
    shown = lambda n: [i for i in range(n) if [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] == m.widgets[f'pod_check{i}']][-1]]
    expect(shown(12) == [0], 'the Month picker checks January')
    m.calls = []; m.click('pod_row1')
    expect(shown(12) == [1] and not saves(m), 'February: the check moves, nothing is written (the date is typed in memory)')
    m = open_on(m, P.DTFIELD_PAGES[2])
    expect(shown(31) == [27], 'the Day picker: the 31st became the 28th with February')
    m.calls = []; m.click('pod_row30')
    expect(shown(31) == [27], 'the 31st of February is refused: the check stays')
    m = page(P.DTDATE_PAGE_INDEX, auto=0, clock=(2026, 11, 15, 14, 5))
    m.calls = []; m.click('pod_row3')
    expect([c for c in m.calls if c[0] == 'set_systime'] == [('set_systime', 2026, 11, 15, 14, 5)] and 'navigator_back' in m.names(), 'Set Date: stock\'s set_systime with the typed date and the clock\'s time, then back')
    m = page(P.DTTIME_PAGE_INDEX, auto=0, clock=(2026, 11, 15, 14, 5))
    expect([value(m, i)[-1] for i in range(2)] == ['14', '05'], 'the Time page starts from the clock')
    m.calls = []; m.click('pod_row2')
    expect([c for c in m.calls if c[0] == 'set_systime'] == [('set_systime', 2026, 11, 15, 14, 5)] and 'navigator_back' in m.names(), 'Set Time: the same call with the clock\'s own minute')
    # the assets
    raw = os.path.join(WORK, 'rootfs/release/assets/default/raw/ui')
    dtree = awtk_ui.parse(open(os.path.join(raw, 'm1plus_datetime.bin'), 'rb').read())
    se = awtk_ui.parse(open(os.path.join(raw, 'm1plus_general.bin'), 'rb').read())
    expect([dtree.find(f'pod_row{i}').find('pod_icon').get('image') for i in range(5)] == ['pod_ci_refresh_cw', 'pod_ci_globe', 'pod_ci_calendar', 'pod_ci_clock', 'pod_ci_sun_moon'] and dtree.find('label_title').get('tr_text') == 'Date & Time'
           and se.find(f'pod_row{di}').find('pod_icon').get('image') == 'pod_ci_calendar_clock', 'the page asset: the glyphs and the title; the General row\'s glyph')
    zt = awtk_ui.parse(open(os.path.join(raw, 'm1plus_timezone.bin'), 'rb').read())
    expect([zt.find(f'pod_label{i}').get('text') for i in range(43)] == [tzmod.TIMEZONES[i][0] for i in tzmod.ORDER] and all(zt.find(f'pod_check{i}').get('visible') == 'false' for i in range(43)), 'the zone picker asset: our labels as plain texts, a hidden check each')


SECTIONS = [auto_tests, h24_tests, zone_tests, clock_tests, settings_tests]
