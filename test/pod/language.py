"""Settings > General > Language (patch/language.c, docs/modules/language.md): our row and picker for stock's language word. The state is stock's own and is changed the way stock's
language page changes it, which the tests check by running stock's row handler (0x4a7cb0) under the emulator on the same state and comparing the final state and the calls, in order, with ours."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_strings
import awtk_ui
import paths

WORD, CHANGED, HOMEMENU = (pod.DATA[n][0] for n in ('LANGUAGE_WORD', 'LANGUAGE_CHANGED', 'HOMEMENU_CHANGED'))
ROW_HANDLER = 0x4a7cb0   # stock's systemset/language_page row click handler (the row item in a0; its name is the row's number)
KEY_TABLE = 0x97c880     # its 13 tr keys, the order of the rows
WIN = 0x30000000
RAW = 'rootfs/release/assets/default/raw'
LEAVES = {0x742da0: 'memset', 0x70f8d8: 'tk_snprintf', 0x7435b0: 'atoi'}   # (the PLT stubs stock's code calls through)
TRACED = ('write_int_config', 'switch_language', 'navigator_back_to_home')


class LM(Machine):
    """Stock's row handler runs for real, with the leaves above mocked. The saves, the locale switch and the navigation record the state words as they are at that moment: the order of the stores and the calls."""
    def __init__(self, word=0, changed=0, homemenu=0):
        super().__init__()
        for a, n in LEAVES.items(): self.handlers[a] = n
        self.snap = []
        self.setword(WORD, word & 0xffffffff); self.u.mem_write(CHANGED, bytes([changed])); self.setword(HOMEMENU, homemenu)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name in TRACED: self.snap.append(self.state())
        if name in ('switch_language', 'navigator_back_to_home'):
            a0 = u.reg_read(UC_MIPS_REG_A0)
            self.calls.append(('switch_language', a0) if name == 'switch_language' else ('navigator_back_to_home',))
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA)); return
        if name != 'tk_snprintf': return super()._hook(u, address, size, _)
        a0, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        text = self.read_cstr(a2) % a3
        u.mem_write(a0, text.encode() + b'\0')
        u.reg_write(UC_MIPS_REG_V0, len(text)); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def byte(self, a): return self.u.mem_read(a, 1)[0]
    def state(self): return (self.word(WORD), self.byte(CHANGED), self.word(HOMEMENU))


def traced(m):
    """What reaches stock's state and the window system, in order."""
    return [c[:4] for c in m.calls if c[0] in TRACED]


def stock_click(word, row):
    """Stock's row handler, with the click on the row whose item is named `row` (its page's widgets: every image_choiceN and the window)."""
    m = LM(word=word)
    m.page_window = WIN
    for i in range(13): m.widget(f'image_choice{i}')
    node = m.alloc(0x40); m.setword(node + 0x10, m.cstr(str(row)))
    m.call(ROW_HANDLER, a0=node, count=3000000)
    return m


def get_tests(ctx):
    """lang_get, lang_key and the key table: stock's word and its page's rows."""
    expect = ctx.expect
    expect(pod.DATA['LANGUAGE_WORD'] == (0xa05ab8, 'language') and pod.DATA['LANGUAGE_CHANGED'] == (0xa05a39, 'change_lanflag') and pod.DATA['HOMEMENU_CHANGED'] == (0xa05a50, 'homemenu_changeflag')
           and pod.FUNCTIONS['switch_language'][2] == 0x4cca40 and pod.FUNCTIONS['navigator_back_to_home'][2] == 0x4d20a0, 'the word, the two flags and the two calls are stock\'s (checked against demo\'s dynsym by the build)')
    pins = {a: w for a, w, _ in pod.LANGUAGE_PINS}
    expect(all(a in pins for a in (0x4a7d04, 0x4a7dfc, 0x4a7e00, 0x4a7e10, 0x4a7e28, 0x4a7e34, 0x4a7e38, 0x4cca5c, 0x4cca64, 0x4d20d4, 0x534888, 0x5348ac, 0x5348b0, 0x4e6534, 0x97c880, 0x97c8b0)),
           'the handler\'s compare, store, save, locale switch, flags and navigation, switch_language\'s range, the Home callback\'s reads and config_init\'s load are pinned')
    for w in range(13): expect(LM(word=w).call(PSYMS['lang_get'], count=200000) == w, f'the word {w}: the row {w} is checked')
    for w in (-1, 13, 14, 99, 0x7fffffff): expect(LM(word=w).call(PSYMS['lang_get'], count=200000) == 0, f'the word {w}: switch_language loads zh_CN for it, so row 0')
    # the keys are the ones stock's page puts on its rows, in its order
    m = LM(); keys = []
    for i in range(13):
        m.call(PSYMS['lang_key'], a0=i, count=200000); r = m.u.reg_read(UC_MIPS_REG_V0); keys.append(m.read_cstr(r))
        expect(keys[-1] == m.read_cstr(m.word(KEY_TABLE + 4 * i)), f'row {i}: the key is stock\'s ({keys[-1]})')
    expect(tuple(keys) == pod_pages.LANGUAGE_KEYS, 'the payload\'s keys are the page\'s')
    m.call(PSYMS['lang_key'], a0=99, count=200000)
    expect(m.read_cstr(m.u.reg_read(UC_MIPS_REG_V0)) == 'lan_simplified', 'a word out of range names row 0')


