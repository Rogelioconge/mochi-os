"""Settings > Bluetooth, the control layer (patch/btset.c, docs/modules/bluetooth.md "Control layer"). Every action is stock's own sequence: the tests run stock's handlers under the emulator (the row
handler 0x4a3a7c, the Quality choice handler 0x4a4850, the page's init 0x4a411c, its timer callback 0x4a3fa0, the close handlers, btdevice_listitem_layout 0x4a33c8, adjustA2dpVolume) with the backend and the
widget helpers mocked as recorders, run ours on the same starting state, and compare the final state, the ordered calls with their arguments, and the state words at each call. The demo they run in is the built
one, so the switch row is as tools/coex.py leaves it."""
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

D = {n: pod.DATA[n][0] for n in ('BT_FLAG', 'WIFI_FLAG', 'BT_CODING', 'BT_INITSTATUS', 'BT_INITTIME', 'BT_CONNECTSTATUS', 'BT_LINKSTATUS', 'BT_SHOWCODING', 'BT_SEARCHTIME', 'BT_START_SCAN', 'BT_LOCALNAME', 'BT_LOCALMAC',
                                  'BT_SHOWLIST', 'BT_PAIRLIST', 'BT_LINKLIST', 'BT_A2DP_DIRECTION', 'BT_RECV_VOLUME', 'BT_A2DP_EVENT', 'BT_RECV_PAGE', 'BT_REFRESH', 'HEADSET_OUTPUT')}
WIN = 0x30000000
ROW, QUALITY, TIMER, PAGE_INIT, LAYOUT, ADJUST = 0x4a3a7c, 0x4a4850, 0x4a3fa0, 0x4a411c, 0x4a33c8, 0x4d28ac
CLOSE_WIN, BACK_CLICK, BACKGROUND = 0x4a28bc, 0x4a29cc, 0x4a2a20
STOCK_PLT = {0x742da0: 'memset', 0x742160: 'memcpy', 0x742c90: 'strcmp', 0x743570: 'strcpy', 0x70f8d8: 'tk_snprintf', 0x7435b0: 'atoi', 0x742ab0: 'snprintf', 0x743590: 'deque_size', 0x742c70: 'deque_at',
             0x741fb0: 'pthread_mutex_lock', 0x743460: 'pthread_mutex_unlock', 0x668a94: 'widget_foreach', 0x743130: 'btctl_transport_get_volume', 0x742420: 'btctl_transport_set_volume'}
STOCK_PAGE = {0x4a3734: 'bt_rebuild', 0x4a2dd4: 'bt_spinner', 0x4a2b68: 'bt_timer_add', 0x4a28f0: 'bt_timer_remove', 0x4a2d2c: 'lay_name', 0x4a2c30: 'lay_sub', 0x4a2cc0: 'lay_del'}   # the page's own helpers: recorders
PAGE_ONLY = ('bt_rebuild', 'bt_spinner', 'bt_timer_add', 'bt_timer_remove')   # what stock does to its widgets: not compared call by call (the page acts on what ours returns)
RECORD = ('switchBluetooth', 'btStartSearch', 'btStopSearch', 'getSearchResult', 'getLocalBtName', 'switchBtPriority', 'bluetoothLink', 'adjustA2dpVolume', 'handleBluetoothLink', 'handleBluetoothPair',
          'judge_outputdevice', 'mclGetSavePlayStatus', 'set_outputchannel', 'save_stop_player', 'save_start_player', 'write_int_config', 'wifi_switch') + PAGE_ONLY
KEYS = ('msg_btinit_run', 'msg_bt_open', 'msg_unpairing', 'msg_unpaired', 'msg_disconnected', 'msg_closesynclink', 'msg_btreconnect')
EN = {'msg_btinit_run': 'Bluetooth Starting', 'msg_bt_open': 'Wi-Fi is turned on. Turn it off first?', 'msg_unpairing': 'unpair?', 'msg_unpaired': 'Unpaired', 'msg_disconnected': 'Disconnected',
      'msg_closesynclink': 'Please close SyncLink', 'msg_btreconnect': 'Reconnect Bluetooth?'}
CODEC_KEYS = ('btcode_ldachq', 'btcode_ldacst', 'btcode_ldacauto', 'btcode_aptxhd', 'btcode_aptx', 'btcode_aac', 'btcode_sbchq', 'btcode_sbc')
MAC = '%02X:00:00:00:00:%02X'


def mac(i): return MAC % (0xa0 + i, i)


