# Keyboard

**Sources:** `patch/keyboard.c`, `patch/keyboard.h` (API and geometry constants); the asset is
`build_keyboard_page` in `tools/pod_ui.py` (`ui/m1plus_keyboard.bin`), geometry in
`tools/pod_keyboard.py`, glyphs `KEYBOARD_IMAGES` (`qk_*`) in `tools/mod_icons.py`.
**Tests:** `test/pod/keyboard.py`, `test/pod/pinyin.py` (the engine on its own).
**Preview:** `tools/preview/preview_keyboard.py`.

Our own on-screen keyboard, built from stock AWTK widgets. It replaces stock's T9 popup
(`ui/user_keyboard.bin`, laid out 640 px wide in a 320 px popup) wherever we use it, and types
Chinese when Settings > General > Keyboards > Chinese (Pinyin) is on. No hook, no new import, no
thread; one timer only while the delete key is held.

## Layout

A page of stock widgets: the plain navbar (Back = cancel, Now Playing), a search field and a 180 px
pad at the bottom of the 450 px window, `#1C1C1E`. White and grey only, no accent.

- **Pad:** four rows at a 44 px pitch, keys 36 px high. Char keys 29 px wide with 3 px gaps, ten
  across; rows of nine and seven are centred. Third row: shift (40) left, delete (40) right. Bottom
  row: 123 / ABC (74), space (163), Search (74). Char keys `#4A4A4E`, function keys `#2E2E32`, rounded
  5 px, letters 20 px. 26 char key widgets (`kb_k0`..`kb_k25`) are moved, relabelled and hidden per
  page; function keys are `kb_shift`, `kb_shifton`, `kb_sym`, `kb_del`, `kb_mode`, `kb_space`,
  `kb_go`, `kb_lang`.
- **Pages:** lowercase, uppercase, **123** (digits, `- / : ; ( ) $ & @ "`, `. , ? ! '`) and **#+=**
  (`[ ] { } # % ^ * + =`, `_ \ | ~ < > € £ ¥ \``). Every printable ASCII character is typeable.
- **Shift** is one-shot: an empty field starts on capitals, the first letter returns to lowercase, an
  emptied field turns it on again. No caps lock. ABC from a symbol page returns to capitals for an
  empty field, lowercase otherwise. Space is ignored at the start and after a space
  (except in a password field or with `KB_LITERAL`).
- **Pop-up:** while a char key is down, `kb_stem` and `kb_pop` (46x50, `#6E6E73`) show the letter.
  Both are window children after the pad (it would clip them) and insensitive for life; only
  visibility changes. A key types when the finger lifts on it.
- **Delete** acts on touch down and repeats while held (80 ms ticks, first repeat after six). Its
  timer exists only between down and up, abort or background.
- **Field** (`kb_field`, 300x36 at (10, 58), radius 10) has a magnifier, a grey placeholder, the
  text (18 px white), a 2x22 caret (not blinking) and a clear button (shown only with text). It
  must stay sensitive: stock's hit test skips an insensitive parent. The caret sits at the measured
  text width (`widget_measure_text`; 9 px a character if it cannot be measured). A text wider than
  228 px shows its end after an ellipsis; the whole text is kept and returned. At most 63 bytes;
  delete removes a whole UTF-8 character.

## The gap rule

A touch on the pad that hits no key goes to the nearest key, as on an iPhone, so every key's touch
area effectively fills the 3 px gaps, the 8 px gaps between rows and the pad margins. On the device,
6% of taps missed, all in the 1 to 4 px gaps.

- AWTK sends a touch between keys to the pad (`kb_pad` is sensitive; down, up and abort are bound).
  `kb_down` measures it against the rectangles of the keys present now (`kb_rects`), by squared
  distance to each rectangle (0 inside); the first nearest wins. `nearest_key` in
  `tools/pod_keyboard.py` is the same model.