def set_tests(ctx):
    """lang_set against stock's row handler, run for real on the same state."""
    expect = ctx.expect
    for cur in (0, 2, 3, 12):
        for new in range(13):
            ms = stock_click(cur, new)
            mo = LM(word=cur); r = mo.call(PSYMS['lang_set'], a0=new, count=2000000)
            expect(r == 0, f'{cur} -> {new}: answers 0')
            expect(mo.state() == ms.state() and traced(mo) == traced(ms) and mo.snap == ms.snap,
                   f'{cur} -> {new}: state {mo.state()} / {ms.state()}, calls {traced(mo)} / {traced(ms)}, at each call {mo.snap} / {ms.snap}')
            if new != cur:
                S = 'SYSSET'
                expect(traced(mo) == [('write_int_config', new, S, 'LANGUAGE'), ('switch_language', new), ('navigator_back_to_home',)] and mo.state() == (new, 1, 2)
                       and mo.snap == [(new, 0, 0), (new, 0, 0), (new, 1, 2)],
                       f'{cur} -> {new}: the word stored, saved, the locale switched with it, the two flags, then Home ({traced(mo)}, {mo.snap})')
            else:
                expect(not traced(mo) and mo.state() == (cur, 0, 0), f'{cur} -> {cur}: the same language does nothing')
    # a word stock\'s own config can hold out of range: the handler compares the raw word, so any row is a change
    for cur in (-1, 13, 99):
        ms = stock_click(cur, 5); mo = LM(word=cur); mo.call(PSYMS['lang_set'], a0=5, count=2000000)
        expect(mo.state() == ms.state() == (5, 1, 2) and traced(mo) == traced(ms) and mo.snap == ms.snap, f'the word {cur} -> 5 is a change, as stock')
    for bad in (-1, 13, 99):
        m = LM(word=2)
        expect(m.call(PSYMS['lang_set'], a0=bad & 0xffffffff, count=200000) == 0xffffffff and m.state() == (2, 0, 0) and not traced(m), f'row {bad}: refused, nothing written')


