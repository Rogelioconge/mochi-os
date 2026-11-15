# Payload safety

## Entry points

The entry points are the hooks in [payload](payload.md), which owns the inventory, each hook's
fallback and its boot reachability. Each is pinned, falls back to stock, and is a pass-through
while the palette is inactive (Black + Neutral) or `/mnt/mmc/m1plus-off` exists. Do not add global
paint or main-loop work outside that set.

Rules for adding a hook:

- **Pin every edit.** Check stock SHA-256, words, symbols, `$gp` and offsets before writing. A
  mismatch fails the build; a hook error falls back to stock.
- **Boot-reachable hooks are a paved path.** A new pinned prologue or call-site hook on a stock
  function that also runs at boot (such as `select_timezone` from `config_init`) needs no separate
  approval when it falls back to stock on the kill switch, invalid input or any error, and does
  only bounded work: no thread, timer, loop over files or network. Check boot reachability with
  `tools/reach.py` and list the hook in [payload](payload.md).
- **Treat startup as critical.** Home initialization needs the crash marker. Hooks that Memory
  Playback reaches at boot (the tag reader, `mclStartPlayer`, the library queries, the player's EQ
  filter) run stock's work first or pass through, and touch nothing else. The EQ filter reads one
  flash file per track and passes DSD and the kill switch through; `mclStartPlayer` with no radio
  running is one comparison.
- **Keep each hook inside its scope.**
  - Tidal-icon recovery applies only while `/mnt/data/m1plus-bad` exists.
  - Home's ready path changes the language's CJK cmap field and the glyph-cache size, repeated by
    a timer after language or theme changes ([home-guard](home-guard.md), [fonts](fonts.md)).
  - Podcast tags apply only under `/mnt/mmc/Podcasts/`, after stock's path copy.
  - Library query hooks rewrite only the documented songtable / myfav cases and pass other SQL
    untouched; album queries use track order so the first track supplies the row and cover.
  - The scan hook skips dot-folders (not on the boot path).
  - The battery hook runs stock first from the first status refresh. Only an enabled percentage
    setting changes capacity and label, and only a set Charge Limit writes the charger switch,
    releasing only its own hold ([charging](charging.md)). With both off it adds one `access` and
    two cached flags.
  - Now Playing's paint work stays on the cover widget; More work stays on init, More and back
    taps and covering-dialog handling.
  - The pull-down hook runs stock's init first, then moves, shows and hides the tiles and captions
    once. Before stock's init it writes the two "inside settings" flags (`syssetinto_flag`,
    `playsetinto_flag`) from the window stack.

## Kill switch

`/mnt/mmc/m1plus-off` disables the payload on the path rollback needs only: the menu entry and
boot guard (`m1plus.c`, `home.c`), boot-reachable hooks, and hooks that run on every screen
(paint, status bar, list gesture). The list-gesture hook reads it once per session. Hooks on
tap-only stock screens (Now Playing, More dialog, pull-down, library rows, Radio Now Playing) and
everything reached from the menu do not check it and rely on their stock fallback.

## Widgets and windows

- **Preserve widget names.** Restyle, move or hide widgets the application looks up; never rename
  or delete them. Hide with both `visible=false` and `sensitive=false`; decorative overlays must be
  insensitive ([ui-rules](ui-rules.md) has the hit-test evidence).
- Normal windows are 450 px below the status bar; fullscreen windows are 480 px.
- Feature timers, workers and paint events stay owned by their page and follow its lifetime. The
  one exception is the radio engine's 500 ms timer: it lives from a station's start to its stop,
  error or hand-over, holds standby and the DAC timer, and ends itself ([radio](radio.md)).

## Updates

Only kernel and rootfs are packaged. Never write the bootloader or recovery kernel. The rebuilt
rootfs must not exceed stock size.
