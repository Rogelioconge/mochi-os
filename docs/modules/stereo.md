# Mono Audio and Crossfeed

**Sources:** `patch/stereo.h`, `patch/stereo.c` (the stage and the record reader), `patch/peq_player.c` (where it runs, `peq_seteq_flag`),
`tools/mod_player.py` (the hciplayer edits), `patch/stereoset.c` (demo: settings, effective record, player notice), `patch/playset.c` rows via `patch/m1plus.c`, tests `test/pod/stereo.py`, `test/pod/playset.py`.
The crossfeed is Boris Mikhaylov's bs2b (libbs2b 3.1.0, MIT): the one-pole designs, the level arithmetic and the three settings are his,
rewritten for float blocks (acknowledged in the README and in the file headers).

## Behaviour

- **Mono Audio:** L = R = (L + R) / 2, on every output, **before** the EQ cascade (per-side EQ bands still apply to the downmix).
- **Crossfeed:** each channel gets the other, low-passed and attenuated, its own highs boosted, the sum scaled back (bs2b), **after**
  the EQ. Levels as bs2b names them: Low 650 Hz / 9.5 dB ("jmeier"), Medium 700 Hz / 6.0 dB ("cmoy"), High 700 Hz / 4.5 dB (bs2b's
  default). The player plays the level the record says; whether crossfeed applies to the current output (headphones and Bluetooth, not
  Line Out or USB DAC) is demo's decision and the record holds the effective level ("Settings and the record").
- Stereo only (`nch == 2`; one channel or more than two: nothing), float domain, 8-384 kHz. Never for DSD, a special format, a rate past
  the range or with the kill switch `/mnt/mmc/m1plus-off` (the filter passes those through, as before).
- Everything off is bit-exact: both stages return before touching a block; Equalizer off with both off passes the native format (below).
- A change while playing (the next channel-0 gain command rereads the record) moves linear weights over 20 ms (`rate / 50` frames):
  mono is `L + (M - L) * w`; crossfeed is `dry * (1 - sum w) + sum w * wet` over two filter slots. A level change crosses over from the
  old slot to a new one that starts from the old one's memory; changes asked faster than a ramp wait for a free slot (latest wins).
  A filter that has faded out is cleared. A non-finite input sample counts as 0 in either stage.
- Coefficients: bs2b's, with `exp(x)` as `pow(e, x)` and `2^(-20 log10(G) / 12)` as a power of G, so
  `Fc_hi = Fc_lo * 2^(GB_lo / 12) * G_hi^(-0.50171665944)` (no new libc import). The `+ 1e-18 - 1e-18` flush keeps the tails out of denormals
  (the MIPS FPU traps on them); it leaves a ~1e-34 floor.

## The record

`/mnt/data/m1plus/playback-stereo` (`STEREO_FILE`), 16 bytes, little endian: `"M1STR01\0"` (8), `int mono` (0 or 1), `int crossfeed`
(0 off, 1 Low, 2 Medium, 3 High). The player reads it with `fopen/fread` at each REINIT (`stereo_load`) and at each channel-0 gain
command. A missing, short, long, bad-magic or out-of-range record (either field) is **both off**. demo writes it whole (tmp, fsync,
rename, creating the folder), like `playback-eq`; the header `patch/stereo.h` is shared (`stereo_record`).

## The player

`stereo_pre` runs before `peq_process`, `stereo_post` after it, in `play`. State is per instance (`player_state.st`, heap); the payload
has no `.bss`. **Gapless join:** an instance that played its track out leaves the whole stage in `carry` next to the EQ's (`stereo_carry`: the Mono
weight, both crossfeed slots with their weights and filter memory), under the shared guards (track ended, under 3 s, same rate and channels,
finite). The next instance takes it on its first block and keeps what its own record asks, so a ramp cut short by the track's end finishes
in the next track, and a setting changed at the join ramps or crosses over instead of jumping. The two carries are independent: the EQ's
still needs a settled, equal curve; the stage's does not (`carry.eq`, `carry.st`).

