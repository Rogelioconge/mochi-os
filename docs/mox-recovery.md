# MOX OS — Home recovery milestone (Sprint 5)

This milestone does **not** bypass stock `home_page_init` and does not enable the dormant `mox_boot_candidate`. The original Shanling grid is still constructed first.

The **real** `home_menu_opened` C callback must complete `hm_fill_window` before the grid may remain hidden. When the navbar, the required list, its scroll view, or any of the 26 menu rows are absent, the guard restores the original grid, disables reopening for this session, persists `BAD_NOTE`, saves Start-in Shanling, and removes `MARKER` only after the failure note is durable. A failed note write deliberately leaves the marker: a reboot then falls back rather than repeatedly starting MOX.

`hm_open` also refuses to treat a zero return from `m1plus_open_entry` as sufficient proof unless the callback confirmed readiness. `home_restore` resets this proof before each new attempt.

## Remaining safety work before native cutover

- **Sprint 6:** the five-second timer is now a deadline gated by AWTK `EVT_AFTER_PAINT` on the correct window. Missing paint triggers Shanling recovery; this proves a toolkit paint dispatch, not actual panel pixels or touch responsiveness (see `docs/mox-boot-proof.md`).
- `mox_boot_candidate` is read-only and unused. Native bypass is not activated; the stock grid still exists.
- Native test harnesses validate C logic; MIPS emulator tests on the developer's Mac and device tests are separate, mandatory gates.
- No `update.bin` is produced in this sprint. Do not flash based solely on this milestone.