- The resolved key is pressed at once (pop-up, pressed look; delete deletes and starts repeating) and
  clicked when the finger lifts. Abort, background or destroy lets go without typing.
- The key and the pad may both see the same touch: only the first sighting counts, a touch inside a
  key's rectangle is never resolved by the pad, and if the two models disagree at an edge pixel the
  key wins.

## Keyboards setting and the language key

Two switch rows in Settings > General > Keyboards: English (always on) and Chinese (Pinyin)
(`/mnt/data/m1plus/keyboard-pinyin`, default off; [settings](settings.md)).

- **Off:** exactly the keyboard above. No language key, space 163 px, the dictionary and engine
  never touched.
- **On:** row four is `123 / ABC` (74), the language key `kb_lang` (40), space (120), Search. The key
  is on every page and shows the layer a tap goes to (`中` on English, `EN` on Chinese; not
  translated). If `gpinyin.dat` is missing, or the engine will not open when the key is tapped, the
  key goes away and English stays.
- The layer the last keyboard ended on is remembered for the session (`kb_memo`); turning the setting
  off forgets it.

## Layers and the Chinese layer

A layer is a `struct kb_layer` of functions (`enter`, `leave`, `compose`, `backspace`, `flush`,
`pending`, `reset`, and the `tag` the key shows). English has none. The page tables, field, pop-up,
gap rule and delete repeat are shared, so another composer would plug in as a table entry.

The Chinese layer has the English pages with these differences: lowercase only and **no shift** (the
pinyin separator `'` takes its place), and punctuation on 123 / #+= stays ASCII. The engine opens
when the layer is first used and closes with the page (the megabyte is returned); an engine someone
else initialised is used as it is and left open.

- **Composing:** a letter appends to the pinyin string (at most 39 letters, lowercased; `'` only
  after a letter and not twice), then the engine searches. Nothing goes into the field while
  composing.
- **The strip** (`kb_strip`, 36 px high just above the pad, `#2A2A2C`; hidden when empty) shows the
  pinyin as the engine segments it (`kb_py`, 16 px), a divider, then the candidates view `kb_cands`.
  Candidates are a pool of 12 label widgets reused by position (20 px white, item width = text + 12
  px a side, 36 to 230). Up to 100 candidates are read, 12 at a time, more as the row scrolls near
  its end.
- **Touch on the strip:** a press highlights the item; a 6 px move scrolls the row (no coasting, no
  overscroll) and the lift takes nothing; a lift without a move takes the item.
- **Taking a candidate** puts its text in the field; `im_choose` fixes it and the rest of the pinyin
  stays, searched fresh (the engine's fixed prefix and context are dropped on purpose, so delete and
  the strip have one simple state). When the pinyin is used up the strip shows predictions.
- **Space** commits candidate 0 (the best for everything left) and shows predictions; letters the
  engine cannot read are committed as typed. **Search** with pinyin pending does the same, then
  searches, so Search never loses what was typed. Back with pinyin pending cancels. 123 / ABC /
  #+= and the language key flush first.
- **Delete** removes the last pinyin letter first (an empty pinyin hides the strip), then text. With
  predictions showing, the first delete hides them and deletes the last character. Clear drops the
  pinyin too.
- **Predictions** (`zh_predict`): after a commit the strip offers `get_predicts` for the last up to
  seven Chinese characters of the field. A tap appends the word and asks again; a letter, space, 123
  or the language key removes them.
- **Limits:** 63 bytes of text (a commit that does not fit puts in whole characters only), 12
  widgets, 100 candidates, 4 KB of candidate text, 39 letters.

## API

```c
int keyboard_open(const char *title, const char *placeholder, const char *initial,
                  kb_done_fn on_done, kb_cancel_fn on_cancel, unsigned flags);   /* patch/keyboard.h */
int keyboard_busy(void);
```