**EQ off keeps the filter** ([peq](peq.md) "The player": `peq_seteq_flag`, `SETEQ_CALL` `0x42cd1c`): stock removes the filter when the
Equalizer switch is off (flag 0 → `0x42929c`). The patched `strtol` call answers 2 for an off flag, so stock takes its flag-2 path
(`0x42ce00`, disassembled: log, `0xb10df0` = 2, back to the loop) and the loop adds the filter at each file and sends GAIN SET. With
`eq_off` the curve is bypassed (`effective()`); REINIT with both options off (or a track that is not stereo) passes the native format and
every block through (`pass_native`), so playback is stock's bit for bit. One exception: a gapless join whose carried stage still has a
weight above 0 (an option switched off just before the track's end) makes the next instance filter in float, finish the fade, then leave
every sample alone for the rest of that track (`stereo_carry_live`). With an option on it asks for float and only the stereo stage runs.
When the filter must leave native pass-through (EQ switched on, or an option switched on with EQ off) `peq_seteq_flag` calls stock's removal
`0x42929c` once on `mpctx + 0x40` and marks the replacement (`replaced`, taken by the next `peq_open` as `ramp_in`): until that instance
has played a block, its REINIT starts the stage at weight 0 (`stereo_reset` `ramp`), so the option ramps in over 20 ms from the untouched
signal like any change while playing. Every other new instance (a track's start) plays what the record asks from its first frame.
The kill switch gets stock's own flag back.

## Pins and sizes

`tools/mod_player.py`: `SETEQ_CALL` (`0x42cd1c`, `0x0c2b6b84` → `jal peq_seteq_flag`), the neighbours of the call and of the flag-0, flag-1
and flag-2 paths, the removal `0x42929c` and its chain read, the insert state `0xb10df0` loads and stores (`0x4224e0..0x4224ec`,
`0x42f438`, `0x42fbd4`), the `strtol` stub `0xadae10` and its GOT slot `0xaf98e8` (checked against `.rel.plt`); every pin fails the build on
a mismatch. libc: `strtol` is the only addition. The payload grew from 12632 to 16200 bytes (`manifest.json` `payload_len`).

## Validation and limits

`test/pod/stereo.py` runs the compiled player under Unicorn: the record reader, the downmix (exact), the crossfeed impulse response at
44.1/48/96/192 kHz for each level against a Python model of libbs2b (and the closed-form low-pass and high-boost responses, the -3 dB
corner and the feed level at DC), ordering with the EQ, the ramps (models), DSD / kill switch / out-of-range / other channel counts,
all-off bit-exactness (EQ on Flat, EQ off native), gapless carry (settled and mid-ramp), the ramp-in of a replacing instance, the flag takeover and the removal call, and the pins.

## The UI

Settings > Playback Settings (`m1plus_playset`), Volume card, directly after Channel Balance ([playset](playset.md)): **Mono Audio**, a switch row (`ACT_MONO` 145, glyph `volume`), and **Crossfeed**, a value row (`ACT_XFEED` 146, glyph `headphones`, grey value Off / Low / Medium / High) opening the picker `m1plus_psxfeed` (`PSXFEED_PAGE`, the last page number; rows `ACT_XFEEDSET` 147 with arg 0..3, a check on the chosen one) built like `m1plus_psrg`. Under the picker's card a two-line grey note: "For headphones and Bluetooth. Not applied to Line Out, USB DAC or DSD." Neutral greys and white only. The Off / Low / Medium / High texts reuse existing keys; "Mono Audio", "Crossfeed" and the note are new in all 13 languages (`tools/pod_i18n.py`; fr, de, es, it, pl keep "Crossfeed", `SAME_AS_ENGLISH`; ru and uk say "Не для ..." / "Не для ..." in the note to fit two lines). The value row shows the level the user chose, also on Line Out (where the player's effective level is 0).

## Settings and the record

The user's choices are ours (not stock's): `/mnt/data/m1plus/playback-mono` (`1\n` on; missing or anything else off) and `/mnt/data/m1plus/playback-crossfeed` (`0\n`..`3\n`; missing or anything else off), written with `home_write_atomic`. A failed save returns -1 and changes nothing (no toast, as the neighbouring rows). Choosing the level already set writes nothing. Both are rows 46 and 47 of `SETTING_FILES` / `sf_files` (Settings Files, per-file delete, Reset All Settings; `INFO_SFOLD` is `INFO_SF + 52`, `INFO_DUR` 68). The effective record `playback-stereo` is derived and not listed; Reset All Settings removes it with the folder.

