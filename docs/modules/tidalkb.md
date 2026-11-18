# Keyboard in the stock Tidal > Search page

**Sources:** `patch/tidalkb.c` (`tidal_kb_focus`), `patch/tidalkb.h`; `add_tidal_keyboard` in
`tools/pod_ui.py` (the asset edit); `TIDALKB_SITE`, `TIDALKB_SEARCH`, `TIDALKB_PINS` in `tools/pod.py`.
Stock's Tidal > Search page has one edit, `search_edit`, and used to pop stock's T9 for it. We embed
our pad **inside the stock page** with `keyboard_attach` ([keyboard](keyboard.md)): Tidal's toolbar
and search bar stay, the pad sits at the bottom over the history and results, and the typed text
shows in the bar. No page of ours opens (a separate keyboard page would change the navbar style). One call-site hook ([payload](payload.md) hook 27); no ACT id, page id or
settings file; nothing at boot.

## Stock behaviour we rely on

- The page init focuses `search_edit` with `edit_set_focus(edit, 1)`, which pops T9. The hook sits on
  that call.
- Stock's search routine (`stock_tidal_search`) reads only the edit's text, writes the 5-entry
  history, shows the waiting state and starts the search; an empty text shows a warning.
- A tap on a history row writes its text into the edit and searches, without telling us.
- The search threads only download; a timer parses the answer onto the result deques and rebuilds the
  list from the whole deque. Stock clears the deques only in the tab buttons and the page init.
- AWTK's `edit` never emits a click. Only the bar's `list_item` turns a tap into `EVT_CLICK`, and
  only if no child answers `RET_STOP`. A `view` has no on_event, so a touch on our field passes on
  to the `list_item`.

## The asset

`add_tidal_keyboard` (build time) adds to `ui/tidal/tidal_serach_page.bin`, the only copy, and asserts
the stock layout:

- In the bar's `list_item`, after the stock edit: `kb_field` (transparent, sensitive) with the hint
  `Search Tidal` (translated; the widest fits the text room), text, caret and a clear button at its
  right end, 18 px like the stock edit. A longer text shows its end after an ellipsis. No magnifier. The stock
  `search_edit` stays in the tree (stock looks it up) but is hidden and insensitive at run time.
- At the end of the window (painted over the history, results and wait image): the shared pad,
  strip and pop-up. The window is the 450 px client area, so the pad's bottom is the screen's.

Taking our widgets out gives the stock bytes. An unedited asset has no `kb_pad`, so
`keyboard_attach` fails and stock's T9 runs.

## Hook

`jalr edit_set_focus` in the page init becomes `jal tidal_kb_focus`. Everything is decided once, in
the init, before anything is changed.

1. With no keyboard up and an edit in a window, `keyboard_attach` runs **in the init** (it only looks
   widgets up by name, so it needs neither the window stack nor the page on top), then the hook binds
   the page's `EVT_DESTROY` and the bar's `EVT_CLICK`, arms the poll, hides and disables the stock
   edit and returns without focusing it. **Any failure** (a keyboard up, no window, no `kb_pad`, a
   handler that will not bind, no navbar button) detaches again, hides our widgets
   (`tk_hide_ours`, else the unbound pad would cover 180 px and the field take taps meant for the
   edit) and runs stock's `edit_set_focus`: **T9 as before**.
2. `tk_on_change` writes the committed text into the stock edit on every change (limit 127 bytes).
3. The action key (`tk_on_go`): trims, does nothing on an empty text, puts the text in the bar,
   hides the pad and runs stock's search. The results show where the pad was.
4. A tap on the bar (`tk_on_click`) with the pad hidden syncs and shows the pad.
5. **History taps:** a 250 ms page-scoped poll (`tk_tick`) compares
   the edit's text with the pad's; a difference means stock wrote it, so it is shown in the bar and
   the pad hides. A tap on the bar syncs first, so a missing timer only delays this.
6. Destroy removes the poll and detaches. A second Tidal search page while the first has the
   keyboard gets stock's T9.
7. **Navbar Search button:** stock's init creates the button before the hook runs, bound to the search
   routine. AWTK runs the newest handler first and `RET_STOP` ends the dispatch, so the hook binds
   `tk_on_search_btn` on it (found as the navbar's last child at 273/0/47/50): it syncs, runs
   `keyboard_go` (which commits pending pinyin first, so `nihao` searches 你好) and answers
   `RET_STOP`. After destroy it passes the tap on.

No kill-switch check: a tap-only hook on a stock page relies on its stock fallback. Pinyin and the
other keyboard features come from the shared keyboard (Settings > General > Keyboards).

## The tap

Symptom: a tap on the bar after a search did nothing when `EVT_CLICK` was bound on the edit. Fix: bind it on the edit's parent (the `list_item`, or the edit itself with no parent),
with the edit as context. A drag that starts on the bar is no click. Searching never rebuilds the
bar, so the same handler takes the tap with results showing.

## Re-search

Symptom: search "a", tap the bar, type "b", Search: the results did not refresh. Fix: `tk_on_go`
(`tk_reset_results`) does what the tab buttons do before a search: limit 50, offset 0, `deque_clear`,
scroll 0, for all three result structs (tracks, artists, albums; the current tab is unchanged).
`total` is left to the parse. All deque work runs on the UI thread, so clearing is safe even with a
download in flight (its answer is parsed later into the cleared deque).