class BM(Machine):
    """Stock's page code and ours, with the Bluetooth backend, the output calls and the page's own helpers mocked as recorders. `log` holds every effect (name, arguments, the state words at that moment), the
    stock dialogs included; `lists` the three device lists as stock keeps them."""
    def __init__(self):
        super().__init__()
        self.handlers.update(STOCK_PLT)
        self.handlers.update(STOCK_PAGE)
        self.page_window = WIN
        self.strings = dict(EN)
        self.reset()

    def reset(self, flag=0, wifi=0, coding=3, init=0, inittime=0, conn=0, link=0, show=0, search=0, start=0, refresh=0, headset=2, recv=0, confirm=False):
        self.log, self.calls = [], []
        self.u.mem_write(D['BT_FLAG'], bytes([flag])); self.u.mem_write(D['WIFI_FLAG'], bytes([wifi])); self.setword(D['BT_CODING'], coding); self.setword(D['BT_INITSTATUS'], init)
        self.u.mem_write(D['BT_INITTIME'], bytes([inittime & 0xff])); self.setword(D['BT_CONNECTSTATUS'], conn); self.u.mem_write(D['BT_LINKSTATUS'], bytes([link])); self.setword(D['BT_SHOWCODING'], show)
        self.u.mem_write(D['BT_SEARCHTIME'], bytes([search & 0xff])); self.u.mem_write(D['BT_START_SCAN'], bytes([start])); self.u.mem_write(D['BT_REFRESH'], bytes([refresh]))
        self.setword(D['BT_A2DP_DIRECTION'], 1); self.setword(D['BT_RECV_VOLUME'], 55); self.setword(D['BT_A2DP_EVENT'], 4); self.setword(D['HEADSET_OUTPUT'], headset); self.setword(D['BT_RECV_PAGE'], recv)
        self.u.mem_write(D['BT_LOCALNAME'], b'old name\0'); self.u.mem_write(D['BT_LOCALMAC'], b'old mac\0')
        self.confirm_yes = confirm
        self.link_ret, self.pair_ret, self.judge, self.save_status = 0, 1, None, 2   # handleBluetoothLink / Pair's results; judge_outputdevice's answer (None: the output it was given); mclGetSavePlayStatus
        self.paired, self.linked, self.out_way, self.volume = set(), [], 0, 60
        self.set_lists([], [])
        return self

    def set_lists(self, paired, others):
        """The show list as getSearchResult leaves it (the paired devices first), the pair list, in the order of the MAC list: paired = [(mac, name)], others = [...]. The link list is `linked`: [(status, mac)]."""
        self.paired = {m for m, _ in paired}
        recs = []
        for m, n in list(paired) + list(others):
            r = self.alloc(0x124); self.u.mem_write(r, bytes(0x124)); self.u.mem_write(r + 4, m.encode() + b'\0'); self.u.mem_write(r + 0x24, n.encode() + b'\0'); recs.append(r)
        self.setword(D['BT_SHOWLIST'], self.new_deque(recs))
        self.setword(D['BT_PAIRLIST'], self.new_deque(recs[:len(paired)]))
        self.setword(D['BT_LINKLIST'], self.new_deque())
        self.shown = [m for m, _ in list(paired) + list(others)]

    def b(self, a): return self.u.mem_read(a, 1)[0]
    def s8(self, a): return struct.unpack('b', self.u.mem_read(a, 1))[0]
    def state(self):
        d = D
        return (self.b(d['BT_FLAG']), self.b(d['WIFI_FLAG']), self.s32(d['BT_CODING']), self.s32(d['BT_INITSTATUS']), self.s8(d['BT_INITTIME']), self.s32(d['BT_CONNECTSTATUS']), self.b(d['BT_LINKSTATUS']),
                self.s32(d['BT_SHOWCODING']), self.s8(d['BT_SEARCHTIME']), self.b(d['BT_START_SCAN']), self.s32(d['BT_A2DP_DIRECTION']), self.s32(d['BT_RECV_VOLUME']), self.s32(d['BT_A2DP_EVENT']),
                self.s32(d['HEADSET_OUTPUT']), self.b(d['BT_REFRESH']))

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        ret = 0
        s32 = lambda v: struct.unpack('<i', struct.pack('<I', v))[0]
        if name in RECORD:
            args = {'switchBluetooth': lambda: (a0 & 0xff, a1), 'btStartSearch': tuple, 'btStopSearch': tuple, 'getSearchResult': tuple,
                    'getLocalBtName': lambda: (bytes(u.mem_read(a0, 4)), bytes(u.mem_read(a1, 4))), 'switchBtPriority': lambda: (a0,), 'bluetoothLink': lambda: (a0,), 'adjustA2dpVolume': lambda: (a0,),
                    'handleBluetoothLink': lambda: (s32(a0),), 'handleBluetoothPair': lambda: (s32(a0),), 'judge_outputdevice': lambda: (s32(a0), a1), 'mclGetSavePlayStatus': tuple,
                    'set_outputchannel': lambda: (s32(a0), a1, a2), 'save_stop_player': tuple, 'save_start_player': lambda: (a0,),
                    'write_int_config': lambda: (s32(a0), self.read_cstr(a1), self.read_cstr(a2)), 'wifi_switch': lambda: (a0,), 'bt_rebuild': tuple, 'bt_spinner': lambda: (s32(a1),),
                    'bt_timer_add': tuple, 'bt_timer_remove': tuple}[name]()
            self.log.append((name,) + args + (self.state(),))
            if name == 'btStartSearch' and self.s8(D['BT_SEARCHTIME']) == 0: u.mem_write(D['BT_SEARCHTIME'], bytes([50]))   # stock's: a scan that runs is not started again
            elif name == 'btStopSearch': u.mem_write(D['BT_SEARCHTIME'], b'\0')
            elif name == 'getLocalBtName': u.mem_write(a0, b'Player\0'); u.mem_write(a1, b'11:22:33:44:55:66\0')
            elif name == 'handleBluetoothLink': ret = self.link_ret & 0xffffffff
            elif name == 'handleBluetoothPair': ret = self.pair_ret & 0xffffffff
            elif name == 'judge_outputdevice': ret = a0 if self.judge is None else self.judge
            elif name == 'mclGetSavePlayStatus': ret = self.save_status
            elif name == 'adjustA2dpVolume': ret = 1
        elif name == 'getFormatString':
            u.mem_write(a1, self.tr(self.read_cstr(a0)).encode('latin-1') + b'\0'); ret = 1
        elif name == 'get_bluetoothcoding_text':
            if s32(a0) < 8: u.mem_write(a1, self.read_cstr(self.word(0x97ca08 + 4 * a0)).encode('latin-1') + b'\0'); ret = 1
            else: ret = 0xffffffff
        elif name == 'checkPairDev': ret = int(self.read_cstr(a0) in self.paired)
        elif name == 'getBtLinkSize': ret = len(self.linked)
        elif name == 'getBtLinkItem':
            if 0 <= s32(a0) < len(self.linked):
                st, mc = self.linked[s32(a0)]; self.setword(a1, st); self.u.mem_write(a2, mc.encode() + b'\0')
        elif name == 'mclGetOutputWay': ret = self.out_way
        elif name == 'strcpy': self.u.mem_write(a0, self.read_cstr(a1).encode('latin-1') + b'\0'); ret = a0
        elif name == 'tk_snprintf':
            text = self.read_cstr(a2) % a3; u.mem_write(a0, text.encode() + b'\0'); ret = len(text)
        elif name == 'widget_foreach': ret = 0
        elif name == 'btctl_transport_get_volume': ret = self.volume; self.log.append(('get_volume', self.state()))
        elif name == 'btctl_transport_set_volume': self.log.append(('set_volume', s32(a0)))
        elif name in ('lay_name', 'lay_sub', 'lay_del'):
            self.log.append((name, self.read_cstr(a1) if name != 'lay_del' else None, a2 if name == 'lay_name' else None))
        elif name == 'navigator_to_with_context' and self.read_cstr(a0) in ('dialog/msginfo_dialog', 'dialog/confirminfo_dialog'):
            what = 'toast' if self.read_cstr(a0) == 'dialog/msginfo_dialog' else 'confirm'
            self.log.append((what, self.read_cstr(a1 + 8), self.word(a1), self.word(a1 + 4) if what == 'toast' else 0, self.state()))
            return super()._hook(u, address, size, _)
        else: return super()._hook(u, address, size, _)
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))


