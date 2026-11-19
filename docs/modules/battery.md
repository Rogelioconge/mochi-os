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
bar and in the pull-down's own bar. The fill is drawn under the image, so the image is the outline
and the fill lands inside.

Stock has no real number: `get_battery_capacity` buckets the battery voltage into 0/20/40/60/80/100
(another table while charging). The optional exact percentage below reads the gauge instead.

One drawing, two sizes: 1.5 px outline (the status-icon stroke), rounded body corners, a 2 px
rounded nub, 8x supersampled, written as a plain zlib PNG (bytes independent of Pillow).

| Look | Outline | Fill |
|---|---|---|
| Normal | white | white level |
| Charging | green `#34C759`, bolt with a 0.5 px black keyline | level |
| Low | red `#FF1448` | level |

| Place | Image | Fill | Right edge |
|---|---|---|---|
| Status bar and pull-down (`STATUS`) | 22x12 at (288, 9): body 20x12, nub 2x6, corner radius 3 | 16x8 at (290, 11) | x 310 as stock |
| Lock screen (`screens_battery/charge/lowbattery`) | same size, at (288, 12) on the date line | same, under the picture | same |

The right icon group ends 4 px before the image (its box is x 183..284). `fill_gap` asserts the
fill stays inside the outline.

## The percentage

**Setting:** Settings > Battery > **Battery Percentage**, a switch, **off by default**,
`/mnt/data/m1plus/battery-percentage` (`1` on; missing or anything else off; [settings](settings.md)).
On, the status bar shows the AXP2101 fuel gauge's charge as a number just left of the outline, and
the fill, the charging picture's fill and the pull-down's fill use the same value.

**Hook.** Stock's `show_sysbar_face` (the status bar's 1 s timer) calls `get_battery_capacity`,
drops the return value and draws from the global `power_capacity` the function leaves; the pull-down
reads the same global. The hook replaces the `jalr` of that call with `bp_capacity`. **Stock's
function runs first**, so its side effects (USB and charge state, power-option timers, RGB LED) are
untouched. Then, if the setting is on, `/mnt/mmc/m1plus-off` is absent and
`/sys/class/power_supply/battery/capacity` is a plain integer 0..100 (one to three digits and at
most one newline), the percentage is written to `power_capacity` and the label `pod_pct` shows
`N%`. Otherwise stock's value stays and the label is hidden. The platform_init and power-off calls
stay stock.

- **Charging:** stock adds 10 to `power_capacity` per call as a fill animation; with the setting on
  the real percentage replaces it every tick. The bolt picture stays stock's logic.
- **Cost:** setting off, one `access` and a cached flag (read once from the 1-byte file; a hand edit
  applies after a restart). On: one open/read/close of the gauge and three lookups per second. No
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

`pod_pct` is a hidden, insensitive `label` appended to the right icon group `view_bar_right` of
`ui/system_bar.bin`, before the Screenshot camera `pod_shot`. `pod_pct_dd` is the same in
`dropdown_dialog.bin` (the pull-down covers the real bar; it can show the number up to a second
after it opens). White, 13 px, right-aligned and vertically centred, its right edge 4 px before the
outline (x 284).

- The group's layouter skips an invisible child, so the label **makes room**: icons to its left
  move left by its width + 4.
- Width follows the text: `BP_W2` 18, `BP_W3` 25, `BP_W4` 32 px for `5%`, `87%`, `100%`
  (`pct_widths` in `tools/pod_ui.py`, written into `stock.h`). When it changes, the hook resizes the
  label and asks the group to lay out again.
- With Bluetooth, SyncLink, Wi-Fi and `100%` the ink starts at x 189, 3 px clear of the 12 h clock's
  end (186); the tests require at least 3 px, also with the Screenshot camera.

## The lock screen

Stock's lock page draws its gauge from the same `power_capacity`, so its fill and picture already
follow the percentage. Its label `pod_pct_lk` (`tools/mod_lockscreen.py`: a child of `view_timeinfo`,
so Show Time off hides it with the gauge; a fixed 32 px box, right-aligned) is set by the same tick
and by `bp_lock` at the page's init (`patch/lockscreen.c`, not with the kill switch), so the number
is there in the first frame. The pull-down's `pod_pct_dd` is set the same way by `bp_pulldown` at the
dialog's init (`patch/pulldown.c`, not with the kill switch). With the setting off or a bad gauge the
label stays hidden.
