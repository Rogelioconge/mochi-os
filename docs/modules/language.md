# Language

Settings > General > Language is our own picker (`m1plus_language`, `LANGUAGE_PAGE`, `patch/language.c`) for stock's UI language. Like
[Buttons & Power](keyspower.md) it is a value row (the loaded language's own name, grey) opening one card of check rows; the state is stock's
own word, nothing of ours is saved, no row opens a stock page. Stock's `systemset/language_page` stays under All System Settings and
shows the same word. All addresses are `demo` virtual addresses (`work/cache/demo.dis`). Not run on a device; the emulator tests run stock's
own row handler (`test/pod/language.py`).

## Stock state and handlers

| What | Where |
|---|---|
| The language word | int `language` `0xa05ab8` (dynsym). 0 .. 12 = the rows of stock's page: simplified, traditional, English, Japanese, Korean, French, German, Spanish, Italian, Thai, Polish, Russian, Ukrainian. `config_init` loads it as `atoi` of `[SYSSET] LANGUAGE` with no clamp (`0x4e6528..0x4e6534`); a missing key also sets the first-run byte `0xa05a59` (the guide page) |
| The row keys | the 13 pointers at `0x97c880` -> `lan_simplified`, `lan_traditional`, `lan_english`, `lan_japanese`, `lan_korean`, `lan_french`, `lan_german`, `lan_spanish`, `lan_italian`, `lan_thai`, `lan_polish`, `lan_russian`, `lan_ukrainian`. Every stock table holds the same value for each: the language's own name (`简体中文`, `繁體中文`, `English`, `日本語`, `한국어`, `Français`, `Deutsch`, `español`, `Italiano`, `ภาษาไทย`, `Polski`, `Русский`, `Українська`) |
| The page | `systemset_language_page_init` `0x4a80b0`: destroys the children of `language_scrollview`, then for 13 rows creates a `list_item`, lays it out with `language_listitem_layout` `0x4a7e60` (hscroll label with the key, an `image_choice<N>` image `selected` for the row whose number equals the word, else `unselect`; the item is named `<N>`) and binds the click (`0x10c`) to `0x4a7cb0`. The title is `system_language` |
| The locale | `switch_language(word)` `0x4cca40`: `word - 1 < 12` indexes a jump table (`0x749d70`: 1 zh_HK, 2 en_US, 3 ja_JP, 4 ko_KR, 5 fr_FR, 6 ge_DE, 7 sp_ES, 8 it_IT, 9 th_TH, 10 po_PL, 11 ru_RU, 12 uk_UK), anything else (0, 13+, negative) loads `zh_CN`; then `set_jplanguage` |

**The row handler `0x4a7cb0`** (ctx = the clicked item; `atoi` of its name is the row), in order:

1. `widget_get_window`, `atoi(name)`; if the row equals the word (`beq` at `0x4a7d04`) nothing else happens.
2. `image_choice<old>` = `unselect`, `image_choice<new>` = `selected` (widgets of stock's page only).
3. `language = row` (`sw` `0x4a7dfc`), then `write_int_config(row, "SYSSET", "LANGUAGE")`.
4. `switch_language(language)`. This runs `locale_info_change`; the window manager re-translates every open window (`tr_text` widgets) and
   our CJK font forms follow `EVT_LOCALE_CHANGED` ([fonts](fonts.md), [i18n](i18n.md)).
5. `change_lanflag` byte `0xa05a39` = 1, `homemenu_changeflag` int `0xa05a50` = 2 (stored in the delay slot before the call).
6. `navigator_back_to_home()` `0x4d20a0` = `window_manager_back_to_home` (tail call, `0x678030`): every window above Home is closed.

Nothing else (no config write besides `LANGUAGE`, no font call, no restart). The two flags are read by the Home screen's refresh
helper `0x534858` (called from the Home foreground handler `0x534b88` at `0x534c44`, and from `0x534998`): with `change_lanflag` set it calls
`reset_homemenu_index(1)`, stores `homemenu_changeflag` = 2 and clears the byte, then, for 2, rebuilds the main menu (`0x534064`) so the
stock Home grid's texts are the new language's, and clears `homemenu_changeflag`. Other users of `change_lanflag`: a reader at `0x4d81cc`
(inside `reset_homemenu_index` `0x4d8114`, which `0x5348a0` calls) and a writer, the first-run guide page's language choice (`0x53361c..0x533648`:
`switch_language`, then the byte = 1).

## What ours does

`lang_set(v)` (`patch/language.c`) repeats steps 1, 3, 4, 5 and 6 and nothing else (stock's widget changes of step 2 belong to its page,
which is not open). The calls and the state words at each call are pinned (`LANGUAGE_PINS`: handler, `switch_language`'s range, the Home
helper's reads, `config_init`'s load, the key table) and compared with stock's own handler under the emulator.
`lang_get` is the word when it is 0 .. 12, else 0 (the language `switch_language` loads).

**Windows after a change.** Stock's handler ends on Home, so there is nothing of ours to refresh: Settings and the picker are closed by
`navigator_back_to_home`, and every window still on the stack when `switch_language` runs is translated by the window manager first. The
texts of our pages are tr keys (`pod_i18n.text_prop`) or are set again each time they are shown (`widget_set_text_utf8` composed
texts), so the next time any of our pages opens it is in the new language, as after a change on stock's page. The picker's own
`page_refresh` after a choice (`pick_choose`) only touches a window that is still there. On opening and on every return to the front
(`EVT_WINDOW_TO_FG`, `page_refresh`) the Language row and the picker re-read the word, so a change made on stock's page shows (the word is
the only state). Choosing the language that is loaded does nothing (stock's compare) and the picker stays.

## Page and labels

Settings > General, the row after Keyboards (the General page lists About, Date & Time, Keyboards, Language, then the stock pages' direct rows): `Row('Language', ACT_LANG, LANGUAGE_PAGE_INDEX)` (`ACT_LANG` 150, glyph `languages`,
`VK_LANG` value: `lang_key(lang_get())` set with `widget_set_tr_text`). The picker `m1plus_language` has 13 check rows (`ACT_LANGSET` 151,
arg = stock's word, `pick_tab` entry `lang_get` / `lang_set`). Texts are stock keys, nothing of ours: the row and the title are
`system_language` (translated by stock in all 13 tables: `STOCK` in `tools/pod_i18n.py`), the picker rows `lan_*` through
`pod_pages.StockText` (a `str` that carries its key, because `English` is also a key of our own for the Keyboards page and
`pod_i18n.key_for` would otherwise pick that one, which translates). The list reads the same in every UI language, as stock's does.
`test/pod/i18n.py` measures the row (label + the widest name) in the shipped font in all 13 languages.

## Tests

`test/pod/language.py`: `get_tests` (getter clamps, keys against stock's table in memory, pins), `set_tests` (stock's handler run for real
on the same state vs ours: 4 starting words x 13 rows, plus out-of-range words and refused rows: the same final state, calls in order and
state at each call), `settings_tests` (the Settings row's place, the picker's rows, checks per word, the tap's calls, the value text per
word and after a change by stock's page, the assets, stock keys in all 13 tables).

## Not verified

- Anything on a device: that closing every window above Home from our picker (a stock call made from our window, the way stock calls it
  from its own) lands cleanly on our Home, that the Home menu rebuild shows the new language there, and that fonts follow.
- That our window is destroyed synchronously by the close; if it is not, `pick_choose`'s refresh runs on a window that is about to
  go (harmless: check images only).
- `0x534b88` / `0x534998` event numbers and the full rebuild at `0x534064` were read as far as the flags above.
