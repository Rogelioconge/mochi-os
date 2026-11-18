# Update Library

**Sources:** `patch/libupdate.c`, `patch/m1plus.c` (`home_open`, `m1plus_home_click`, `info_text`),
`tools/pod_pages.py` (`LIBUPDATE_PAGE`), `tools/pod_pins.py` (`LIBUPDATE_PINS`, `LIBUPDATE_SITE`),
`tools/pod_i18n.py`. **Tests:** `test/pod/libupdate.py`, `test/demo_diff.py`, `test/pod/rows.py`.

Our own page `m1plus_libupdate` ("Update Library") replaces stock's `systemset/updatemusic_page`.
The scan itself stays stock's: the scan dialog and its two workers; Choose Folders is our own picker. The page adds the
library's size, the time of the last completed scan, and a clearer layout.

## The page

Cards page, no glyphs on any row (`NOGLYPH_ACTIONS`):

| Card | Row | Kind | What it does |
|---|---|---|---|
| 1 | Songs (`ACT_INFO`, `INFO_LUSONGS`) | info, no touch | `toolsGetDbTableNumber("songtable", "/mnt/data/database.db")`, stock's own count query, with a thousands comma; `-` when it fails. Read each time the page is in front, so it follows a scan. |
| 1 | Last Updated (`INFO_LUWHEN`) | info, no touch | The recorded scan time, `-` when there is none (the row stays, so the card does not change shape). |
| 2 | Update Now (`ACT_LUNOW` 193) | action, no chevron | Stock's handler `0x4af070`: `navigator_to_with_context("dialog/scanmusic_dialog", four zero words)`, a full scan that drops and rebuilds `songtable`. |
| 2 | Choose Folders (`ACT_LUFOLDERS` 194) | link | Stock's check `0x4af1f4` (`toolsCheckMount("/mnt/mmc")`, else `msg_nottf`), then [the folder picker](#the-folder-picker-choose-folders). |
| 3 | Auto Update (`ACT_LUAUTO` 195) | switch | Stock's toggle `0x4af0bc`: the byte `autoscan_flag` (`0xa05aa9`, `[SYSSET] AUTOSCAN`) is stored as its xor, then `write_int_config`. The generic switch shows the byte. |

The page keeps its window in the shared refresh slot (`pod_fg`). If a second Update Library window opens (Home tile, then
Settings > Library after Now Playing), the first is remembered (`pod_fg_prev`) and takes the slot back when the second
closes, so the remaining window keeps refreshing Songs and Last Updated.

Notes: under card 2 "Choose Folders only adds new music. To remove deleted songs, use Update Now."; under the
switch "Updates after a card is inserted or USB transfer ends." (both two lines, checked in all 13
languages by `test/pod/i18n.py`). Stock's triggers for Auto Update are unchanged: a hot card insert and the end
of a USB transfer set a pending flag (`0xa041a0`) and the main loop opens the scan dialog with a zero context.

## Last Updated

One line on the card, `/mnt/mmc/.m1plus/library-updated`: the Unix time in decimal and a newline, written atomically by
`m1_card_write` (library state lives on the card, never in `/mnt/data`). No card, a clock before `M1_MIN_EPOCH` or a
failed write leave the old record.

