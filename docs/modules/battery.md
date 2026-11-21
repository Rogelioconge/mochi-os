# The battery art

**Sources:** `tools/battery_art.py`, `tools/mod_battery.py`, `tools/statusbar.py` (art);
`patch/battery.c`, `patch/battery.h` (percentage; hook 8 in [payload](payload.md)); `BATTERY_PINS`
in `tools/pod_pins.py`.
The [Charge Limit](charging.md), [Battery History](batthist.md) and the
[automatic scrobble upload](scrobble.md#automatic-upload) run on the same status bar hook,
independently of the Battery Percentage setting. The Charge Limit also has a worker thread of its
own, which covers the screen off and stock's standby.

## One battery

The app swaps `img_battery`'s image between `bar_power`, `bar_charge` (charging) and `bar_lowpower`
(capacity 0 only) and feeds `pgbar_battery` the capacity (100 when charge is done), in the status
bar and in the pull-down's own bar. The fill is drawn under the image, so the image is only the
body's rim and nub, and the fill (white level on the body's grey) lands inside.

Stock has no real number: `get_battery_capacity` buckets the battery voltage into 0/20/40/60/80/100
(another table while charging). The optional exact percentage below reads the gauge instead.

The look is iOS's solid battery: one grey body with the level in white, 14 px tall like the other
status glyphs ([icons](icons.md)). Under `pgbar_battery` the view `pod_bat_bg` fills the body's
interior (inset 1 px) with `EMPTY` `#5A5A5A`; the bar draws the level in white over it (its own
background is transparent); the image is the 1 px rim (its inner corners rounded too, covering the
fill's square corners) that rounds the body's corners, the nub, and while charging a bolt right of
the nub (the body's middle belongs to the number). The picture has no pixel outside these, so it
sits on any background (the lock screen's wallpaper). 8x supersampled, written as a plain zlib PNG (bytes independent of Pillow).

| Look | Rim and nub | Inside |
|---|---|---|
| Normal | grey `#5A5A5A` | white level |
| Charging | green `#34C759`, a green 6x10 bolt right of the nub | white level |
| Low | red `#FF3B30`, a 3 px red sliver at the level's left end | grey (the level is 0) |

| Place | Image | Fill | Right edge |
|---|---|---|---|
| Status bar and pull-down (`STATUS`) | 36x14 at (282, 8): body 26x14, nub 1.6x5, corner radius 4, then the bolt's 8 px (`tail`) | 24x12 at (283, 9) | the nub at x 310 as stock, the bolt in the bar's margin |
| Lock screen (`screens_battery/charge/lowbattery`) | same size, at (282, 11) on the date line | same, under the picture | same |

The right icon group ends 5 px before the image (its box ends at x 277).

## The percentage

**Setting:** Settings > Battery > **Battery Percentage**, a switch, **off by default**,
`/mnt/data/m1plus/battery-percentage` (`1` on; missing or anything else off; [settings](settings.md)).
On, the status bar shows the AXP2101 fuel gauge's charge as a number in the battery, and
the fill, the charging picture's fill and the pull-down's fill use the same value.

**Hook.** Stock's `show_sysbar_face` (the status bar's 1 s timer) calls `get_battery_capacity`,
drops the return value and draws from the global `power_capacity` the function leaves; the pull-down
reads the same global. The hook replaces the `jalr` of that call with `bp_capacity`. **Stock's
function runs first**, so its side effects (USB and charge state, power-option timers, RGB LED) are
untouched. Then, if the setting is on, `/mnt/mmc/m1plus-off` is absent and
`/sys/class/power_supply/battery/capacity` is a plain integer 0..100 (one to three digits and at
most one newline), the percentage is written to `power_capacity` and the label `pod_pct` shows
the number. Otherwise stock's value stays and the label is hidden. The platform_init and power-off calls
stay stock.

- **Charging:** stock adds 10 to `power_capacity` per call as a fill animation; with the setting on
  the real percentage replaces it every tick. The bolt picture stays stock's logic.
- **Cost:** setting off, one `access` and a cached flag (read once from the 1-byte file; a hand edit
  applies after a restart). On: one open/read/close of the gauge and a few lookups per second. No
  allocation, timer or thread. The hook first runs when the UI starts, not at boot.
- **Accuracy** is the AXP2101's own estimate.

## The wake repaint

The framebuffer is blanked while the screen is dark (`disable_fb`), so what the UI draws then never
reaches the panel. Two call-site hooks in stock's `screen_action` (`0x4e71a4`, every backlight
change: the idle timeout, the power key) repaint on wake. The `jalr toolSetBackLight` words at `0x4e71cc`
(on) and `0x4e71fc` (off) become `jal bp_light_on` / `jal bp_light_off`. Off sets a flag (`bp.dark`)
and calls `toolSetBackLight`. On, when the flag is set and `/mnt/mmc/m1plus-off` is absent, first runs
`show_sysbar_face(0)` (the bar's own timer call, so the labels follow), then marks the whole window
manager dirty (`widget_invalidate_force`), lays it out and paints it as the main loop does
(`window_manager_check_and_layout`, then `window_manager_paint`; a label whose width changed has asked
its group to lay out again), clears the flag and
calls `toolSetBackLight` with the same argument. So the first frame the panel shows is a fresh one.
**Cost:** about 34 ms on a wake (measured on the device), nothing while the screen stays lit (the
flag is clear, so a second on paints nothing). With the kill switch present both hooks are a plain
`toolSetBackLight` call.

## BP_LOW

Stock chooses `bar_lowpower` only for `power_capacity <= 0`, re-sets the picture every tick, and
only on the path that is not the charging or full picture. The readers of 0 (the power-off page's
low-battery screen, the on-device update and OTG refusals) never shut down or open a page.

- **With the setting on, `power_capacity` is stored as 0 at a gauge reading of 5% or less on
  battery** (`BP_LOW`), and whenever stock's own bucket is 0 (never later than stock). These are
  stock's low-battery behaviours, now from 5% instead of below 3.535 V.
- The hook mirrors stock's test and stores 0 only when stock would reach it, so a charging battery
  keeps the real value.
- The label always shows the real number. A fill of 0 is empty (5% of 16 px is under 1 px).

## A zero gauge

An uncalibrated AXP2101 gauge can read `0` while the battery is healthy (issue 19: a full stock
battery, a red `0%` with the setting on). The driver returns the gauge register as it is, so on a
`0` `battery_gauge` also reads `/sys/class/power_supply/battery/voltage_now` (`BP_VOLT`, µV, the file
stock's `toolsGetBatteryVoltage` reads). It believes the `0` only below `BP_EMPTY_UV` (3535001,
stock's own bucket-0 level). A higher or unreadable voltage makes the reading unreadable (`-1`).
`power_capacity` is no witness: while charging it holds stock's +10 animation, which wraps to 0.
On `-1` the setting keeps stock's look with the label hidden, the [Charge Limit](charging.md)
releases a hold of its own, and [Battery History](batthist.md) records the level as unknown. A
charging battery's voltage is above the empty level, so a real 0 while charging is hidden too.

## The label

`pod_pct` is a hidden, insensitive `label` over the battery's body in `ui/system_bar.bin`, drawn
after `img_battery` (`battery_parts` in `tools/statusbar.py`). `pod_pct_dd` is the same in
`dropdown_dialog.bin` (the pull-down covers the real bar; it can show the number up to a second
after it opens). The number has no `%`: black, 15 px in the bold face (`lyrics`), centred in the
26x14 body, so `100` fits and nothing in the bar moves when it shows. The label's box is 15 px high
and 1 px below the body's top (`PCT_DY`): AWTK centres the whole line, and the digits have no
descender, so this centres their ink.

- **No inversion.** The digits are black over the white level and over the rest of the body alike.
  For that the rest must be light: the hidden view `pod_pct_bg` (`EMPTY_PCT` `#8E8E93`, drawn
  between `pod_bat_bg` and the level) is shown together with the label. With the setting off the
  body keeps the darker `EMPTY`, which sets the level off better when there is no number.
- **Charging** keeps the number: the bolt is right of the nub, not in the body.
- The contrast scan (`tools/mod_theme.py` `DRAWN_OVER`) rates the digits against `EMPTY_PCT`.

## The lock screen

Stock's lock page draws its gauge from the same `power_capacity`, so its fill and picture already
follow the percentage. Its label `pod_pct_lk` and grey `pod_pct_bg_lk` (`tools/mod_lockscreen.py`:
the same `battery_parts`, children of `view_timeinfo`, so Show Time off hides them with the gauge) are set by the same tick
and by `bp_lock` at the page's init (`patch/lockscreen.c`, not with the kill switch), so the number
is there in the first frame. The pull-down's `pod_pct_dd` is set the same way by `bp_pulldown` at the
dialog's init (`patch/pulldown.c`, not with the kill switch). With the setting off or a bad gauge the
label stays hidden.