def effects(m): return [e for e in m.log if e[0] not in PAGE_ONLY]
def rebuilt(m): return any(e[0] == 'bt_rebuild' for e in m.log)
def spins(m): return [e[1] for e in m.log if e[0] == 'bt_spinner']


def stock_row(m, row, x=0):
    """Stock's row handler for the row item of that number (the click's x in the event)."""
    item = m.alloc(0x40); m.setword(item + 0x10, m.cstr(str(row)))
    ev = m.alloc(0x40); m.setword(ev + 0x18, x)
    m.call(ROW, a0=item, a1=ev, count=5000000)


def stock_quality(m, c):
    item = m.alloc(0x40); m.setword(item + 0x10, m.cstr(str(c)))
    m.call(QUALITY, a0=item, count=5000000)


def stock_tick(m):
    tm = m.alloc(0x40); m.setword(tm + 0x24, WIN)
    m.call(TIMER, a0=tm, count=5000000)


def ours(m, fn, a0=0, a1=0):
    m.log, m.calls = [], []
    if isinstance(a0, str): a0 = m.cstr(a0)
    return m.call(PSYMS[fn], a0=a0, count=5000000) if not a1 else m.call(PSYMS[fn], a0=a0, a1=a1, count=5000000)


def same(expect, ms, mo, what, rebuild=None):
    """The final state, the effects in order with their arguments and the state words at each call. `rebuild`: ours' answer must say what stock's rebuild did (BS_REBUILD or not)."""
    es, eo = effects(ms), effects(mo)
    expect(ms.state() == mo.state() and es == eo, f'{what}: state {mo.state()} / {ms.state()}; calls {eo} / {es}')
    if rebuild is not None: expect(rebuilt(ms) == (rebuild == 1), f'{what}: stock rebuilds {rebuilt(ms)}, ours says {rebuild}')


def pair_of(ctx):
    """Two machines (stock's run and ours) for a test function, made once."""
    return BM(), BM()