The text is local time, with the clock as 24-Hour Time says (the Date & Time page's Time row): `Today 09:41`
(`Today 9:41 AM`), `Yesterday 21:05`, `Nov 14 09:41` (month names are the existing `Jan %d` keys), `2025-10-09` for
another year. An empty, malformed or pre-`M1_MIN_EPOCH` record reads `-`.

### The hook (payload hook 34)

The scan dialog's timer callback (`0x47bab0`, 200 ms) polls the state word `0xa03a40`: 0 while the worker runs, 1 when
`scanAllMusicFile` / `scanSpecFolder` returned, then +1 per tick; at 3 the dialog quits. At the first tick that sees
the state above 0 it calls the dialog's refresh `0x47b604` with `done = 1` (the "finished" texts) through
`bal` at `0x47baec`. That `bal` becomes `jal lu_scan_finish`: stock's refresh first, then, when the state is 1 and
`toolsGetUserStop()` is 0 and the scan reached its commit (`lu_committed`), the record; the flag is cleared at every
finish. Both worker kinds (Update Now, Choose Folders, and Auto Update's full scan)
go through the same callback.

- Commit flag: both scan functions end a successful scan with `toolsDatabaseCommit` (`0x5ed96c`: COMMIT,
  `sqlite3_close`, the handle = 0), at a `jalr t9` (`0x4e9e70` in `scanAllMusicFile`, `0x4e9f9c` in
  `scanSpecFolder`; GOT load before, nop after). Both become `jal lu_commit`. Stock's commit drops the COMMIT's
  result, so `lu_commit` runs the COMMIT itself when the rows-since-the-last-COMMIT word (`0xa0b080`, which the insert
  path adds 1 to and commits at 100) is above 0: `sqlite3_exec(handle 0xa0ac74, "COMMIT;")`, then the word = 0.
  `lu_committed` is set only when it returned `SQLITE_OK` (a busy or failed COMMIT records nothing). Stock's commit
  then only closes the handle. A word at 0 means no transaction is open, so nothing to commit and the scan counts
  as committed.
- Batch COMMIT: the insert path (`toolsInsertDbTable`) commits every 100 rows with `jalr t9` (`sqlite3_exec`, result dropped) at
  `0x5ee090`, which becomes `jal lu_batch_exec`: the same `sqlite3_exec` call (the fifth argument stays at `0x10($sp)`
  of the caller's frame, as stock set it), and a nonzero result sets `lu_failed`. Stock's insert-error path runs `ROLLBACK;`
  through the same call; any statement other than `COMMIT;` sets `lu_failed` too, whatever it returns. `lu_scan_finish` records only when
  `lu_committed` and not `lu_failed`, and clears both. Only the scan reaches 100 uncommitted rows, so the flag needs no
  clear at a scan's start.
- Failed scan: when `toolsInitDatabase` fails, the scan functions skip the scan and the commit (`bne` at `0x4e9e3c` /
  `0x4e9ee4`) and return; the worker still sets state 1. No commit flag, so nothing is recorded.
- Cancel (`0x47b5ac`) sets the stop byte `0xa0b088` (`toolsStopUpdateMusic`), which the worker's return does not
  clear and the dialog's init does (`toolsClearDbCount`); the worker then still sets state 1, so the stop byte is
  what tells a cancelled scan from a finished one. A cancel pressed in the 200 ms between the worker's return and
  the first tick is also not recorded.
- Pinned by `LIBUPDATE_PINS` (the callback's words around the site, the delay slot, both workers' stores, the stop
  byte's writer, reader and clear, the dialog's init). Fallback: any mismatch fails the build; the hook is one
  `bal` replaced by one `jal` (calling stock's refresh unchanged) and two `jalr t9` replaced by `jal lu_commit`, one by `jal lu_batch_exec`
  (calling stock's commit unchanged).
- Bounded work: one `time`, one small file write on the UI thread, once per scan. No thread, timer or loop. Not on
  the boot path; like the other hooks on tap-only stock screens it does not read the kill switch.

## Entry points

| Entry | Path |
|---|---|
| Settings > Library > Update Library | `ACT_PAGE` row to `LIBUPDATE_PAGE_INDEX` |
| Menu / Extras item "Update Library" | item id 2 (frozen), `ACT_HOME`: `home_open` opens our page first, stock's dispatcher where it will not open |
| Stock Home grid tile (id 2) | `m1plus_home_click` (hook 1) opens our page unless the kill switch exists or the page will not open |
| All System Settings (stock's list) | stock's page stays, as for Playback Settings; the Control Center and the Pod have no entry |

## The folder picker (Choose Folders)

**Sources:** `patch/lupick.c`, `tools/pod_ui.py` (`build_lupick_page`), `tools/pod_pages.py` (`LUPICK_PAGE`, key `m1plus_lupick`, last in
`PAGE_ORDER`). **Tests:** `test/pod/libupdate.py` (`picker_tests`, `picker_asset_tests`). No `ACT_` id: the page has no settings rows.

`lu_folders()` keeps stock's card check (`toolsCheckMount("/mnt/mmc")`, else `msg_nottf`), then `lupick_open()`; stock's
`systemset/specfolder_page` is only the fallback when the window will not open (`-1`).

The page is the Folders page's structure ([folders](folders.md)): glass navbar, a stock list holding one view the payload paints (a
rounded card of 52 px rows: select circle, name, chevron; hairlines; the grey caption MUSIC CARD at the root), no widget per row.
Title: Choose Folders at the root, else the folder's name. Navbar: Back, Select All disc (`ah_nav_unsel` / `ah_nav_sel`, checked
when every row of the level is ticked or covered), Now Playing. Bottom bar: one pill.

- **Listing.** `opendir` / `readdir` of the level on the UI thread, folders only, as stock's `toolsLoadDirectory` (0x5e85c8):
  `d_type` 4 (a link or unknown type by one `opendir`), no name starting with `.`, and not `lost+found`, `System Volume
  Information`, `RECYCLER`, `$RECYCLE.BIN`, `lockscreenimage`; `/mnt/mmc/Android/data` lists nothing (0x5e86bc). Order is the
  lists' name order (`cc_key_cmp`), not stock's own comparator (`algo_sort_if`, not read). At most `LP_MAX` (1500) folders a level,
  names in 256 KB, a path under 512 bytes; depth is unbounded (offsets kept for 24 levels).
- **Chevron.** A timer (16 ms) probes one row in view per tick; the first folder found ends the probe. A probe that reads 4000 entries
  without an answer counts the row as holding a folder (chevron, tap opens; an empty level shows No folders). A row
  not probed has no chevron; a tap on it probes it first.
- **Selection.** A set of full paths (at most 256, kept for this visit across levels). A selected folder covers what is under it:
  those rows show ticked, dimmed, and the circle does nothing; selecting a folder drops its selected descendants, and the limit is checked on the size after that drop (size - dropped + 1).
  The circle toggles; the rest of a row opens the folder if it holds one, else toggles. Select All toggles the uncovered rows of the
  current level (all ticked: clears them). Otherwise it adds every unticked row, each dropping its selected descendants; the limit is
  on the size after that, so when the result is over 256 it adds as many as fit, the rows that hold selected descendants (they free
  room) first, then the rest in the order shown, and says "You can choose up to 256 folders."; a tap that can add none, with some of
  the level's rows in the set, clears them. A path that cannot be allocated stops Select All and keeps the set (no message,
  no clear). Back pops a level (offset restored); at the root it closes the page. The hardware Back
  key closes the page at any level.
- **Pill.** "Scan N Folders" ("Scan 1 Folder"); with none, "Scan Folders", dimmed: not sensitive and not enabled (the style's disable state follows the enable flag). Live: light grey, black text;
  dimmed: dark grey, grey text.
- **Scan.** Stock's `btn_startscan` (0x4ac9f8): `stop_player`, a `char*` deque of the full paths, `navigator_back`, then
  `navigator_to_with_context("dialog/scanmusic_dialog", {deque, 0, 1, 0})` (`scanSpecFolder(deque, 0)`, add only). The picker is
  gone before the dialog opens, so the dialog returns to Update Library, whose Songs and Last Updated are read when it is in front.
  Stock destroys the deque right after that call while the dialog's worker thread reads it; the picker keeps it and
  `lu_scan_finish` (`lp_scan_done`) destroys it at the first finished tick, when the worker has returned.

Constants: `LP_*` in `patch/lupick.c`. Texts (all 13 languages): Scan %d Folders, Scan 1 Folder, Scan Folders, MUSIC CARD, No folders, You can choose up to 256 folders.
