# Battery History

**Sources:** `patch/batthist.c`, `patch/batthist.h`, `patch/battery.c` (the start); the page: [History
page](#history-page). **Tests:** `test/pod/batthist.py`. **Setting:** Settings > Battery > **Battery History**, a row (On or Off, chevron; `ACT_BHPAGE` 190) opening its own page, whose first card is the switch, **off by
default**, `/mnt/data/m1plus/battery-history` (`1` on; [settings](settings.md)); note "Keeps the
last 24 hours of battery level and use. Turning it off deletes them." (`ACT_BATTHIST` 188; `m1plus_batthist`, `BATTHIST_PAGE`).

Records the last 24 hours of battery level and what the player was doing, for the History page
(below). Nothing is recorded, started or kept while the setting is off.

## Recorder

One detached thread, `bh_main`, exists only while the setting is on. It is **not** the status bar
tick: `show_sysbar_face` (hook 8) returns early in stock's standby (with the screen merely dark it keeps
ticking, as the wake probe's logs show). `bp_capacity` (hook 8, [battery](battery.md)) calls `bh_poll` after the
Charge Limit's tick, only without the kill switch: a cached state compare while off, otherwise it
makes the thread when none runs (a failed `pthread_create` is retried after 30 ticks). The switch
starts it too. The thread ends when the setting file says off (the switch, or Reset All Settings
deleting it), after clearing the ring and unlinking the data; a switch turned on again meanwhile
is seen under the lock that ends the thread.

Every `BH_PERIOD` (15) s `bh_sample` reads:

| Input | Source |
|---|---|
| Wall clock | `time()`; before 2020-01-01 it is an unset RTC: nothing recorded |
| `CLOCK_MONOTONIC` (1), `CLOCK_BOOTTIME` (7) | `clock_gettime`; without BOOTTIME it stands in for it (a long step is then a clock jump, never standby) |
| Screen | `m1_screen_lit()`, the backlight byte `0x97cae4` |
| Playing | `mclGetPlayStatus() == 2`: `lw v0, 0xa0abe4` (pinned in `tools/pod_pins.py`, `0x5d3654`), a plain word load, also read by the lock screen, VU page and tracklamp; radio's status is reconciled into it ([radio](radio.md)) |
| External power | `/sys/class/power_supply/battery/status` (`BH_STATUS`): `Charging`, `Full`, `Not charging` = external power, `Discharging` = battery, anything else keeps the last answer |
| Gauge | `battery_gauge()` (`/sys/class/power_supply/battery/capacity`), every `BH_GAUGE` (60) s of BOOTTIME and at once after a standby |

External power comes from sysfs, not the `POWER_EXT` word (`0xa059f8`): that word is only updated
by `get_battery_capacity` on the status bar tick, which may not run in standby, and the status text
is the kernel's own answer. `Not charging` counts, so the Charge Limit's hold stays "on the
charger".

### Time

Per step: `awake` = BOOTTIME delta minus `suspended`; `suspended` = BOOTTIME delta minus
MONOTONIC delta (MONOTONIC stops in suspend; at least `BH_SUSP` 5 s counts). The awake part gets
the sample's state (screen on over playing with the screen off over idle) and goes into the bucket
of the wall clock now. The suspended part is idle known time, spread over the buckets of the wall
span it covered (anchored at the sample), so buckets nobody sampled still say "standby". Times
are stored in units of 8 s with the remainder carried.

- Wall minus BOOTTIME more than `BH_JUMP` (120) s ahead: the clock was set forward; the buckets in
  between stay gaps and only the BOOTTIME delta counts. More than that behind, or a bucket number
  two or more behind the newest: the history is dropped (a small step back is ignored).
- MONOTONIC or BOOTTIME going backwards (not the same run) or an unset RTC: a new baseline, no time
  made up. The first sample of every baseline opens its bucket and reads the gauge.
- A reboot is found from the file: its newest bucket is older than now, the buckets between are
  gaps (`BH_F_GAP`); a newest bucket in the future drops the file.

### Drops

On battery the seconds per state (screen on, playing, idle) are summed since the last drop. A gauge
read lower than the last gives the whole drop to the state with the most seconds (screen on, then
playing, then idle on a tie), and clears the sums. With `BH_SUSP_DROP` (30) s or more of standby
since the last gauge read the drop is the standby's (idle). On external power (any sample of the
bucket, or the charger having ended inside the interval's first bucket) the sums are cleared,
nothing is attributed and the bucket gets `BH_F_CHG`; a rise is just a new level.

## Ring and file

96 buckets of 900 s of wall clock (UTC; number = wall / 900, slot = number % 96), 8 bytes
(`struct bh_bucket`):

| Byte | Field |
|---|---|
| 0 | `level`: the gauge at the end of the bucket, 0..100, `0xff` unknown (a new bucket starts with the last level) |
| 1 | `flags`: 1 `BH_F_CHG` charging seen, 2 `BH_F_GAP` no data (power off, clock jump, not recorded yet) |
| 2 | `on`: screen on, units of 8 s |
| 3 | `play`: playing with the screen off |
| 4 | `cov`: known time (sampled or standby seen); `on` and `play` are parts of it, the rest is idle / standby |
| 5, 6, 7 | `d_on`, `d_play`, `d_idle`: percent the gauge fell, attributed to the screen on / playing / idle and standby |

`/mnt/data/m1plus/battery-history.bin` (`BH_DATA`): `magic "BHS1"`, `version` 3 and `count` 96
(u16 each), `head` (the newest bucket's number), the [since-charge](#since-last-charge) fields
(`unplug_at`, `unplug_lvl`, `sc_play`, `sc_on`, `sc_total`, u32 each), a checksum, then the ring in slot
order: **804 bytes, always** (a 36 byte header). Written with `m1_save` (tmp, fsync, rename) when a bucket has just
been opened, so at most every 15 minutes; a power loss costs the open bucket and up to 15 minutes of the
since-charge counters. Read once at the
thread's start; magic, version, size, checksum, head not before 2020 (`unplug_at` may be after it: a clock set back keeps the run),
`unplug_lvl` 0..100 or unknown, `sc_play` + `sc_on` not above `sc_total`, no counters without an `unplug_at`
and every bucket value are checked, otherwise the file is discarded. A write that finishes after
the setting went off deletes its file again.

## Since last charge

The 24 hour charts cannot say how much was played since the player was unplugged, which may be longer than
a day, so the file header keeps a run that is independent of the ring:

| Field | Meaning |
|---|---|
| `unplug_at` | wall time the charger was last removed; 0 = no removal seen yet (nothing counts) |
| `unplug_lvl` | the gauge then (the last reading when that sample did not read it; `BH_NONE` unknown) |
| `sc_play` | seconds on battery since then with the player playing and the screen off (same precedence as the bucket's state: screen on, then playing, then idle; the three kinds never overlap) |
| `sc_on` | seconds with the screen on |
| `sc_total` | all known seconds on battery: awake plus standby, so idle and standby are in it |

The external power to battery step (`bh.chg` 1 to 0, in `bh_account`) starts a new run: the three counters go
to 0 and `unplug_at` / `unplug_lvl` are set (that step's own time is still the charger's). Awake time follows
the sample's state (`playing`, `lit`), the suspended part goes into `sc_total` only. On external power they stand
still and keep their values. They are saved with the bucket-open write and read back with the ring; a reboot does
not count the time the player was off, and a reboot on the charger keeps the old run until the next unplug. A clock
set back drops the ring but **not** the run (`bh_clear_ring`: the counters are seconds, not wall time); a missing or
bad file and the setting off clear it (`bh_clear`).

## Snapshot

`int bh_snapshot(struct bh_view *out)` (`patch/batthist.h`): 1 and the view, or 0 with `out`
zeroed when the setting is off or no bucket is open. The ring is copied under a spin lock (a few
instructions, no I/O inside; the thread's end reads the setting file under it). The view has the
96 buckets oldest first (`b[95]` is the open one, `head` its number), per-state totals over buckets that have data and no charging (`t_*` seconds, `d_*`
percent: the On Battery rows) and `act_on` / `act_play` seconds over every
bucket with data, charging included (the Activity chart), and the run: `unplug_at`, `unplug_lvl`, `level`
(the gauge now, the open bucket's) and `sc_play` / `sc_on` / `sc_total`. `bhpage_show`
(patch/bhpage.c) is its caller.

## Cost

Setting off: one cached compare per status bar tick. On: the thread's wakeup every 15 s (two
`clock_gettime`, one status read, the backlight byte and play word), a gauge read per minute, a
804-byte write per quarter hour; ring and state about 1 KB of `.scratch`.

## Open device questions

- Does the kernel suspend with the screen off, and does `CLOCK_BOOTTIME` run ahead of
  `CLOCK_MONOTONIC` there (the standby gap detection depends on it)? Without a difference, standby
  looks like idle awake time, which is still attributed to idle.
- The exact text of `battery/status` while the Charge Limit holds (`Not charging` is assumed).
- Whether a sleeping thread keeps the device from deep standby (it should not hold a wake lock;
  `sleep` is a plain nanosleep).
- The gauge's steps (whole percent) against a 1 % an hour idle drain: the estimates need a few hours
  of data before they mean anything.

## History page

**Sources:** `patch/bhpage.c`, `tools/batthist_model.py` (the Python model), `tools/pod_ui.py`
`cards_hist` / `cards_summary`, `tools/preview/preview_batthist.py`. **Tests:** `test/pod/batthist.py`
(`sc_tests`, `history_tests`, `texts_tests`, `visibility_tests`).

The page is `BATTHIST_PAGE` (`tools/pod_pages.py`), opened by the Battery page's Battery History row (a value row
like Charge Limit: `row_value` writes On or Off, and the Battery page refreshes as it comes back in front), after
the switch's note. The items are in the asset (hidden and insensitive) and `bhpage_show` shows the ones that belong
to the state; it runs from `page_refresh` (patch/m1plus.c: the page opening, back in front) and from the switch's
click (`pod_page_refresh(POD_BATTHIST_PAGE)`). The list_view layouter skips hidden items, so the page closes up and
grows in place. It reads `bh_snapshot` each time and never touches the ring.

| State | Shown |
|---|---|
| Setting off | nothing |
| On, no closed bucket with data (`b[0..94]`; the open one does not count) | the note "Battery history appears after the first 15 minutes." alone (no header) |
| On, data | everything below; the Since Last Charge header and card only with an `unplug_at` |

Items, in page order (widget names, heights from `tools/pod_settings.py`): the switch `pod_row0` and its note
`pod_note0`; header "Since Last Charge" (`pod_sec0`) and its card (`pod_hist0`, 254); "Last 24 Hours" (`pod_sec1`)
and the level chart (`pod_hist1`, 150); "Activity" (`pod_sec2`) and the activity chart with its legend (`pod_hist2`,
150); "On Battery" (`pod_sec3`), three rows (`pod_row1..3`, `ACT_BHROW` arg 0..2, 60) and the note "Estimated from the
battery gauge." (`pod_note1`); the empty note (`pod_note2`).

**Bitmaps, not widgets, for the bars.** Each of the three items is a transparent view the list's width whose
`EVT_BEFORE_PAINT` blits a 300 px wide RGBA bitmap at x 10 (`peq_blit`, as the preset page's graph,
[peq](peq.md)); the bitmaps are made when data first shows (the card's only with an `unplug_at`) and destroyed with
the window. The card (`#1C1C1E`, 12 px corners in the alpha, nothing under its height), the dotted gridlines at the
plot's top, middle and bottom, the hour ticks, the bars, the charger band and the marks are drawn in `bhpage.c`;
`batthist_model.py` is the same drawing in Python and the test compares them pixel for pixel. Offsets are `BHC_*`,
`BHL_*`, `BHA_*`, `BHS_*` in `patch/offsets.inc` (read by `tools/pod_ui.py`, asserted against `pod_settings.py`).
Axis labels, hour labels, legend names, captions, durations and rows are real labels (language and font).

**The three kinds** (Screen On, Playing / Screen Off, Standby) are exclusive everywhere and always the same marks:
10 px squares with radius 4 (antialiased over the card), light `#E6E6E6`, mid `#78787C`, dark `#3A3A3C`; in the
activity chart's legend, in the card's rows and, as small `view` widgets with `round_radius` 3, in the On Battery
rows. Standby is the rest: `sc_total - sc_on - sc_play` (awake idle counts as standby, as in the ring).

**Since Last Charge card** (`BHS_CARD` 244): a grey 15 px caption "Unplugged at 21:25, 100%" (`unplug_at` as 12 / 24 hour
local time by 24-Hour Time, `unplug_lvl`; ", N%" dropped when it is `BH_NONE`), the total on battery `sc_total` in the
bold face (28 px, `ly_title_face`), right aligned grey 18 px "58% left" (the gauge now, empty when unknown), a stacked bar
(276 x 10, rounded ends: screen on / playing with the screen off / standby, edges `(276 * s + t / 2) / t` with the
seconds halved until `t` is under 2^20; all standby with no time) and three rows of 44 px with a mark, the name (20 px white) and the
duration (18 px grey) right aligned, hairlines between.

| Chart | Bars | Colours |
|---|---|---|
| Level | 48 of two buckets (`b[2j]`, `b[2j+1]`), 5 px apart, 3 wide; height `level` px of 100 (`(level * 100 + 50) / 100`); the later bucket's level, else the earlier's; none without a level or in a gap | grey 216; `#34C759` when either bucket has `BH_F_CHG`; `#FF1448` at 20 % or less (on battery) |
| Activity | 24 of four buckets, 10 px apart, 8 wide; seconds with the screen on at the bottom (`#E6E6E6`), playing with the screen off above it (`#78787C`); each `(s * 76 + 1800) / 3600` px of 76, the second capped to the room left | charging buckets count (`act_*`) |

On the activity chart a bucket with `BH_F_CHG` (and data) has a faint `#2A2A2C` band behind the bars (the level chart's green bars already say it): its 2.5 px slice of the
plot (bucket i from `BHC_PX0 + 5 i / 2` to `BHC_PX0 + 5 (i + 1) / 2`), the plot's height, not below the axis.

Axis: level 100% / 50% / 0% (fixed text); activity "60 min" / "30 min" / "0" (`%d min` through the language's table).
Hour labels: four bucket boundaries (0..95) fall on local multiples of six hours; the zone's offset is read once, from
`localtime` at the open bucket (UTC quarter hours are quarter hours in every picker zone; a DST change inside the 24
hours is not followed). Label text is `HH:00` (level) or `HH` (activity) in 24-hour time and `6 PM` in 12-hour time; the
label is centred on the boundary's x (`10 + 12 + 5 * i / 2`) with `widget_move`.

**On Battery rows**: the mark, the title, the duration (rounded to the minute: `%d h %d min`, `%d h`, `%d min`) as the
grey second line, and at the right the bold white "~12%": the percent the gauge fell in that state (`d_*`, charging
buckets left out). Order: Screen On, Playing / Screen Off, Standby.

The page does not refresh while it stays open (it is read when it opens, comes back in front, or the switch turns); no
timer.
