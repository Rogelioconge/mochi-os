# Language

**Sources:** `patch/language.c`, `LANGUAGE_PAGE` in `tools/pod_pages.py`, `LANGUAGE_PINS`.
Settings > General > Language is our own picker (`m1plus_language`) for stock's UI language. Like
[Buttons & Power](keyspower.md) it is a value row (the loaded language's own name, grey) opening
one card of check rows. The state is stock's own word, nothing of ours is saved, and no row opens a
stock page. Stock's `systemset/language_page` stays under All System Settings and shows the same
word. The emulator tests run stock's own row handler on the same state.

## Stock behaviour we rely on

- **The word:** int `language`, 0..12 = simplified, traditional, English, Japanese, Korean, French,
  German, Spanish, Italian, Thai, Polish, Russian, Ukrainian. `config_init` loads it from
  `[SYSSET] LANGUAGE` with no clamp; a missing key also sets the first-run flag (the guide page).
- **The row keys** `lan_*` hold each language's own name in every stock table, so the list reads
  the same in every UI language.
- **The locale:** `switch_language(word)` loads the locale for 1..12; anything else (0, 13+,
  negative) loads `zh_CN`.
- **The row handler**, in order: if the row is the current word, nothing; mark the choice images
  (stock's page only); store the word and `write_int_config(row, "SYSSET", "LANGUAGE")`;
  `switch_language`, which re-translates every open window (our CJK font forms follow
  `EVT_LOCALE_CHANGED`, see [fonts](fonts.md) and [i18n](i18n.md)); set `change_lanflag` = 1 and
  `homemenu_changeflag` = 2; `navigator_back_to_home()`, which closes every window above Home.
- The Home refresh helper reads the two flags and rebuilds the main menu, so stock's Home grid
  shows the new language. Nothing else happens: no other config write, font call or restart.

## What ours does

`lang_set(v)` repeats stock's store, save, `switch_language`, the two flags and the return to Home,
and nothing else (the image changes belong to stock's page, which is not open). The calls and the
state words at each call are pinned (`LANGUAGE_PINS`) and compared with stock's handler under the
emulator. `lang_get` is the word when it is 0..12, else 0 (the language `switch_language` loads).

- **Windows after a change:** the handler ends on Home, so Settings and the picker are closed and
  there is nothing of ours to refresh. Our pages' texts are tr keys or set again each time they are
  shown, so the next open is in the new language.
- The Language row and the picker re-read the word on opening and on every return to the front, so
  a change made on stock's page shows.
- Choosing the loaded language does nothing and the picker stays.

## Page and labels

Settings > General, the row after Keyboards: `Row('Language', ACT_LANG, LANGUAGE_PAGE_INDEX)`
(glyph `languages`; value `lang_key(lang_get())` via `widget_set_tr_text`). The picker has 13 check
rows (`ACT_LANGSET`, arg = stock's word).

Texts are stock keys, nothing of ours: the row and title are `system_language` (translated by stock
in all 13 tables), the picker rows `lan_*` through `pod_pages.StockText`, a `str` that carries its
key, because `English` is also a key of our own for the Keyboards page and `key_for` would
otherwise pick that one. `test/pod/i18n.py` measures the row in the shipped font in all 13
languages.
