# Sleep Timer

Our own Sleep Timer page (`m1plus_sleeptimer`, `SLEEP_PAGE`, `patch/sleeptimer.c`) replaces the two routes that opened stock's Power page
(`systemset/powermanager_page`, `view_sleep`): Now Playing's More sheet row ([playmore](playmore.md)) and the Control Center Sleep Timer tile
(id `8`, [pulldown](pulldown.md)). It is built like [Buttons & Power](keyspower.md): stock's own state words, written the way stock's own
handlers write them, no row opening a stock page, nothing of ours saved, no hook, nothing boot-reachable (no kill-switch check). Stock's Power
page stays under All System Settings and shows the same state. Static analysis of V2.1 `demo` (addresses are `demo` virtual addresses,
disassembly cache `work/cache/demo.dis`) and emulator tests; not run on a device.

## The page

A cards page opened by the two entries only (no Settings row): one card of seven check rows (`ACT_SLEEPSET` 170, arg = the row) and a grey
note, "The player turns off when the time is up".

| Row | Text | Word `sleep_time` it leaves |
|---|---|---|
| 0 | Off | 0, byte 0 |
| 1 .. 3 | 15 minutes, 30 minutes, 45 minutes | 900, 1800, 2700 |
| 4 .. 6 | 1 hour, 1.5 hours, 2 hours | 3600, 5400, 7200 |

The title is the stock key `powerm_sleep` (the text the More row and the tile already use). Stock's Spanish text "Temporizador de apagado"
was 7 px wider than the navbar title's room, so `pod_i18n.STOCK_FIX` shortens it to "Temporizador" (it applies to every use of the key,
the Power page's own row included). The row texts and the note are our keys with 12 translations each (`pod_i18n.TEXT`, machine translations,
checked for fit only); `Off` is the existing key.

**Which row is checked** (`st_choice`): Off while the byte is 0; a time only while the byte is on and the word equals that time exactly;
otherwise no row. The word is the seconds left (below), so a running timer matches its preset only until the first tick; a time set on
stock's page (any minute up to 3:59) matches no row either. The page reads the state when it opens and on every `EVT_WINDOW_TO_FG`
(`page_refresh`), which a restack delivers.

