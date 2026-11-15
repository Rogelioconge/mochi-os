# Date & Time

Settings > General > Date & Time (`m1plus_datetime`, `DATETIME_PAGE`, `patch/datetime.c`) is an own cards page for what stock keeps behind
System list row 5 (`system_time`, All System Settings): Set Automatically, Time Zone, manual date and time, 24-Hour Time. Every
state is stock's own; nothing of ours is saved to a file. Stock's three pages stay under All System Settings and show the same
state ([autotime](autotime.md) for the sync and the RTC, [timezones](timezones.md) for the 43-zone table). No new hook, nothing at boot or paint.

## Page

| Row | Kind | State | Opens |
|---|---|---|---|
| Set Automatically | switch (`ACT_DTAUTO` 157) | byte `auto_sync_nettime` `0xa05ab1`, `[SYSSET] AUTOSYNCTIME` | |
| Time Zone | value (`ACT_DTZONE` 158), the zone's English label | word `time_zone` `0xa05ab4`, `[SYSSET] TIMEZONE` | `m1plus_timezone`: 43 check rows (`ACT_DTZONESET` 159) in `tools/timezones.py` `ORDER` (west to east), arg = the saved index |
| Date | value (`ACT_DTDATE` 160), `2026-11-15` | the local clock | `m1plus_dtdate` |
| Time | value (`ACT_DTTIME` 161), `14:05` or `2:05 PM` | the local clock, 24-Hour Time | `m1plus_dttime` |
| 24-Hour Time | switch (`ACT_DT24` 162) | byte `time24hflag` `0xa05ab0`, `[SYSSET] TIME24H` | |

