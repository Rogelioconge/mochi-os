# Payload safety

## Entry points

Entry points = the hooks in [payload](payload.md) (inventory, fallbacks, boot reachability). Each is
pinned, falls back to stock, and passes through while the palette is inactive (Black + Neutral) or
`/mnt/mmc/m1plus-off` exists. No global paint or main-loop work outside that set.

Adding a hook:

- **Pin every edit.** Check stock SHA-256, words, symbols, `$gp`, offsets before writing. Mismatch
  fails the build; a hook error falls back to stock.
- **Boot-reachable hooks are a paved path.** A new pinned prologue or call-site hook on a stock
  function that also runs at boot (e.g. `select_timezone` from `config_init`) needs no separate
  approval if it falls back to stock on kill switch, invalid input or any error, and does only
  bounded work (no thread, timer, file loop, network). Check reachability with `tools/reach.py`;
  list the hook in [payload](payload.md).
- **Startup is critical.** Home init needs the crash marker. Hooks Memory Playback reaches at boot
  (tag reader, `mclStartPlayer`, library queries, player EQ filter) run stock's work first or pass
  through, and touch nothing else. EQ filter: one flash file read per track; passes DSD and kill
  switch through. `mclStartPlayer` with no radio running: one comparison.
- **Keep each hook in scope:**
  - Tidal-icon recovery: only while `/mnt/data/m1plus-bad` exists.
  - Home ready path: changes the language's CJK cmap field and glyph-cache size, repeated by a timer
    after language or theme changes ([home-guard](home-guard.md), [fonts](fonts.md)).
  - Podcast tags: only under `/mnt/mmc/Podcasts/`, after stock's path copy.
  - Library query hooks: rewrite only the documented songtable / myfav cases, pass other SQL
    untouched; album queries use track order so the first track supplies row and cover.
  - Scan hook: skips dot-folders (not on the boot path).
  - Battery hook: runs stock first from the first status refresh. Only an enabled percentage setting
    changes capacity and label; only a set Charge Limit writes the charger switch, releasing only its
    own hold ([charging](charging.md)). Both off: one `access` and two cached flags.
  - Now Playing paint work: cover widget only. More work: init, More and back taps, covering-dialog
    handling.
  - Pull-down hook: runs stock's init first, then moves/shows/hides tiles and captions once. Before
    stock's init it writes the "inside settings" flags (`syssetinto_flag`, `playsetinto_flag`) from
    the window stack.

## Kill switch

`/mnt/mmc/m1plus-off` disables the payload only on the path rollback needs: menu entry and boot guard
(`m1plus.c`, `home.c`), boot-reachable hooks, hooks on every screen (paint, status bar, list
gesture; the list-gesture hook reads it once per session). Hooks on tap-only stock screens (Now
Playing, More dialog, pull-down, library rows, Radio Now Playing) and everything reached from the
menu do not check it; they rely on stock fallback.

## Widgets and windows

- **Preserve widget names.** Restyle, move or hide looked-up widgets; never rename or delete. Hide
  with `visible=false` and `sensitive=false`; decorative overlays insensitive ([ui-rules](ui-rules.md)).
- Normal windows 450 px below the status bar; fullscreen 480 px.
- Feature timers, workers and paint events belong to their page and follow its lifetime. Sole
  exception: the radio engine's 500 ms timer lives from station start to stop, error or hand-over,
  holds standby and the DAC timer, and ends itself ([radio](radio.md)).

## Updates

Package only kernel and rootfs. Never write the bootloader or recovery kernel. Rebuilt rootfs must
not exceed stock size.