def settings_tests(ctx):
    """The Settings row, the picker, the value text, the refresh on return, the translations and the assets."""
    expect, P = ctx.expect, pod_pages
    import pod_i18n
    import mod_icons
    V, L = P.GENERAL_PAGE, P.LANGUAGE_PAGE
    labels = [r.label for r in V.rows]
    li = labels.index('Language')
    expect(V.rows[li].action == P.ACT_LANG and V.rows[li].arg == P.LANGUAGE_PAGE_INDEX and P.PAGES[P.LANGUAGE_PAGE_INDEX] is L and P.row_kind(V.rows[li]) == 'value'
           and labels[li - 1] == 'Keyboards' and labels[li + 1:] == [] and (L.key, L.title) == ('m1plus_language', 'Language') and V.layout.index(V.rows[li]) == V.layout.index(V.rows[li - 1]) + 1,
           'Settings > General > Language: a value row after Keyboards, opening our picker')
    expect([(str(r.label), r.action, r.arg) for r in L.rows] == [(n, P.ACT_LANGSET, i) for i, n in enumerate(P.LANGUAGE_NAMES)] and all(P.row_kind(r) == 'check' for r in L.rows) and len(L.rows) == 13
           and not any(not isinstance(x, P.Row) for x in L.layout) and (P.ACT_LANG, P.ACT_LANGSET) == (150, 151) and P.ACT_LANG in P.VALUE_ACTIONS and P.ACT_LANGSET in P.CHECK_ACTIONS and P.VALUE_INIT[P.ACT_LANG] == '',
           'the picker: one card of 13 check rows by stock\'s word, the actions 150 and 151')
    expect(not any(r.action == P.ACT_STOCK for r in L.rows) and not any(n.split('/')[-1] == 'language_page' for n, *_ in P.STOCK_PAGES), 'no row opens a stock page')
    # the names are stock's own text, the same in every table; the keys are the page's and the English is not our own "English"
    stock_dir = os.path.join(paths.find_stock(paths.ZIP), RAW, 'strings')
    tables = {f[:-4]: dict(awtk_strings.load(os.path.join(stock_dir, f))) for f in sorted(os.listdir(stock_dir))}
    expect(all(tables[t][k] == n for t in pod_i18n.LOCALES for k, n in zip(P.LANGUAGE_KEYS, P.LANGUAGE_NAMES)), 'lan_* hold each language\'s own name in the 13 tables the language menu reaches')
    expect([pod_i18n.key_for(r.label) for r in L.rows] == list(P.LANGUAGE_KEYS) and pod_i18n.key_for('English') == 'English' and pod_i18n.text_prop(L.rows[2].label) == ('tr_text', 'lan_english')
           and all(pod_i18n.STOCK[k] == n for k, n in zip(P.LANGUAGE_KEYS, P.LANGUAGE_NAMES)), 'the rows use stock\'s keys (English too: Keyboards\' own English key stays another text)')
    expect(pod_i18n.key_for('Language') == 'system_language' and pod_i18n.STOCK['system_language'] == 'Language' and tables['zh_CN']['system_language'] and tables['uk_UK']['system_language'],
           'the Settings row and the picker\'s title are stock\'s system_language, translated in every table')
    expect(mod_icons.CARD_GLYPHS['Language'] == 'languages', 'the glyph')
    stock_rows = pod_pages.STOCK_PAGES
    expect(all(not n.endswith('language_page') for n, *_ in stock_rows), 'stock\'s Language page is only under All System Settings')

    def page(index, nrows, kinds=('pod_check', 'pod_label'), **state):
        m = LM(**state)
        m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(['btn_return', 'btn_backtoplayer'] + [f'{k}{i}' for k in ('pod_row',) + tuple(kinds) for i in range(nrows)])}
        row = m.alloc(12)
        m.setword(row, m.cstr('pod_row0')); m.setword(row + 4, P.ACT_PAGE); m.setword(row + 8, index)
        m.call(PSYMS['on_row'], a0=row, count=6000000)
        return m

    def checks(m, n):
        out = []
        for i in range(n):
            v = [c[2] for c in m.calls if c[0] == 'widget_set_visible' and c[1] == m.widgets[f'pod_check{i}']]
            out.append(v[-1] if v else None)
        return out
    for w in range(13):
        m = page(P.LANGUAGE_PAGE_INDEX, 13, word=w)
        expect(('window_open', L.key) in m.calls and checks(m, 13) == [int(i == w) for i in range(13)] and not traced(m), f'the word {w}: the picker checks row {w} and writes nothing')
    # a tap: stock's handler's changes, then Home; the picker's own refresh is the page's (it is closed by the navigation)
    m = page(P.LANGUAGE_PAGE_INDEX, 13, word=2)
    m.calls = []; m.snap = []; m.click('pod_row5')
    expect(m.state() == (5, 1, 2) and traced(m) == [('write_int_config', 5, 'SYSSET', 'LANGUAGE'), ('switch_language', 5), ('navigator_back_to_home',)] and 'navigator_to' not in m.names() and 'navigator_back' not in m.names()
           and [c for c in m.calls if c[0] == 'window_open'] == [], f'a tap on Français: stock\'s changes, then Home, nothing else opened ({traced(m)})')
    m.calls = []; m.snap = []; m.click('pod_row5')
    expect(not traced(m), 'a tap on the language that is loaded does nothing')
    # the Settings row: the loaded language's own name, read as the page opens and each time it is back in front
    SV = ('pod_value', 'pod_label')

    def value(m, i): return [c[2] for c in m.calls if c[0] == 'widget_set_tr_text' and c[1] == m.widgets[f'pod_value{i}']]
    nrows = len(V.rows)
    for w in range(13):
        m = LM(word=w)
        m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(['btn_return', 'btn_backtoplayer'] + [f'{k}{i}' for k in ('pod_row',) + SV for i in range(nrows)])}
        row = m.alloc(12); m.setword(row, m.cstr(f'pod_row{li}')); m.setword(row + 4, P.ACT_PAGE); m.setword(row + 8, P.GENERAL_PAGE_INDEX)
        m.call(PSYMS['on_row'], a0=row, count=8000000)
        expect(value(m, li) == [P.LANGUAGE_KEYS[w]] and not traced(m), f'the word {w}: the Language row shows {P.LANGUAGE_KEYS[w]}')
        m.u.mem_write(WORD, (4 if w != 4 else 5).to_bytes(4, 'little')); m.calls = []; m.fire(O['EVT_WINDOW_TO_FG'])
        expect(value(m, li) == [P.LANGUAGE_KEYS[4 if w != 4 else 5]] and not traced(m), f'back in front after stock\'s page changed the word: the row follows (from {w})')
    # the assets
    raw = os.path.join(WORK, RAW, 'ui')
    se = awtk_ui.parse(open(os.path.join(raw, 'm1plus_general.bin'), 'rb').read())
    lt = awtk_ui.parse(open(os.path.join(raw, 'm1plus_language.bin'), 'rb').read())
    expect(se.find(f'pod_row{li}').find('pod_icon').get('image') == 'pod_ci_languages' and se.find(f'pod_label{li}').get('tr_text') == 'system_language' and se.find(f'pod_value{li}') is not None,
           'the General page row: the glyph, stock\'s label, a value')
    expect(lt.find('label_title').get('tr_text') == 'system_language' and [lt.find(f'pod_label{i}').get('tr_text') for i in range(13)] == list(P.LANGUAGE_KEYS)
           and all(lt.find(f'pod_check{i}').get('visible') == 'false' and lt.find(f'pod_check{i}').get('sensitive') == 'false' for i in range(13)), 'the picker asset: stock\'s title and keys, a hidden insensitive check per row')


SECTIONS = [get_tests, set_tests, settings_tests]
