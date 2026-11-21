# Card script runner

**Sources:** `tools/mod_cardrun.py`, `assets/cardrun/m1plus-run`, `patch/cardrun.c`, `patch/radio.c` (`rd_dac_take`, `cr_ext_yield` calls), `patch/relnotes.c`.

The stock rootfs has no network shell (no `telnetd`, `nc`, `tcpsvd` or dropbear) and the UART pads are
not located ([firmware](../firmware.md)). A look at the running system is therefore a shell script on
the card, started by hand from the Card Script page. Nothing runs at boot.

## Runner

`/usr/bin/m1plus-run` is the one file added (mode 755, pinned by SHA-256); no stock file changes.
It runs once, as root, in the foreground of its caller:

1. exits when `/mnt/mmc/m1plus-run.sh` does not exist, or when `/tmp/m1plus-run.pid` names a live process;
2. copies the script to `/tmp/m1plus-run.sh` (no file on the card stays open, so USB storage and Standby can unmount it);
3. writes `m1plus-run.pid` (its own pid, `$$`), removes `m1plus-run.exit`, and runs the copy with `/bin/sh` from `/`, stdin from `/dev/null`, output in
   `/tmp/m1plus-run.log`;
4. writes the exit status to `m1plus-run.exit` and removes the pid file.

The shell traps TERM with a handler, so that a signal to its group ends the script (default action
again after the exec) and the shell still writes `143` and removes the pid file.

- Writes nothing to the card or flash.
- The kill switch `/mnt/mmc/m1plus-off` is not read: the file is the switch (delete `m1plus-run.sh`
  to stop), and a script must run with the payload off too.
- No checks on the script: whoever can write the card root can run anything, as with `update.bin`.

## Developer page

Settings > Developer > Tools > **Card Script** (`m1plus_cardrun`, `patch/cardrun.c`) runs and stops
the runner by hand. Cards: **Status**; **Run Now** and **Stop**; **View Script** and **View Log**; then one note.
No row has a glyph. The page is a Developer tool: it is not in the Control Center or elsewhere. Strings are
`tools/pod_i18n.py`; `m1plus-run.sh` is a file name.

- **Live page**: while a run is alive the 500 ms timer (`cr_tick`, started by Run Now and by the page when it opens during a run)
  refreshes the page (`cardrun_refresh`, a no-op when the page is not open), and once more when the run ends.
  Status and rows follow without a tap.
- **Rows**: none is dimmed. One row, Run Now, reads `Stop` while a run is alive (`page_refresh` sets its `pod_label` text with
  `TR`, so it follows each refresh); a tap runs or stops accordingly. View Script and View Log are always tappable.
- **Status**: `Running m:ss` (the pid file names a live process, `kill(pid, 0)`; the time is now minus the pid file's mtime, `statx`,
  never negative), `No Script` (no `/mnt/mmc/m1plus-run.sh`), `Ready` (a script, no exit file), `Done` (exit 0),
  `Stopped` (exit 143 or 137) or `Failed (n)`.
- **Run Now**: `cr_spawn` forks twice. The UI process holds open files (the playing track, sockets,
  input devices), which a `system()` child would inherit and keep the card busy. So the first child
  forks the runner and ends at once (the UI reaps it with `waitpid`); the runner calls `setsid()`,
  closes descriptors 0 to 1023, reopens 0 to 2 on `/dev/null` and execs
  `/usr/bin/m1plus-run`. It is its own session and group leader, so its pid is its group. No toast on success
  (the status shows it); `Storage unavailable` when the fork fails; the toast `No m1plus-run.sh on the card` when there is no script.
- **Stop** (the Run Now row during a run): `kill(-pid, SIGTERM)`, then `kill(pid, SIGTERM)`; the tick shows the end.
- **View Script**: `m1plus_cardsrc` (`cardsrc_open`, `cardrun_src`), titled `m1plus-run.sh` (no painted heading), the same painter, text 15 px on a 20 px pitch (`RN_PITCH_CARD`): the first 16 KiB of the card's own `/mnt/mmc/m1plus-run.sh` (not the copy in `/tmp`), cut at a line end, at most the first 300 lines, with the log's ASCII cleanup; `No m1plus-run.sh on the card` when it is missing. Read once when the page opens. One reader (`cr_text`) serves both pages.
- **View Log**: `m1plus_cardlog`, a Release Notes page (`cardlog_open`, `rn_open`, the painter shared
  with the update notes and the Lock Screen instructions; body 15 px, 20 px pitch, no painted
  heading, the text starts at y 12). Text: the last 16 KiB of `/tmp/m1plus-run.log`, cut to start at a line
  boundary, at most the last 300 lines, plain ASCII (a tab becomes four spaces, another control byte a space, a byte above
  0x7e a `?`), or `No log yet` when the file is missing or empty. It is read once when the page
  opens (the stock navbar, Now Playing's button as on the script page); the page also opens scrolled to the end (`yoffset` set to the content height minus the 400 px view). The script and Release Notes pages keep their Now Playing button. The painter wraps lines at 288 px (a source line is cut at 600
  characters, 40 wrapped lines at most), so a 170-character line takes about five lines; a whole
  16 KiB tail fits the painter's tables (`RN_WIDE`, `RN_LINES`).

Limits:

- Stop is a SIGTERM: a script that ignores it keeps running (the status stays `Running`).
- `/tmp` is memory: a reboot clears the record and the log.

## External audio hold

A card script can play straight to the DAC with stock `aplay`. Run Now starts the 500 ms UI timer
(`cr_tick`, `m1_timer`-style `RET_REPEAT`); it runs while the script's process is alive or
`/tmp/m1plus-extaudio` exists, then ends itself. Files in `/tmp` (the protocol is fixed):

- `m1plus-extaudio`: the script wants the DAC; it creates the file and removes it when done.
- `m1plus-extaudio.ready`: the payload creates it once the DAC is readied for the hold, and removes it when the hold ends.
- `m1plus-extaudio.yield`: the payload creates it when local music or a station is about to start during a hold; the script kills its `aplay` and removes `m1plus-extaudio`. The payload removes it when the hold ends.

`cr_poll` (one tick): a want file that is new takes the DAC as q2-pod's librespot hand-over does
(`spot_take`, `spot_poll`, `spot_yield`; q2-pod, MIT, see README acknowledgements): a running station is
stopped (`rd_stop`), local music is stopped with `stop_player` unless `mclGetPlayStatus()` is 1, the
output is readied by `rd_dac_take` (patch/radio.c, the routine a station start uses), then `.ready` is created. While
held, each tick calls `reset_poweroptions_timer(1, 1, 0)` and clears a positive `dacoff_time`, as the
radio's poll does. When the want file is gone the hold ends: `.ready` and `.yield` are removed and
the DAC is left as it is.

`cr_ext_yield` runs at the start of the `mclStartPlayer` hook (`rd_start_player`, possibly off the UI
thread: no widgets, no timers) and of `rd_begin`, before the station readies the DAC. With the want
file present it creates `.yield` and waits up to 2000 ms (100 x 20 ms) for the file to go, then returns
whatever happened. Without a hold it is one `access`. No `hciplayer`, stock file, boot path or kill
switch is involved.