`stereo_sync(output, notify)` (`patch/stereoset.c`) computes the effective state: mono = the setting on every output; crossfeed = the setting when `peqout_current()` is Headphones (jacks and Bluetooth, way 1), 0 on Line Out and USB DAC. It compares with the record on disk (read by the player's own rules; a missing or damaged record counts as both off) and writes it whole (tmp, fsync, rename, folder made if missing) only when it differs, so both off with no record writes nothing and a fresh device is untouched. After a write with `notify` it calls `set_equalizer_value(equalizer_mode)`; the record is always in place before that call. A failed write leaves the state dirty and the next call retries; the player is not told then.

**Where it runs:** at the top of `peqout_sync` (after its kill-switch check, once `peqout_current()` is known), so only where peqout already runs: the status bar timer (`notify` 1, within a second of a jack or DAC change), stock's `save_start_player` and `mclStartPlayer` hooks (`notify` 0, the player thread) and the Equalizer page's calls. No new hook, no timer, nothing new on the boot path. Early exit: the output equals the one the record was made for and nothing is dirty (one `mclGetOutputWay` and a byte read). With `notify` 0 (player thread) the record is written and **no** command is sent: those calls come just before a track starts or restarts, and the player reads the record at REINIT. (peqout also sends from there only when its switch changes; the stereo record needs no such case.) A setting change calls the same function with `notify` 1 on the UI thread. With `/mnt/mmc/m1plus-off` present nothing is written or sent; the dirty state is applied when the switch is gone. A busy flag keeps two threads from writing at once (the loser leaves the state dirty).

## Verified in the stock binaries

Static reading of the pinned hciplayer (SHA `a6450374...`) and demo; not run.
- `set_equalizer_value` (`0x4d851c`): when `equalizer_mode - 1 < 11` it builds the ten gains and calls `mclSetEq` (`0x5d2b28`) with the flag argument 0 when `equalizer_flag` (`0xa05ac2`) is 0 (`0x4d85e0..0x4d8608`, `sw $zero, 0x28($sp)`), else 1 or 2 by `mclGetPlayStatus`. It is not "nothing" with the switch off. `mclSetEq` formats `{mcl-seteq\%f|...(ten)|%d}` (`0x756564`, the last field is the flag) and writes it to the mcl fd (`0x5d2c04..0x5d2c34`); its only early exit is flag 1 with a zero byte at `0xa10000 - 0x5476`, which flag 0 skips. A mode outside 1..11 sends nothing (`config_init` clamps it).
- hciplayer, `mcl-seteq` with flag 2 (what flag 0 is now answered as): `0x42ce00` logs, then `0xb10df0` = 2 and back to the loop (`0x42bf10`). The playback loop (`0x42f434..0x42f43c`) takes state 2 to `0x42fa68`; the 48 kHz test there is patched to always continue (`RATE_GATES`), `0x42fbc4` calls `0x4291cc` (finds "equalizer" in `mpctx + 0x40`, adds it with `0x44cc88` if missing) which sends `AF_CONTROL_EQUALIZER_GAIN | SET` (`0x40001d00`) for channels 0..7 (`0x4291f4..0x429264`, `a1 = 0x40001d00`, the gains at `0xb10df4`), then stores state 1 (`0x42fbd4`). Nothing on this path reads the Equalizer switch (stock's flag 0 only differs in the removal `0x42cd54`). At each file start `0x4224e0..0x4224ec` turns state 1 into 2, so the filter is added and GAIN SET sent again for every file. One gate sits before it: with `0xb10de4` in {5, 10, 12, 13} and `0xb10e3c` = 1 the loop skips the insert up to three times (`0x42f3f8..0x42f428`, `0x42fc38`, counter `0xb10d50`), independent of the switch. All holds as phase 1 assumed; what remains unverified is the live behaviour (below).

## Tests

`test/pod/stereo.py`: the player under Unicorn (record reader, downmix, crossfeed impulse responses at 44.1/48/96/192 kHz against a Python model of libbs2b, ordering with the EQ, the ramps, DSD / kill switch / other channel counts, all-off bit-exactness, gapless carry (settled and mid-ramp), the ramp-in of a replacing instance, the flag takeover and the removal call, the pins) and `settings_tests` for demo's side: a fresh device writes nothing on any output; the effective record for Headphones, Line Out, USB DAC and Bluetooth (way 1) with and without Mono; the record written before the player is told; not rewritten when unchanged; Headphones -> Line Out -> Headphones; notify 0 writes without sending; a level changed on Line Out; stale, damaged and equal records; damaged setting files (off); the kill switch; failed record and failed setting saves; `save_start_player`. `test/pod/playset.py` `stereo_rows_tests`: rows, order, kinds, glyphs, 13 languages, picker checks and taps, value texts, the switch, failed saves, the asset; `test/pod/i18n.py` measures every label, value and the note.

## Device checks (not run)

STE-01 Equalizer off and Mono Audio on while a track plays: the sound goes mono within about 20 ms, no click; off again returns it. STE-02 Mono and each Crossfeed level switched while a track plays, and between tracks of a gapless pair. STE-03 Line Out (pull-down Output tile) or a USB DAC while Crossfeed is High: the sound loses the crossfeed within a second, the Crossfeed row still says High; back on the jacks it returns. Bluetooth (AirPods): crossfeed applies. STE-04 a hard-panned track (one channel only): Crossfeed brings it into the other ear, Mono plays it in both. STE-05 a 192 kHz file with a curve and Crossfeed: no dropouts (CPU). STE-06 DSD (DoP and native): untouched with both on. STE-07 `/mnt/mmc/m1plus-off`: sound as stock with both on. STE-08 Equalizer off, both options off: bit-exact stock sound and no new files in `/mnt/data/m1plus` (no `playback-stereo`). STE-09 Settings > Developer > Tools > Settings Files lists `playback-mono` and `playback-crossfeed`; Reset All Settings brings both off after a restart.

Not verified on a device: the audio quality and level of the crossfeed (bs2b's own tuning), clicks at a switch, hciplayer's behaviour with the filter kept in the chain for every file with EQ off (native pass-through through a no-op filter), CPU load of the double-precision stage at 192 kHz, and the items above.