`title` and `placeholder` are UTF-8 and already translated; NULL keeps the page's title or no hint.
Search (action key) with a non-empty trimmed text calls `navigator_back()` then `on_done(text)`;
an empty text does nothing and the page stays. Back (navbar or hardware) calls `on_cancel()`
(hardware Back: from the destroy event). Callbacks run on the UI thread with the page closing: use
only what they are given. One keyboard at a time: `keyboard_open` returns -1 while a previous page
is not destroyed (also from a callback) or when the asset is not ours; `keyboard_busy()` tells
which. Callers need nothing for Chinese.

| Flag | Effect |
|---|---|
| `KB_LONG` (4) | text limit 255 bytes instead of 63 (a feed address) |
| `KB_DONE` (2) | the action key reads **Done** |
| `KB_PASSWORD` (8) | see below |
| `KB_LITERAL` | plain text, capital start, clear button, spaces typed as pressed |

### Embedded in another page

A page can host the pad on its own window so nothing opens or closes while the user types. The code
is shared: `keyboard_open` is `kb_init` (widgets by name, bindings, layers, first page) plus a page's
own window, title, Back and destroy handler. The asset side is `keyboard_pad_widgets()` in
`tools/pod_ui.py` (pad, strip, pop-up), byte for byte equal in the keyboard page and every host.

```c
int  keyboard_attach(void *win, const char *placeholder, int text_x, int text_w, int caret_y,
                     unsigned flags, kb_change_fn on_change, kb_go_fn on_go);
void keyboard_detach(void);          /* the page's destroy event */
void keyboard_show(int on);          /* pad and strip shown or hidden; held key and pop-up let go */
int  keyboard_shown(void);
void keyboard_set_mask(int on);      /* password field: one dot a character */
void keyboard_set_clear(const char *leave);  /* clear button leaves this text ("" = nothing), shown while
                                                the field differs from it; NULL = no button */
void keyboard_set_go(const char *key, int enabled);   /* action key label and whether it works */
void keyboard_go(void);              /* the action key as if pressed */
const char *keyboard_text(void);
int  keyboard_refocus(placeholder, text_w, flags, text, on_change, on_go);
```

- The pad starts shown. The host window holds `kb_pad`, `kb_strip`, `kb_stem`, `kb_pop` and a field (`kb_field`, `kb_mag`,
  `kb_hint`, `kb_text`, `kb_caret`, `kb_clear`) by those names; `text_x`, `text_w`, `caret_y` give
  the field's inner geometry there.
- `on_change(text)` runs at the end of every refresh, so also when a layer or page switch refreshes
  the field (the caller ignores a repeat). A candidate still being composed is not in it.
- The action key commits what is pending and calls `on_go`; no page closes and there is no cancel.
- `keyboard_open` and `keyboard_attach` refuse while either exists; `keyboard_detach` frees it.
- `keyboard_refocus` (-1 when no embedded keyboard exists) lets another field of the same page take the pad: widgets and bindings stay; the
  flags, text room, placeholder, text and callbacks are replaced; pending composition, held key and
  pop-up are dropped; layers and first page are chosen again. An open Chinese engine stays open.

### Password mode

`KB_PASSWORD` (Wi-Fi password, [wifi](wifi.md)): English only (no language key, no strip, no engine,
whatever the setting); the letter page starts lowercase and an emptied field never turns capitals on;
space is typed anywhere; the text is returned untrimmed; no clear button (the page has an eye); at
most `KB_PASS_MAX` 127 bytes. The field is masked by the keyboard (one `•` per character, caret
measured on what is shown), so the host renders nothing. `keyboard_set_go(key, 0)` dims the action
key and makes it insensitive; a touch the gap rule resolves to it does nothing.

### Consumers

