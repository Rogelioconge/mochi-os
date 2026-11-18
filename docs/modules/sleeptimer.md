# Sleep Timer

**Sources:** `patch/sleeptimer.c`, `tools/pod_pages.py` (`SLEEP_PAGE`), `tools/pod_pins.py`
(`SLEEPTIMER_PINS`), `tools/pod_i18n.py`.
Our own Sleep Timer page (`m1plus_sleeptimer`) replaces the two routes that opened stock's Power
page (`systemset/powermanager_page`, `view_sleep`): Now Playing's More sheet row
([playmore](playmore.md)) and the Control Center Sleep Timer tile ([pulldown](pulldown.md)). It is
built like [Buttons & Power](keyspower.md): it writes stock's own state words the way stock's
handlers do, saves nothing of its own, has no hook and nothing boot-reachable. Stock's Power page
stays under All System Settings and shows the same state.

## The page

A cards page opened by the two entries only (no Settings row): one card of seven check rows
(`ACT_SLEEPSET` 170, arg = the row) and the grey note "The player turns off when the time is up".

| row | text | `sleep_time` it leaves |
|---|---|---|
| 0 | Off | 0, byte 0 |
| 1 .. 3 | 15 minutes, 30 minutes, 45 minutes | 900, 1800, 2700 |
| 4 .. 6 | 1 hour, 1.5 hours, 2 hours | 3600, 5400, 7200 |

The title is the stock key `powerm_sleep`. Stock's Spanish text "Temporizador de apagado" is 7 px wider
than the navbar title's room, so `pod_i18n.STOCK_FIX` shortens it to "Temporizador" (for every use of
the key, the Power page's row included). Row texts and the note are our keys.

**Which row is checked** (`st_choice`): Off while the byte is 0. A row picked on our page (`st_set`
remembers it and the seconds it stored, in `.scratch`) stays checked while `0 < sleep_time <=` the
last seen word, which it then updates: the word only counts down for the same timer. A higher word
or 0 forgets the pick (another timer or the end), as do Off and the byte off. Without a pick a row
is checked only when the word equals its time exactly, else none (a time set on stock's page
matches no row). A time set on stock's page that is lower than the last seen word cannot be told
from the countdown and keeps the old check. The page reads the state when it opens and on every
`EVT_WINDOW_TO_FG` (`page_refresh`).

**Time Left** (`ACT_SLEEPLEFT` 171) is a second card under the note with one information row
(label, grey value, no chevron, never sensitive). The value is the word as `H:MM` rounded up to the
next minute (`st_left_text`: 59 s `0:01`, 1380 `0:23`, 5400 `1:30`, 14399 `4:00`; no language). It
shows the time left, which the checked row no longer gives after a first tick or for a time set on
stock's page.

- `page_refresh` shows the row and its card only while the byte is on and the word is above 0. Else
  it hides them (visible and sensitive off, so the page closes up).
- The value is read when the page opens, on every return to the front, right after a choice, and by
  a 4 s page timer. `st_opened` adds it; `st_front` adds it again after a background (never twice);
  `st_on_background` and `st_gone` remove it. The tick only calls `pod_page_refresh`. Nothing is on
  the main loop or a global timer.

**Entries.** `pm_on_sleep` (More sheet) restacks an opened page with `m1_restack_window`, else
`pod_open_sleeptimer`, then closes the sheet. `pd_run` (`PD_SLEEP`) uses `pd_open_own`, as
Settings and Equalizer: the window in front is left alone, one in the stack is restacked
(sub-pages closed first), else it is opened. The page has the usual top-right Now Playing button
that restacks the player over it, so the stack holds one window.

## Stock state and handlers

| word | symbol | meaning |
|---|---|---|
| byte `0xa05a94` | `sleepflag` | the Sleep Timer switch |
| word `0xa05a90` | `sleep_time` | the seconds left. Stock saves nothing: the timer is gone after a reboot (`into_poweroff` clears both) |

| stock handler | does |
|---|---|
| switch click | byte ^= 1, then refresh with the word 0 stored. No save |
| Back (`btn_return0`) | word = (hour selector * 60 + minute selector) * 60, whatever the byte is; then `navigator_back`. No save. The top-right Now Playing button stores the same value |
| refresh | byte non-zero: switch image on, selectors shown, hour = word / 3600, minute = word % 3600 / 60; zero: off, selectors hidden |
| countdown (`to_poweroptions` tail) | byte non-zero and word > 0: word -= 1 per tick; at 0 the byte is cleared and `poweroff_page` opens. Runs also while playing |

The selectors' ranges are hours 0 .. 3 and minutes 0 .. 59, so every time of ours is one stock's
page can show (maximum 3:59). `SLEEPTIMER_PINS` pin the switch's xor, store and word, Back's
arithmetic and store, the ranges, the refresh's tests and the countdown; a mismatch fails the
build. The words are `DATA` entries `SLEEP_FLAG` / `SLEEP_TIME`.

**Our setter** (`st_set`) repeats those stores:

- Off while the byte is on is the switch (byte 0, word 0).
- A time from Off is the switch (byte 1, word 0), then Back's store (the word in seconds).
- From a running timer it is Back's store alone.
- Choosing the time already set stores it again, so the countdown restarts at the full time.
- Off while off does nothing.
- No save and no countdown call, as in stock.