# ---------------------------------------------------------------------------
def switch_tests(ctx):
    """bs_toggle against stock's row handler on row 0: the guard, the Wi-Fi confirm, switchBluetooth(flag, 1), the rebuild; bs_on / bs_starting."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    pins = {a: w for a, w, _ in pod.BLUETOOTH_PINS}
    expect(pins[0x4a3b64] == 0x10400004 and ms.word(0x4a3b64) == 0x10000004, 'the switch row is as tools/coex.py leaves it: the Wi-Fi flag test after the confirm is a branch (Wi-Fi stays on)')
    n = 0
    for flag in (0, 1):
        for wifi in (0, 1):
            for yes in (False, True):
                for init in (0, 1, 0x65):
                    kw = dict(flag=flag, wifi=wifi, confirm=yes, init=init, link=1, show=3, search=20)
                    ms.reset(**kw); stock_row(ms, 0)
                    mo.reset(**kw); r = mo.call(PSYMS['bs_toggle'], count=5000000)
                    same(expect, ms, mo, f'switch (flag {flag}, Wi-Fi {wifi}, confirm {yes}, init {init:#x})', r)
                    expect(not any(e[0] == 'wifi_switch' for e in ms.log + mo.log), 'Wi-Fi is never switched by the Bluetooth switch (as patched)')
                    sw = [e for e in mo.log if e[0] == 'switchBluetooth']
                    if init: expect(not sw and [e[0] for e in mo.log] == ['toast'] and mo.log[0][1:4] == ('Bluetooth Starting', 1, 2000) and r == 0, f'init {init:#x}: the toast of kind 1 for 2000 ms and nothing else')
                    elif flag == 0 and wifi and not yes: expect(not sw and r == 1, 'Cancel on the Wi-Fi question: nothing started, the page rebuilt')
                    else: expect(len(sw) == 1 and sw[0][1:3] == (flag, 1) and r == 1, f'switchBluetooth({flag}, 1) once, the page rebuilt')
                    if flag == 0 and wifi and not init: expect(mo.log[0][:4] == ('confirm', 'Wi-Fi is turned on. Turn it off first?', 5, 0), f'the Wi-Fi question: {mo.log[0]}')
                    n += 1
    for flag in (0, 1, 2):
        mo.reset(flag=flag)
        expect(mo.call(PSYMS['bs_on']) == (flag != 0), f'the byte {flag}: bs_on')
    for init, want in ((0, 0), (1, 1), (0x65, 1), (0x66, 1), (3, 1)):
        mo.reset(init=init)
        expect(mo.call(PSYMS['bs_starting']) == want, f'init status {init:#x}: bs_starting {want}')
    expect(n == 24, 'twenty-four starting states compared')


def scan_tests(ctx):
    """bs_open, bs_tick (the whole 50-tick count-down), bs_search and bs_close against stock's page init, its 200 ms timer, the Search row and the close handlers."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    for flag in (0, 1):
        for init in (0, 1, 0x65):
            for search in (0, 30):
                for refresh in (0, 1):
                    for start in (0, 1):
                        kw = dict(flag=flag, init=init, search=search, refresh=refresh, start=start, wifi=1)
                        ms.reset(**kw); ms.call(PAGE_INIT, a0=WIN, count=5000000)
                        mo.reset(**kw); mo.call(PSYMS['bs_open'], count=5000000)
                        es = [e for e in effects(ms) if e[0] != 'widget_on']
                        expect(ms.state() == mo.state() and es == effects(mo), f'open (flag {flag}, init {init:#x}, scan {search}, refresh {refresh}, start {start}): {mo.state()} / {ms.state()}; {effects(mo)} / {es}')
                        expect(bytes(ms.u.mem_read(D['BT_LOCALNAME'], 8)) == bytes(mo.u.mem_read(D['BT_LOCALNAME'], 8)) and bytes(ms.u.mem_read(D['BT_LOCALMAC'], 8)) == bytes(mo.u.mem_read(D['BT_LOCALMAC'], 8)),
                               'open: the local name and MAC are cleared and read again as stock does')
    mo.reset(flag=1); mo.call(PSYMS['bs_open'], count=5000000)
    expect([e[0] for e in effects(mo)] == ['getLocalBtName', 'btStartSearch'] and effects(mo)[0][1:3] == (b'\0\0\0\0', b'\0\0\0\0') and mo.state()[8] == 50, f'open with Bluetooth on: the name read into cleared buffers, a scan started ({effects(mo)})')
    # one tick at a time, ours and stock's side by side on every state
    for flag in (0, 1):
        for init in (0, 1, -1):
            for inittime in (0, 1, 50):
                for search in (0, 1, 2, 3, 24, 25, 26, 27, 49, 50, 127):
                    for refresh in (0, 1):
                        for start in (0, 1):
                            kw = dict(flag=flag, init=init, inittime=inittime, search=search, refresh=refresh, start=start)
                            ms.reset(**kw); stock_tick(ms)
                            mo.reset(**kw); r = mo.call(PSYMS['bs_tick'], count=5000000)
                            tag = f'tick (flag {flag}, init {init}, inittime {inittime}, scan {search}, refresh {refresh}, start {start})'
                            same(expect, ms, mo, tag)
                            sp = [(r >> 8) & 0xff] if r & 2 else []
                            sp = [x - 256 if x > 127 else x for x in sp]
                            expect(rebuilt(ms) == bool(r & 1) and spins(ms) == sp and not (r & ~0xff03), f'{tag}: stock rebuilds {rebuilt(ms)}, spins {spins(ms)}; ours {r:#x}')
    # the whole scan: started by the page's init or by the flag, counted down to the end; both machines in step
    for how in ('open', 'flag', 'search'):
        ms.reset(flag=1, wifi=0); mo.reset(flag=1, wifi=0)
        if how == 'flag': ms.u.mem_write(D['BT_START_SCAN'], b'\1'); mo.u.mem_write(D['BT_START_SCAN'], b'\1')
        if how == 'open': ms.call(PAGE_INIT, a0=WIN, count=5000000); mo.call(PSYMS['bs_open'], count=5000000)
        if how == 'search': stock_row(ms, 4); mo.call(PSYMS['bs_search'], count=5000000)
        started = ms.s8(D['BT_SEARCHTIME']) if how != 'flag' else 0
        expect(ms.state() == mo.state() and (how == 'flag' or started == 50), f'scan by {how}: the count-down is at {started} in both')
        stops, refreshes, ticks = 0, [], 0
        for t in range(1, 61):
            ms.log, mo.log = [], []
            stock_tick(ms); r = mo.call(PSYMS['bs_tick'], count=5000000)
            same(expect, ms, mo, f'scan by {how}, tick {t}')
            sp = [x - 256 if x > 127 else x for x in ([(r >> 8) & 0xff] if r & 2 else [])]
            expect(rebuilt(ms) == bool(r & 1) and spins(ms) == sp, f'scan by {how}, tick {t}: rebuild {rebuilt(ms)} / {r & 1}, spinner {spins(ms)} / {sp}')
            stops += sum(1 for e in mo.log if e[0] == 'btStopSearch'); ticks += 1 if ms.s8(D['BT_SEARCHTIME']) else 0
            if any(e[0] == 'getSearchResult' for e in mo.log): refreshes.append(t)
            if how != 'flag' and r & 1: expect(any(e[0] == 'getSearchResult' for e in mo.log), 'a rebuild by the scan reads the results first')
            if how == 'flag' and t == 1: expect(effects(mo) and effects(mo)[0][0] == 'btStartSearch' and effects(mo)[0][-1][9] == 1 and mo.state()[9] == 0 and mo.state()[8] == 50, 'bt_start_scan: the scan is started, then the request cleared')
        expect(mo.state()[8] == 0 and stops == 1, f'scan by {how}: ends stopped once, the count-down at 0 ({stops} stops)')
        if how != 'flag': expect(refreshes == [25, 49], f'scan by {how}: the results are read at 5 s and at the end: ticks {refreshes}')
        else: expect(refreshes == [26, 50], f'scan by {how}: the results are read at 5 s and at the end: ticks {refreshes}')
    # the Search row, the close handlers
    for init in (0, 1):
        for search in (0, 40):
            ms.reset(flag=1, init=init, search=search); stock_row(ms, 4)
            mo.reset(flag=1, init=init, search=search); r = mo.call(PSYMS['bs_search'], count=5000000)
            same(expect, ms, mo, f'Search row (init {init}, scan {search})'); expect(r == 0 and not rebuilt(ms), 'the Search row rebuilds nothing')
    for fn, handler in (('close', CLOSE_WIN), ('background', BACKGROUND)):
        ms.reset(flag=1, search=30)
        ms.call(handler, a0=WIN, count=5000000)
        mo.reset(flag=1, search=30); mo.call(PSYMS['bs_close'], count=5000000)
        same(expect, ms, mo, f'stop on {fn}')
        expect([e[0] for e in effects(mo)] == ['btStopSearch'] and mo.state()[8] == 0, f'{fn}: btStopSearch, nothing else')
    ms.reset(flag=1, search=30); ms.call(BACK_CLICK, a0=WIN, count=5000000)
    expect([e[0] for e in effects(ms)] == ['btStopSearch'], 'the return button: btStopSearch (then the timer removal and window_close, the page\'s)')
    for s, want in ((0, 0), (1, 1), (50, 1), (127, 1), (-1, 0), (-128, 0)):
        mo.reset(search=s)
        expect(mo.call(PSYMS['bs_scanning']) == want, f'scan count {s}: bs_scanning {want} (a signed byte, as the timer reads it)')