| Consumer | Use |
|---|---|
| Library Search | embedded pad ([search](search.md)) |
| Radio > Search | embedded pad; `rp_on_go` fetches results ([radio](radio.md)) |
| Podcasts > Search | `keyboard_open` with `KB_LONG`, title `Apple Podcasts`, placeholder `Search Apple Podcasts`; the callbacks only record what happened, the page handles it when back in front ([podcasts](podcasts.md)) |
| Playlists > New playlist | `keyboard_open` with `KB_DONE`, no cancel callback; `pl_named` makes the playlist ([playlists](playlists.md)). Limit 63 bytes (stock's edit allowed 127) |
| Tidal > Search | pad embedded in the stock page: [tidalkb](tidalkb.md) |
| Wi-Fi Join Network / password | one attach with `KB_LITERAL` or `KB_PASSWORD`, two fields served in turn by `keyboard_refocus`; the Security picker over it needs no keyboard, so the pad stays attached ([wifi](wifi.md)) |

## Pinyin engine

Stock's Google Pinyin engine (AOSP PinyinIME) gives the keyboard Chinese input from the payload, with
the dictionary stock already ships. Pins: `PINYIN_PINS` in `tools/pod_pins.py`; entry points
`FUNCTIONS` in `tools/pod.py`; [addresses](addresses.md) "Pinyin engine". Test: `test/pod/pinyin.py`
(demo's own engine code under Unicorn).

- **The dictionary** `/release/assets/default/raw/data/gpinyin.dat` is stock's and nothing names it,
  so we open it in place (`im_open_decoder` takes any path, but both the system and the user path
  are required: a NULL one fails). `tools/mod_space.py` must never list it in `REMOVE`.
- **Engine lifetime:** the C entry points work over one global `MatrixSearch*`. We open it only while
  one of our keyboards is up on the Chinese layer and close it with the page (about 1 MB, opens in
  76 ms; searches take 0.1 to 2.5 ms).
- **Predictions** use `MatrixSearch::get_predicts` (a member call with the global as `this`; no C
  entry point).
- **Candidates** are UTF-16LE; the layer converts to UTF-8 (surrogates included). After `im_choose`,
  candidate 0 is the whole text so far.
- **Quality:** jianpin (`nh` -> 你好), a syllable plus initials, a whole sentence with no separators
  (`woxihuantingboke` -> 我喜欢听博客), a half-typed last syllable and `'` all work. **No fuzzy
  matching** (z/zh, n/l, an/ang are literal).
- **No learning:** with an unreadable user path there is no user dictionary; with a creatable path
  four picks change no order. So nothing is re-ranked and nothing is saved. A user-dictionary path
  that can be neither read nor created is tolerated.
- **Stock's own Chinese input stays dead.** After any stock keyboard has been shown the global holds
  a dead object (`inited_` 0); `zh_enter` closes it before opening ours. Stock's text-entry windows call its init at every open,
  which replaces whatever is at the global (and leaves a dead object), and it asks for
  `/usr/dict_pinyin.dat`, which the rootfs lacks. Shipping that file would wake it in Wi-Fi and
  playlist-name entry for 1 MB of rootfs: not done.

### Hanzi to pinyin

For the library search ("zjl" finds 周杰伦) the same dictionary gives each character's readings
(`DictList::get_splids_for_hanzi`, then `SpellingTrie::get_spelling_str`, lowered): 周杰伦 is
`zhou jie lun`, 行 has `hang heng xing`. **Never call `get_splids_for_hanzi` for a character without
the `get_lemma_id` check**: it dereferences its binary-search result and crashes (Latin and fullwidth
letters, a rare Ext A character, an unassigned code point). The engine must be open: the search page
holds it through `pinyin_hold` / `pinyin_release`, which also stops the Chinese layer closing it under
the page. Used by `se_read_hanzi` ([search](search.md)).

## Limits

- No caps lock, no number-row variant (rejected), no accents, no fullwidth punctuation on the Chinese layer, no Korean or Japanese
  layers.
- Stock's T9 popups in other stock windows are unchanged.