**Time Left** (`ACT_SLEEPLEFT` 171). Because a running timer matches no preset after its first tick, a second card sits under the note: one
information row (the About page's kind: label, grey value, no chevron, never sensitive) whose value is the word as `H:MM` rounded up to the
next minute (`st_left_text`: 59 s `0:01`, 1380 `0:23`, 5400 `1:30`, 14399 `4:00`; no language). `page_refresh` shows the row and its card only
while the byte is on and the word is above 0 and hides it (visible and sensitive off, so the page closes up, as LED Light's Theme card) while
no timer runs; the grey Off check is unchanged. The value is read when the page opens, on every return to the front, right after a choice
(`pick_choose` refreshes) and by a page timer: `st_opened` (called from `open_page`) adds one 4 s `timer_add` timer; `on_page_fg` (`st_front`)
adds it again after a background (never twice), `st_on_background` removes it, `on_page_gone` (`st_gone`) removes it with the window. The tick
only calls `pod_page_refresh`. Same pattern as the Cache page's counting timers (`homecover_cache_open`); nothing is on the main loop or a global
timer. `Time Left` is our key with 12 translations.

**Entries.** `pm_on_sleep` (More sheet) restacks an opened `m1plus_sleeptimer_page` with `m1_restack_window`, else `pod_open_sleeptimer`
(`open_page(POD_SLEEPTIMER_PAGE)`), then closes the sheet; a page that will not open leaves the sheet. `pd_run` (`PD_SLEEP`) uses
`pd_open_own`, as Settings and Equalizer: the window in front is left alone, one in the stack is restacked (sub-pages closed first), else it is
opened. The page has the usual top-right Now Playing button, which restacks the player over it; the next tap restacks the page, so the stack holds
one window. `m1_open_sleep` (`patch/common.c`) is gone.

## Stock state and handlers

| Word | Address | Symbol | Meaning |
|---|---|---|---|
| on/off byte | `0xa05a94` | `sleepflag` | the Sleep Timer switch; the page's refresh and the countdown test it for non-zero |
| seconds | `0xa05a90` | `sleep_time` | the seconds left; no `[SYSSET]` key (stock saves nothing: the timer is gone after a reboot; `into_poweroff` clears both, `0x4e0b90..0x4e0b9c`) |

`systemset/powermanager_page`, `view_sleep` (`imgswitch_sleep`, `view_selectors` with `tselector_hour` / `tselector_min`):

| Handler | Does, in order |
|---|---|
| switch click `0x4a9ae0` | byte ^= 1 (`0x4a9b08..0x4a9b0c`); refresh `0x4a9924` with the word 0 stored in its call's delay slot (`0x4a9b14..0x4a9b18`). No save, no `reset_poweroptions_timer`. |
| Back `0x4a91d0` (`btn_return0`) | word = (hour selector * 60 + minute selector) * 60 (`0x4a9258..0x4a9274`), whatever the byte is; tail call `navigator_back`. No save. The top-right Now Playing button (`on_powermanagertoplayer_onclick`, store at `0x4a8da0`) stores the same value. |
| refresh `0x4a9924` | byte non-zero: switch image `sset_on`, selectors shown, hour = word / 3600, minute = word % 3600 / 60; zero: `sset_off`, selectors hidden and disabled. Also run by the page's `EVT_WINDOW_TO_FG` handler `0x4a9b2c`. |
| countdown (`to_poweroptions` tail `0x4ce784`) | byte non-zero and word > 0: word -= 1 per tick; when it reaches 0 the byte is cleared and `navigator_to("poweroff_page")` opens. Runs also while playing (the play-status and car-mode branches jump to it). |

The selectors' options are set in the page's widget walk: hours 0 .. 3 (`0x4a8f84`), minutes 0 .. 59 (`0x4a8ffc`), so every time of ours is one
stock's page can show (the maximum is 3:59). Pinned in `tools/pod_pins.py` `SLEEPTIMER_PINS` (the switch's xor, store and word, Back's arithmetic
and store, the ranges, the refresh's tests, the countdown); a mismatch fails the build. The words are `DATA` entries `SLEEP_FLAG` /
`SLEEP_TIME`, checked against demo's dynsym.

**Our setter** (`st_set`) repeats those stores: Off while the byte is on is the switch (byte 0, word 0); a time from Off is the switch (byte
1, word 0), then Back's store (the word in seconds); from a running timer it is Back's store alone. Choosing the time already set stores it
again (the countdown restarts at the full time). Off while off does nothing. No save and no countdown call, as in stock.

## Tests

`test/pod/sleeptimer.py`, sections `state_tests`, `page_tests`:

- every (byte, word) of eleven states x the seven rows: stock's own switch and Back handlers run under the emulator (the selectors' values
  mocked: hour / minute as the user spun them) and ours must leave the same byte and word and make no save or countdown call; stock's refresh
  `0x4a9924` is then run on the state ours left and must show the switch and the hour / minute selectors for it;
- `st_choice` over sixteen states (counted-down words and out-of-range bytes included), the refused rows, every pinned word against the stock image;
- the page's rows, kinds, actions, texts in all 13 languages, no stock page, no Settings row, the checks as the state changes, a tap's
  stores, the refresh on return to the front and the built asset.

The entries are covered in `playmore.py` (tap opens the page then closes the sheet; five restack cycles; a refused restack or page; a
stale handler; stock's refresh never called by us) and `pdtiles.py` (the tile's open, restack, front and refused cases); `i18n.py` measures
every row, the title and the note in all 13 languages.

## Not verified

- Anything on a device: that the countdown shuts the player down with ours as with stock's page, that a restacked page shows the state, the
  look of the rows and note.
- The period of the countdown tick (read as "one per call of `to_poweroptions`'s tail"; the seconds in the word are stock's name for it, not
  measured) and the guards before `to_poweroptions`' tail were read only as far as the sleep branch.
- No other writer of `0xa05a90` / `0xa05a94` exists besides this page, the countdown and `into_poweroff` (GOT-based xrefs only); the SyncLink
  `GetAutoShutdown` / `SetAutoShutdown` messages were not traced to these words.
- The translations' tone (fit only).
- Design point: because the word counts down, the page shows no check for a running timer after its first tick (the user rule is state = stock's
  own, nothing saved); a note or row showing the time left would need dynamic text.
