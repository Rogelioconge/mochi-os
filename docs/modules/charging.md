# Charge Limit

**Sources:** `patch/charging.c`, `patch/charging.h`, `patch/power.c`, `patch/power.h`, `patch/battery.c`. **Tests:** `test/pod/charging.py`, `test/pod/power.py`.

Settings > **Battery** (with Battery Percentage, first on the page) > **Charge Limit** pauses charging at 80, 85, 90 or 95 %
while the player runs; 100 % (the default) is no limit. Charging resumes 5 points lower.
Powered-off charging and the status bar's charging picture stay stock's. The art and the
percentage are in [battery](battery.md).

## Behaviour

Two callers run the same check (`chg_step`), serialised by a spin lock:

- `chg_tick` on the status bar's 1 s tick: the Battery Percentage hook `bp_capacity`
  (`patch/battery.c`, [payload](payload.md) hook 8) calls it after stock's `get_battery_capacity`,
  with the kill switch result and the gauge when Battery Percentage already read it. It only
  try-locks, so a tick is skipped while the worker checks. A check runs at most every
  `CHG_PERIOD` (5) seconds of `time()`; a clock that went back checks at once, and a new limit
  checks at the next tick.
- `chg_main`, one detached worker thread: a check every `CHG_PERIOD` seconds with `sleep`. It covers the screen off and stock's
  standby (userspace still runs; `show_sysbar_face` does not tick), independently of the Battery History setting. `chg_tick` and `chg_set` start it
  (once; a failed `pthread_create` is retried after 30 ticks) while a limit under 100 is set; it
  ends when the limit is 100 or the kill switch is there. The worker holds (`0`) and forgets a
  hold that stock's DAC mode owns, but never writes `1`: every release is `chg_tick`'s, on the UI
  thread that also runs stock's DAC toggle and USB page, so the ownership test and the `1` cannot
  straddle the user's change. With the screen off a release waits for the next tick. The worker's
  checks never move the tick's `CHG_PERIOD` deadline, and a release it leaves to the tick makes the
  next tick check at once, so the worker cannot postpone a release.

With no limit and no hold nothing runs: a cached compare, no thread.

A check reads the AXP2101 gauge (`/sys/class/power_supply/battery/capacity`, `battery_gauge`;
stock's `power_capacity` is a voltage bucket) and writes the driver's charging request
`/sys/class/power_supply/battery/charger` with `open` / `write` / `close` (no shell):

| State | Action |
|---|---|
| External power (see below), not held, gauge >= limit | write `0`: our hold |
| Held, gauge <= limit - 5 | write `1`: release |
| Held, in between | read the switch; anything but `0` (stock enabled charging: the USB page's exit `0x545988`, the DAC toggle) writes `0` again |
| Stock's USB DAC mode with charging off (`POWER_USBSTATE` 2, `POWER_FLAG` 1, `usbdac_chargeflag` 0: the same test as `show_sysbar_face`'s picture) | nothing written; a hold is forgotten (stock wrote `0` and its exit writes `1`) |
| Limit 100, `/mnt/mmc/m1plus-off`, no external power, unreadable gauge | release a hold of ours |

`1` is only ever written after our own `0`, and every release (limit 100, kill switch, unplug,
bad gauge, resume level) first checks the DAC state: while stock owns the switch the hold is only
forgotten, so the user's USB DAC charging-off choice is never overridden. A failed write keeps the old state and is retried at the next check (the kill
switch's release at every tick). A reboot resets the driver's disable flag.

The setting is `/mnt/data/m1plus/battery-charge-limit`, one character `0`..`3` = 80..95 %;
anything else or missing is 100 % ([settings](settings.md)). `chg_limit` caches it;
`chg_set` (the picker) saves atomically and then applies. The pages are `m1plus_battery`
(the Charge Limit value row, `ACT_CHGLIM` 80, Lucide `battery-medium`, note "Applies while the
player is on") and the picker `m1plus_chargelimit` (`ACT_CHGLIMSET` 81, arg = the limit,
note "Resumes a little below the limit"); the Settings row is Lucide `battery-full`.

Not covered: a real kernel suspend. No userspace runs then, so a limit crossed meanwhile is held
only after the wake (a hold stays, a release waits). `show_sysbar_face` returns early while
`standby_mode` (`0xa059e0`) is 2, which the worker's holds do not depend on (its releases wait for the screen); external power normally keeps
`to_poweroptions` (`0x4ce5a8`) from that standby.

## External power

`pwr_external` (`patch/power.c`, `patch/power.h`) is the one reading shared by the
Charge Limit and [Battery History](batthist.md). It looks at every source; **any source saying
external wins**, else any saying battery, else unknown (-1):

| Source | External | Battery |
|---|---|---|
| `battery/status` (`PWR_STATUS`) | `Charging`, `Full`, `Not charging` | `Discharging` (`Unknown`, empty, unreadable: no answer) |
| `/sys/class/power_supply/usb/online`, `.../ac/online` (fixed paths; the stock kernel registers a `battery` supply only, so they may not exist) | `1` | `0` |
| PD17 raw level | ioctl returns 0 | ioctl returns 1 (a failed ioctl or a device that does not open: no answer) |

The PD17 read repeats stock's `usb_detect` (`0x4d6f30`, which `get_battery_capacity` calls to refresh
`POWER_EXT`): `open("/dev/gpio", O_RDWR)`, `ioctl(fd, 0x2000477a, "PD17")`, `close`, as libhardware2's
`gpio_open` (`0x556c`) and `gpio_get_value` (`0x57bc`) do; a read of an input line, nothing written,
without stock's `toolsGpioGetValue` mutex (it only serialises stock's own callers). `BATTERY_PINS`
pins the `usb_detect` words and the build (`check_gpio_lib` in `tools/pod.py`) pins libhardware2's
symbols and words and the `"PD17"` string.

The Charge Limit counts external power when `POWER_EXT` is 1 **or** `pwr_external` is 1. Stock's
`get_battery_capacity` is never called from a worker.

## Interfaces

Only the `POWER_*` / `USBDAC_CHARGEFLAG` words are pinned (by Battery Percentage).

| Interface | Evidence |
|---|---|
| `battery/charger` | `0` sets the driver's disable flag and zero charging current; nonzero restores the configured runtime current. Its read is the inverse of the disable flag, not a current measurement |
| `toolsSetChargeSwitch(int)` `0x5ec2c8` | stock's writer: `echo %d > .../charger` through `system` |
| `toolsGetChargeStatus()` `0x5e37a0` | `battery/status`: Charging 1, Full 2, else -1; `get_battery_capacity` stores only 0..2 in `pmucharge_status` (`0xa059e8`), so that word can be stale |
| USB DAC charging choice | `usbdac_chargeflag` `0x97cae8`; handlers `0x473960`, `0x528cb4`; USB page `0x545f24` (on) / `0x545ff8` (off), exit `0x545988` (on). Stock's toggle also writes `0x1600` / `0x1605` to `/sys/class/axp/axp_reg` (register `0x16`, USB input current); the limit does not |

In the kernel, `charger` `0` sets the driver's disable flag (kept across suspend and resume, not
across reboot) and nonzero restores the runtime current (DT `x-powers,axp2101-power-supply`: 1000 mA,
termination 100 mA, 4350 mV, USB input limit 2000 mA, unchanged).

q2-pod (`patch/system.c` `charge_poll`) stops at 80 % and resumes at
75 % from a 5 s main-loop poll on the Q2's active-low GPIO PE22. Neither that poll (outside
[safety](safety.md) scope) nor its GPIO or addresses apply to the M1 Plus.