def device_rows(m, paired, others, flag=1):
    """Stock's row number of each show-list entry (docs/modules/bluetooth.md section 1): the switch and four rows, the headers, then the devices."""
    p, k = len(paired), len(others)
    rows, r = {}, 5
    if p: r += 1
    for i, (mc, _) in enumerate(paired): rows[mc] = r; r += 1
    if k: r += 1
    for mc, _ in others: rows[mc] = r; r += 1
    return rows


def link_tests(ctx):
    """bs_link against stock's row handler on every device row (a tap left of the bt_del icon)."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    layouts = (([(mac(1), 'Alpha'), (mac(2), 'Beta')], [(mac(3), 'Gamma'), (mac(4), 'Delta')]), ([], [(mac(5), 'Echo'), (mac(6), 'Foxtrot'), (mac(7), 'Golf')]), ([(mac(8), 'Hotel')], []),
               ([(mac(9), 'India')], [(mac(10), 'Juliet')]))
    n = 0
    for paired, others in layouts:
        rows = device_rows(ms, paired, others)
        for mc, name in paired + others:
            for res in (-1, 0, 1, 2):
                for judge, save in ((None, 2), (0, 2), (0, 1)):
                    for conn, init in ((0, 0), (1, 0), (0, 1)):
                        kw = dict(flag=1, search=30, conn=conn, init=init, headset=2)
                        for m in (ms, mo): m.reset(**kw); m.set_lists(paired, others); m.link_ret, m.judge, m.save_status = res, judge, save
                        stock_row(ms, rows[mc], x=100)
                        r = ours(mo, 'bs_link', mc)
                        same(expect, ms, mo, f'tap {name} ({mc}, result {res}, judge {judge}, status {save}, connect {conn}, init {init})', r)
                        n += 1
                        if not init and not conn: expect([e[1] for e in mo.log if e[0] == 'handleBluetoothLink'] == [mo.shown.index(mc)], f'{name}: the show-list index handed to stock is its own ({mo.shown.index(mc)})')
    expect(n >= 150, f'{n} device taps compared with stock')
    # a closer look at what each result does
    paired, others = layouts[0]
    for res, want in ((-1, ['btStopSearch', 'handleBluetoothLink', 'toast']), (1, ['btStopSearch', 'handleBluetoothLink', 'judge_outputdevice', 'mclGetSavePlayStatus', 'set_outputchannel', 'toast', 'save_start_player']),
                      (0, ['btStopSearch', 'handleBluetoothLink']), (2, ['btStopSearch', 'handleBluetoothLink'])):
        mo.reset(flag=1, search=30, headset=2); mo.set_lists(paired, others); mo.link_ret, mo.judge, mo.save_status = res, 0, 2
        r = ours(mo, 'bs_link', mac(3))
        got = [e[0] for e in mo.log]
        expect(got[:len(want)] == want and len(got) == len(want) and r == (0 if res == -1 else 1), f'result {res}: {got}, answers {r}')
        if res == -1: expect(mo.log[-1][1:4] == ('Please close SyncLink', 1, 2000), f'SyncLink: {mo.log[-1]}')
        if res == 1: expect(mo.log[-2][1:4] == ('Disconnected', 1, 2000) and mo.log[-1][:2] == ('save_start_player', 1), f'disconnect: the toast, then the restart, no results read ({mo.log[-3:]})')
    # the device is gone: nothing is called but the scan stop, and the page is told to read the list again
    mo.reset(flag=1, search=30); mo.set_lists(paired, others)
    r = ours(mo, 'bs_link', mac(99))
    expect(r == 1 and [e[0] for e in mo.log] == ['btStopSearch'], f'a device that is not listed: only btStopSearch, rebuild ({[e[0] for e in mo.log]}, {r})')
    # a stale list: the list changed between the page's draw and the tap; the MAC still finds its device
    mo.reset(flag=1); mo.set_lists([(mac(3), 'Gamma')] + paired, others); mo.link_ret = 0
    ours(mo, 'bs_link', mac(1))
    expect([e[1] for e in mo.log if e[0] == 'handleBluetoothLink'] == [1], 'the index is the one in the list now, not the one the page drew')


def forget_tests(ctx):
    """bs_forget against stock's row handler on the bt_del icon (x >= 230) of every paired device."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    layouts = (([(mac(1), 'Alpha'), (mac(2), 'Beta')], [(mac(3), 'Gamma')]), ([(mac(4), 'Delta')], []))
    n = 0
    for paired, others in layouts:
        rows = device_rows(ms, paired, others)
        for mc, name in paired:
            for yes in (False, True):
                for res in (0, 1, 2, 3):
                    for judge, save in ((None, 2), (0, 2), (0, 1)):
                        for conn, init in ((0, 0), (1, 0), (0, 1)):
                            kw = dict(flag=1, search=30, conn=conn, init=init, confirm=yes, headset=2)
                            for m in (ms, mo): m.reset(**kw); m.set_lists(paired, others); m.pair_ret, m.judge, m.save_status = res, judge, save
                            stock_row(ms, rows[mc], x=250)
                            r = ours(mo, 'bs_forget', mc)
                            same(expect, ms, mo, f'forget {name} (confirm {yes}, result {res}, judge {judge}, status {save}, connect {conn}, init {init})', r)
                            n += 1
    expect(n == 216, f'{n} forgets compared with stock')
    paired, others = layouts[0]
    mo.reset(flag=1, search=30, confirm=True, headset=2); mo.set_lists(paired, others); mo.pair_ret, mo.judge = 2, 0
    r = ours(mo, 'bs_forget', mac(2))
    got = [(e[0], e[1] if e[0] in ('confirm', 'toast') else None) for e in mo.log]
    expect(r == 1 and got == [('btStopSearch', None), ('confirm', 'unpair?'), ('handleBluetoothPair', None), ('judge_outputdevice', None), ('mclGetSavePlayStatus', None), ('set_outputchannel', None),
                              ('toast', 'Unpaired'), ('getSearchResult', None), ('save_start_player', None)], f'the forget of the connected device: {got}')
    expect(mo.log[1][2] == 1 and [e[2:4] for e in mo.log if e[0] == 'toast'] == [(1, 4000)] and [e[1] for e in mo.log if e[0] == 'handleBluetoothPair'] == [1], 'the confirm is kind 1, the toast kind 1 for 4000 ms, the index its own')
    # not paired, not listed, a list that changes under the confirm
    mo.reset(flag=1, confirm=True); mo.set_lists(paired, others)
    r = ours(mo, 'bs_forget', mac(3))
    expect(r == 0 and [e[0] for e in mo.log] == ['btStopSearch'], f'an unpaired device is not forgotten: {[e[0] for e in mo.log]}')
    r = ours(mo, 'bs_forget', mac(99))
    expect(r == 1 and [e[0] for e in mo.log] == ['btStopSearch'], f'a device that is not listed: {[e[0] for e in mo.log]}')
    mo.reset(flag=1, confirm=True); mo.set_lists(paired, others)
    mo.on_confirm = lambda m: m.set_lists([(mac(3), 'Gamma'), (mac(2), 'Beta')], [])   # the list is refilled while the question is up
    mo.pair_ret = 1
    ours(mo, 'bs_forget', mac(2))
    mo.on_confirm = None
    expect([e[1] for e in mo.log if e[0] == 'handleBluetoothPair'] == [1], 'a list refilled under the confirm: the index is looked up again after it')
    mo.reset(flag=1, confirm=True); mo.set_lists(paired, others)
    mo.on_confirm = lambda m: m.set_lists([(mac(3), 'Gamma')], [])
    r = ours(mo, 'bs_forget', mac(2)); mo.on_confirm = None
    expect(r == 1 and 'handleBluetoothPair' not in [e[0] for e in mo.log], 'the device went while the question was up: nothing is unpaired')