The Date page holds Year, Month and Day (value rows, `ACT_DTFIELD` 163) and a Set Date row (`ACT_DTAPPLY` 165, arg 0); the Time page
Hour and Minute and Set Time (arg 1). Each field opens a check-row picker (`m1plus_dtyear` 2022..2050, `dtmonth`, `dtday`,
`dthour`, `dtminute`; `ACT_DTSET` 164, arg = field * 4096 + value). The pages open with the date being typed read from the clock
(`dt_edit_start`); the pickers only change it in memory. Set Date / Set Time write the clock and go back. Choosing a month or year
that leaves the day past the month's end moves the day to the month's last (ours; stock's selector offers only valid days). A
clock outside stock's range (year before 2022 or after 2050, month or day out of range) starts at 2022, 1, 1 as stock's init does.

What the switch controls (from stock's own pages, not a choice of ours):

- Time Zone is **always** live, whatever Set Automatically says. Stock lists the zones only while auto time is on: its page builder
  `0x4a2424` makes the zone rows only then (`movz v0, 1, auto` at `0x4a2474`: auto off leaves the one switch row). That is layout
  only (the address is kept): the click handler `0x4a25b8` does not test the byte, and a chosen zone just stores `time_zone`, saves
  `[SYSSET] TIMEZONE` and calls `select_timezone`. Ours never dims the row and `dt_zone_set` does not look at the auto byte, so
  someone without Wi-Fi can pick a zone without turning automatic time on.
- Date and Time are live only while it is **off**: stock's Manual row (`typedatetime_page`, refresh `0x4aebd8`) is disabled while the
  byte is set (`0x4aec74` / `0x4aec7c`). Ours dims them and `dt_apply` refuses while auto is on.
- (`timezones.md` said the zone rows exist while auto time is off; the page builder's `movz` shows the reverse. Corrected there.)

## Stock

`typedatetime_page` (init `0x4aed58`; title `system_time`) holds three rows: Auto (`listitem_auto`, opens `autosynctime_page`), Manual
(`listitem_manual`, opens `datetime_page`) and the 24-hour switch (`listitem_24h`, handler `0x4aeb50`).

- **Set Automatically** (`autosynctime_page` click `0x4a25b8`, row name `0`): from on, store 0 in `sync_nettime_flag` `0xa05a66` and in
  the byte, then `write_int_config(byte, "SYSSET", "AUTOSYNCTIME")`; from off, store 1 in both, then the save. Then it rebuilds the list.
  The flag is what `networktime_adjust_thd` `0x4d92bc` (a thread, every second) acts on once Wi-Fi is up: it runs `ntpdate` (four servers),
  then `toolsSetRtcTime`. The switch itself calls nothing blocking. `dt_auto_toggle` repeats the stores and the save, in order.
- **Time Zone** (same handler, row `n` is zone `n - 2`): the zone that is chosen already does nothing; else `time_zone` is stored, then
  `write_int_config(index, "SYSSET", "TIMEZONE")`, then `select_timezone` `0x4d6b2c` (our `tz_select` hook: `setenv("TZ")` from the table).
  `dt_zone_set` does the same. No `tzset`; `get_systime` calls it before reading the clock, so the Date and Time rows show the new zone.
- **24-Hour Time** (`0x4aeb50`): byte xor 1 stored in the delay slot of `change_time24h_12h` `0x544ab0` (the status bar clock's format,
  `"hh:mm"` when the byte is set, else `"HH:TT"`; it looks up `bar_dclock` in the status bar window and does nothing without one), then
  `write_int_config(byte, "SYSSET", "TIME24H")`. `config_init` keeps 0 and 1, anything else is 1 (default). The label and the on image
  mean 24 hours when the byte is 1; which of the two AWTK format strings shows 24 hours is read from that label, not tested on a device.
- **Manual date and time** (`datetime_page`): init `0x4a58fc` calls `get_systime(&minute, &hour, &day, &month, &year)` `0x4d76e4`
  (`toolsGetSysTime`: `tzset`, `localtime`) and fills five text selectors (year clamped to 2022..2050). The confirm handler `0x4a576c`
  reads the five and calls `set_systime(year, month, day, hour, minute)` `0x4d7770` (which calls `toolsSetRtcTime(0, minute, hour, day,
  month, year)`: `date -s "Y-M-D h:m:s"`, then `hwclock -wu`, [autotime](autotime.md)), then `navigator_back`. Ours calls `set_systime` with
  the same five numbers (checked against the confirm handler under the emulator); Set Date keeps the clock's time of day and Set Time its
  date, because stock's page holds both.

**UI thread.** `set_systime` runs `system()` twice (`date`, `hwclock`) on the UI thread, in stock's confirm handler and in ours; the page
freezes for that moment. Kept as stock does it. Nothing else blocks: the toggles store, save and return.

## Not done

- Date format and week day: stock has none.
- A calendar or wheel entry: the pickers are plain check lists (no new widget).
- The status bar clock and the lock screen read the byte and the clock on their own; nothing here repaints them (24-Hour Time calls stock's
  `change_time24h_12h`, as stock does).

## Pins and tests

`tools/pod_pins.py` `DATETIME_PINS` (checked at build): the switch's stores and save, the page builder's row count, the zone click's
store, save and same-zone test, the 24-hour switch, `config_init`'s clamp, the Manual row's gate, the manual page's clamps, the confirm
call and `set_systime`'s call. Stock functions and bytes: `tools/pod.py` (`get_systime`, `set_systime`, `select_timezone`,
`change_time24h_12h`, `AUTO_TIME`, `SYNC_NEED`, `TIME_24H`; names checked against the dynsym).

`test/pod/datetime.py` runs stock's own handlers under the emulator on the same state and compares the stored words, the calls in order
and the state at each call: Set Automatically from all four states, 24-Hour Time from both, every zone change (4 current zones x 43), and
stock's confirm handler against ours for `set_systime`'s arguments. It also checks the clock texts (24 and 12 hours), the edit rules
(clamps, leap years, refusals), the page rows and kinds, the dimming, the refresh on return to the front, the pickers, Set Date / Set Time
and the assets. `test/pod/i18n.py` measures every row, title and note in all 13 languages.

## Device checks open

- Set Automatically on with Wi-Fi up: the clock syncs within a few seconds (the thread, as under stock's page).
- Time Zone: choose Kolkata, the Date and Time values follow; stock's zone page ticks the same zone.
- Set Date and Set Time with auto off: the clock changes, survives a reboot (the RTC write), and stock's manual page shows it.
- 24-Hour Time: the status bar clock changes format; which format is 24 hours (see above).
- The freeze while Set Date / Set Time run (`system()` twice) is short enough.