def codec_tests(ctx):
    """bs_codec_set against stock's Quality choice handler 0x4a4850 for every codec, every state it can find; bs_codec, bs_codec_key."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    n = 0
    for old in (0, 3, 7):
        for c in range(8):
            for link, show in ((0, 0), (1, 0), (0, 3), (1, 3), (1, 13), (2, 1)):
                for yes in (False, True):
                    for judge, save in ((None, 2), (0, 2), (0, 1)):
                        for conn in (0, 1):
                            kw = dict(flag=1, coding=old, link=link, show=show, conn=conn, confirm=yes, headset=2)
                            ms.reset(**kw); ms.judge, ms.save_status = judge, save; stock_quality(ms, c)
                            mo.reset(**kw); mo.judge, mo.save_status = judge, save; r = ours(mo, 'bs_codec_set', c)
                            same(expect, ms, mo, f'Quality {old} -> {c} (link {link}, codec in use {show}, confirm {yes}, judge {judge}, status {save}, connect {conn})')
                            changed = mo.state()[2] == c and c != old
                            expect(r == (1 if changed else 0), f'Quality {old} -> {c}: answers {r} for a change {changed}')
                            n += 1
    expect(n == 1728, f'{n} choices compared with stock')
    mo.reset(flag=1, coding=3, link=1, show=3, confirm=True, headset=2); mo.judge = 0; ours(mo, 'bs_codec_set', 0)
    names = [(e[0], e[1] if e[0] == 'confirm' else None) for e in mo.log]
    expect(names == [('confirm', 'Reconnect Bluetooth?'), ('save_stop_player', None), ('judge_outputdevice', None), ('mclGetSavePlayStatus', None), ('set_outputchannel', None), ('switchBtPriority', None),
                     ('write_int_config', None), ('bluetoothLink', None)], f'the connected change: {names}')
    expect(mo.log[0][2] == 1 and mo.log[-1][1] == 2 and mo.log[-3][1] == 0 and mo.log[-2][1:4] == (0, 'SYSSET', 'BTCODING') and mo.state()[6:8] == (0, 0) and mo.state()[10:13] == (0, -1, 0) and mo.state()[14] == 1,
           f'kind 1, bluetoothLink(2), priority 0, the five words cleared (link, codec, role, volume -1, event 0), the refresh flag set ({mo.state()})')
    mo.reset(flag=1, coding=3, link=1, show=3, confirm=True); r = ours(mo, 'bs_codec_set', 9)
    expect(r == 0 and not mo.log and mo.state()[2] == 3, 'a codec stock has no row for: refused, nothing called')
    r = ours(mo, 'bs_codec_set', -1 & 0xffffffff)
    expect(r == 0 and not mo.log, 'a negative one too')
    for v, want in ((0, 0), (7, 7), (8, 0), (255, 0), (-1, 0), (-1 & 0xffffffff, 0)):
        mo.reset(coding=v if v >= 0 else v)
        expect(mo.call(PSYMS['bs_codec']) == want, f'btcoding {v}: bs_codec {want} (config_init: 8 and up become 0)')
    for i, key in enumerate(CODEC_KEYS):
        mo.reset(); p = mo.call(PSYMS['bs_codec_key'], a0=i)
        expect(p and mo.read_cstr(p) == key, f'codec {i}: stock\'s key {key}')
    for i in (8, 9, -1 & 0xffffffff):
        mo.reset(); expect(mo.call(PSYMS['bs_codec_key'], a0=i) == 0, f'codec {i}: no key')
    expect(all(mo.read_cstr(mo.word(0x97ca08 + 4 * i)) == CODEC_KEYS[i] for i in range(8)), 'the table the keys come from is stock\'s (pinned)')


def volume_tests(ctx):
    """bs_volume_ok against what stock's adjustA2dpVolume does with the same state (run for real, libbtctl mocked); bs_volume calls it."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    ms.handlers.pop(0x4d28ac)   # stock's own, run for real
    for flag in (0, 1):
        for link in (0, 1):
            for show in (0, 3, -1):
                for recv in (0, 2):
                    for up in (0, 1):
                        for vol in (0, 5, 60, 118, 127, 128, 200):
                            ms.reset(flag=flag, link=link, show=show, recv=recv); ms.volume = vol
                            r = ms.call(0x4d28ac, a0=up, count=500000)
                            acted = [e for e in ms.log if e[0] == 'set_volume']
                            mo.reset(flag=flag, link=link, show=show, recv=recv); ok = mo.call(PSYMS['bs_volume_ok'], count=200000)
                            reads = vol < 128 and ok
                            want = [max(0, vol - 10) if not up else min(127, vol + 10)] if reads else []
                            expect(r == 1 and [e[1] for e in acted] == want, f'stock (flag {flag}, link {link}, codec {show}, receiver {recv}, up {up}, reading {vol}): answers {r}, sets {acted}')
                            expect(bool(ok) == (len([e for e in ms.log if e[0] == 'get_volume']) == 1), f'bs_volume_ok {ok} is whether stock reads the volume (flag {flag}, link {link}, codec {show}, receiver {recv})')
                            mo.reset(flag=flag, link=link, show=show, recv=recv); a = ours(mo, 'bs_volume', up)
                            expect(a == int(bool(ok)) and [e[:2] for e in mo.log] == [('adjustA2dpVolume', up)], f'bs_volume({up}) calls adjustA2dpVolume({up}) once and answers {a}')


DEV = 290   # sizeof(struct bs_dev): mac[32], name[256], paired, state


def read_dev(m, buf, i):
    a = buf + i * DEV
    return m.read_cstr(a), m.read_cstr(a + 32), m.b(a + 288), m.b(a + 289)


def list_tests(ctx):
    """bs_devices against stock's btdevice_listitem_layout 0x4a33c8 (its helpers recorded): the four row cases, every link list shape."""
    expect = ctx.expect
    ms, mo = pair_of(ctx)
    paired = [(mac(1), 'Alpha'), (mac(2), 'Beta \xc3\x9c')]
    others = [(mac(3), 'Gamma'), (mac(4), 'Delta')]
    P, C = 5, 6 + len(paired)
    shows = [mc for mc, _ in paired + others]
    n = 0
    for linked, conn, show in (([], 0, 0), ([(1, mac(1))], 1, 0), ([(1, mac(1))], 0, 0), ([(3, mac(1))], 0, 3), ([(3, mac(1))], 0, 0), ([(3, mac(1))], 0, 13), ([(3, mac(1))], 0, 5), ([(3, mac(1))], 0, 4),
                               ([(4, mac(1))], 0, 3), ([(5, mac(2))], 0, 2), ([(3, mac(3))], 0, 2), ([(1, mac(4))], 1, 0), ([(3, mac(9)), (3, mac(2))], 0, 1), ([(3, mac(2)), (1, mac(9))], 1, 1), ([(3, mac(4))], 0, 14)):
        for who in range(4):
            for m in (ms, mo): m.reset(flag=1, conn=conn, show=show); m.set_lists(paired, others); m.linked = linked
            row = 6 + who if who < 2 else C + 1 + (who - 2)
            ms.call(LAYOUT, a0=ms.alloc(0x40), a1=row, a2=P, a3=C, count=2000000)
            lay = [e for e in ms.log if e[0] in ('lay_name', 'lay_sub', 'lay_del')]
            name = (paired + others)[who][1].encode().decode('latin-1')   # (read_cstr shows UTF-8 bytes as latin-1 characters)
            expect(lay[0][:2] == ('lay_name', name), f'the row {row} is {shows[who]}: stock names it {lay[0][1]}')
            sub = [e[1] for e in lay if e[0] == 'lay_sub']
            buf = mo.alloc(8 * DEV)
            k = mo.call(PSYMS['bs_devices'], a0=buf, a1=8, count=5000000)
            got = read_dev(mo, buf, who)
            expect(k == 4 and got[0] == shows[who] and got[1] == name, f'{shows[who]}: {k} devices, its MAC and name {got[:2]}')
            is_paired = shows[who] in mo.paired
            key = {1: 'msg_connecting', 2: 'msg_connected'}.get(got[3]) or ('msg_paired' if is_paired else None)
            expect(got[2] == int(is_paired) and (sub[0] if sub else None) == key and len(sub) == int(key is not None),
                   f'{shows[who]} (links {linked}, connect {conn}, codec {show}): stock says {sub}, ours state {got[3]} paired {got[2]}')
            expect(any(e[0] == 'lay_del' for e in lay) == (is_paired or got[3] == 2), f'the forget icon is on the paired rows and on a connected one, whatever checkPairDev says ({shows[who]}, {[e[0] for e in lay]})')
            n += 1
    expect(n == 60, f'{n} rows compared with stock')
    # the cap, an empty and a missing list, a long name
    for m in (mo,): m.reset(flag=1); m.set_lists(paired, others)
    buf = mo.alloc(8 * DEV)
    expect(mo.call(PSYMS['bs_devices'], a0=buf, a1=3, count=5000000) == 3 and mo.call(PSYMS['bs_devices'], a0=buf, a1=0, count=5000000) == 0, 'at most max devices are written')
    mo.reset(flag=1); mo.setword(D['BT_SHOWLIST'], 0)
    expect(mo.call(PSYMS['bs_devices'], a0=buf, a1=8, count=5000000) == 0, 'no list: no device')
    mo.reset(flag=1); mo.set_lists([], [(mac(1), 'x' * 255)])
    expect(mo.call(PSYMS['bs_devices'], a0=buf, a1=8, count=5000000) == 1 and read_dev(mo, buf, 0)[1] == 'x' * 255, 'a name of 255 bytes is copied whole')
    mo.reset(flag=1); mo.u.mem_write(D['BT_LOCALNAME'], b'My Player\0')
    expect(mo.read_cstr(mo.call(PSYMS['bs_name'])) == 'My Player', 'bs_name is stock\'s localBtName')


SECTIONS = [switch_tests, scan_tests, link_tests, forget_tests, codec_tests, volume_tests, list_tests]
