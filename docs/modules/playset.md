# Playback settings

**Sources:** `patch/playset.c`, `tools/pod_pages.py` (`PLAYSET_PAGE`, `PSVOLUME_PAGE`, `PSOUTPUT_PAGE`, `PSMAXVOL_PAGE` ..),
`tools/pod_ui.py` `cards_volcard`, `tools/pod_pins.py` `PLAYSET_PINS`, `tools/pod.py` (`FUNCTIONS`,
`DATA`).
Settings > Playback Settings is an own hub page (`m1plus_playset`) with two own sub-pages, Volume & Sound
(`m1plus_psvolume`) and Output (`m1plus_psoutput`), that replace stock's
`playset/playset_page` ("All Playback Settings") and its sub-pages, as [Buttons & Power](keyspower.md)
and [Display](display.md) replaced theirs. Every row shows stock's own state word and calls setters
that repeat stock's click handler stores in order, store for store and call for call. Nothing of ours
is saved (except Mono, Crossfeed and Crossfade). No hook, nothing boot-reachable. Values are read again when each
page opens and on `EVT_WINDOW_TO_FG`; a picker or slider page returns to the sub-page that opened it
(the window stack, no parent is recorded), and the Gain row's dim is applied wherever the row sits.

## The pages

The Settings row **Playback Settings** (Settings > Playback, after EQ; `ACT_PAGE`, `PLAYSET_PAGE`)
replaces **All Playback Settings** and takes **Continue Playing** with it. The hub has three
groups under headers: **Queue** (Play Mode, Continue Playing, Folder Skip, Resume), **Transitions**
(Gapless, Crossfade) and **Audio**, two link rows, **Volume & Sound** (`ACT_PAGE`,
`PSVOLUME_PAGE`) and **Output** (`ACT_PAGE`, `PSOUTPUT_PAGE`). **Volume & Sound** has a Volume header
and a Stereo header; **Output** starts with a card without a header, then a USB & Digital header.
The two pages come last in `PAGE_ORDER` so no other page's number moved. Rows, in order:

| Section | Row | Control | State (stock's own) | Setter = stock's click, in its order |
|---|---|---|---|---|
| Hub > Queue | Play Mode | value row, picker: List Play, Repeat Track, Shuffle, Repeat All | `pod_play_mode()` ([shuffle](shuffle.md)) | `pod_set_mode(m)`: `mclSetPlayMode`, `notifyPlayMode`, `dmrSendPlayMode`, `write_int_config(m, "PLAYSET", "PLAYMODE")`; nothing when `m` is shown already |
| | Continue Playing | value row | ours ([nextalbum](nextalbum.md)), moved here unchanged | |
| | Folder Skip | switch | `mclGetJumpFolder()` | `write_int_config(new, "PLAYSET", "JUMPFOLDER")`, `mclSetJumpFolder(new)` |
| | Resume | value row, picker: Off, Track, Location | word `memory_play` | the word, `write_int_config(i, "PLAYSET", "MEMORYPLAY")` |
| Hub > Transitions | Gapless | switch | `mclGetGaplessMode()` | `write_int_config(new, "PLAYSET", "GAPLESS")`, `mclSetGaplessMode(new)` |
| | Crossfade | value row (Off or N s) opening the Crossfade page: a switch, a 1 to 12 s duration slider, Keep Albums Gapless | ours: files `playback-crossfade`, `playback-crossfade-auto` ([crossfade](crossfade.md)) | `xfade_on_toggle`, `xfade_sec_set`, `xfade_auto_toggle` |
| Volume & Sound > Volume | Gain | value row, picker: Low, High | `mclGetGainMode()` | `write_int_config(new, "PLAYSET", "GAIN")`, `mclSetGainMode(new, 1)`; dimmed and refused while Line Out is on |
| | Max Volume | value row (number), slider page | word `max_volume` | stock's slider, `btn_dec`, `btn_add` handlers ("Loudness pages") |
| | Default Volume | value row (`Memory` while the byte is 1, else the number), page with Volume Memory switch and slider | byte `boot_volflag`, word `boot_volume` | switch: byte xor 1, `write_int_config(byte, "PLAYSET", "BOOTVOLFLAG")`; slider: stock's handlers |
| | ReplayGain | value row, picker: Off, Track, Album | `mclGetReplayGain()` | `mclSetReplayGain(i)`, `write_int_config(i, "PLAYSET", "REPLAYGAIN")` |
| Volume & Sound > Stereo | Channel Balance | value row (stock's label text), slider page | word `balance` | stock's handlers |
| | Mono Audio | switch | ours: file `playback-mono` ([stereo](stereo.md)) | `stereo_mono_toggle` |
| | Crossfeed | value row, picker Off / Low / Medium / High; note "For headphones and Bluetooth. Not applied to Line Out, USB DAC or DSD." | ours: file `playback-crossfeed` | `stereo_crossfeed_set` |
| Output | Digital Filter | link row, picker of eight filters | `mclGetfilter()` | `mclSetFilter(i)`, `write_int_config(i, "PLAYSET", "FILTER")` |
| | DSD Output Mode | value row, picker: D2P, DOP, Native | `mclGetDsdMode()` | `write_int_config(i, "SYSSET", "DSDMODE")`; on USB audio (`mclGetOutputWay() == 2`) `save_stop_player()`; `mclSetDsdMode(i)`; if still USB `save_start_player(0)` |
| Output > USB & Digital | USB Mode | link to stock's usbset page (Back returns to Output) | - | stock's page, no code of ours ([settings](settings.md)) |
| | USB Volume | value row, picker: Fixed, Variable | word `usbvol_mode` | the word, `set_devicevolume(volume)`, `write_int_config(i, "SYSSET", "USBVOLMODE")` |
| | Digital Output | switch | byte `digital_flag` | byte xor 1, `write_int_config(byte, "PLAYSET", "DIGITALMODE")`, `mclSetLineOut(byte)` |

Settings > Library also gets **Folder Album Cover** (switch, under a Folders header): the byte
`foldercover_flag` xor 1, `write_int_config(byte, "PLAYSET", "FOLDERCOVER")`, nothing else. The
Folders page and the cover task read the byte ([folders](folders.md)); the Folders page re-reads it
when its window returns, so the change shows without a rebuild.

Rules shared by the rows:

- A picker's choice is stock's click only when it differs from the state shown. The chosen value
  shows a check. A setter refuses a value stock does not have (-1) and writes nothing.
- The mcl getters are stock's own functions; the words without a getter (`memory_play`,
  `digital_flag`, `usbvol_mode`) are read directly (`DATA`, checked against dynsym at build). A value
  out of range shows the first choice.
- `save_stop_player` / `save_start_player` are called at stock's addresses, so [Internet Radio](radio.md)'s
  hooks over them see the DSD change as they see stock's.
- **Gain at Line Out:** Bluetooth and USB do not disable the row. It follows the Line Out byte, dimmed (60 % opacity) and insensitive on
  open and on return to front (Volume & Sound), so the pull-down's Output tile (which forces gain high in the
  hardware with `mclSetGainMode(1, 0)`) is reflected. The shown value is the stored word.
- **Pull-down:** the Playback Settings tile opens the hub (`pd_open_settings`,
  [pulldown](pulldown.md)), restacked if already in the stack; stock's list opens only if ours
  will not. Our pages never set `playsetinto_flag`,
  so `pd_reconcile` reads it from the hub's window: the tile is disabled over the hub and every
  window above it up to the player (Volume & Sound, Output, their pickers and slider pages), live
  behind the player. `pd_close_subpages` closes those windows before the hub is restacked.
- **Not on the page:** EQ (own row on the Settings root, [peq](peq.md)), Enlarged album art (it is
  Idle Display, [bigcover](bigcover.md)) and **Single Dual DAC**. Stock never lists the last: the
  builder omits the row, so it is not part of the product.

### Loudness pages

Max Volume, Default Volume and Channel Balance (Volume & Sound) open slider pages (`m1plus_psmaxvol`,
`m1plus_psbootvol`, `m1plus_psbal`). Each is a value card holding stock's label by stock's name
(`label_vol`, `label_balance`) over a control card holding stock's `btn_dec` and `btn_add` (`-` and
`+`, on balance `L` and `R`) either side of stock's slider (`vol_slider` 0..100, `slider_balance`
0..20) in the Display page's slider look. Default Volume has the Volume Memory switch row above.

- **Stock's own handlers run** (`ps_vol_opened`, `PLAYSET_PINS`): the window binds stock's handlers to
  the widgets by name with the window as context, the slider's on `EVT_VALUE_CHANGING`, the buttons'
  on `EVT_CLICK`, as stock's page inits do. Stores, the clamp of `volume` to the new max,
  `set_devicevolume` (only while `headset_output != 2`), saves and the refresh are not repeated in
  the payload, so order and guards cannot differ. Stock's refresh runs when the page opens (before
  the handlers are bound, so setting the slider is not a change to save) and on `EVT_WINDOW_TO_FG`.
- **Volume Memory** (`ps_bootmem_toggle`) is the one control without stock's code: stock's click needs
  its switch image and hidden `bootvol_view`, so the payload repeats the byte xor 1 and the save and
  dims the cards itself (60 % opacity, insensitive, while the byte is set).
- **The number alone:** Max Volume and Default Volume show "80", not "VOL: 80". Stock's `label_vol`
  stays hidden for stock's code to write into, and `pod_vsnum` shows the word (`ps_vol_num`). Our
  handler is bound before stock's, so it runs after (the emitter runs the newest first) and reads the
  word as stock stored it. Channel Balance keeps stock's text (`L3`, `0`, `R2`).
- **Saving:** every control writes at once (nothing on release or leaving). A slider drag saves on
  every changing event, as stock's does. Max Volume's slider and dec button lower `volume` to the new
  max when it is above (device call unless Bluetooth, `VOLUME` saved, then `MAXVOLUME`); add and a
  raised max never raise it. Balance calls `set_devicevolume(volume)` after every store (unless
  Bluetooth). Default Volume applies nothing live: it is a boot-time level.
- **Stale values:** Max Volume's page shows only the max. Volume keys change `volume` under it; every
  handler reads `volume` when it runs.

## Labels

Our own short English keys (stock's translations are partly wrong: French "avoir ralenti" for
ReplayGain, Italian "Modalità di gioco" for Play Mode), all in the 13 languages ([i18n](i18n.md)). Names differing from stock: **Max Volume**, **Default Volume**
(stock "Boot volume"), **Channel Balance**, **Volume & Sound**, **Stereo** and **USB & Digital** (the new page title and headers; `Output` and `Volume` already existed), **Volume Memory**, **Resume** (stock "Memory playback":
the full word does not fit beside "Location"), **USB Volume** (stock "USB Audio Output": it sets
the DAC's volume mode), **Digital Filter**, **Track** (ReplayGain; stock "Audio"), **Fixed / Variable**.
The eight filters are shortened: Minimum Phase, Linear Fast Apodizing, Linear Fast, Linear Fast Low
Ripple, Linear Slow, Minimum Fast, Minimum Slow, Minimum Low Dispersion. Digital Filter shows no value
on its row (no name fits); the picker shows the check. D2P, DOP and ReplayGain stay English in every
language (`SAME_AS_ENGLISH`).

## Stock behaviour the rows rely on

All from stock V2.1 `demo` (pins in `PLAYSET_PINS`). Config keys are `write_int_config(value,
section, key)`; "load" is `config_init`'s clamp.

| Row | State | Config key | Load clamp / default | What stock does that we keep |
|---|---|---|---|---|
| Play Mode | mode word + our flag | `PLAYSET PLAYMODE` | >= 4 -> 0; shipped 3 | set function: `mclSetPlayMode`, `notifyPlayMode`, `dmrSendPlayMode`, config, applied at once, no confirmation |
| Gapless | byte | `PLAYSET GAPLESS` | >= 2 -> 0; 0 | turning off closes an open preload at once |
| Resume | `memory_play` 0/1/2 | `PLAYSET MEMORYPLAY` | >= 3 -> 0; 2 | word then config only; no player action |
| Folder Skip | byte | `PLAYSET JUMPFOLDER` | >= 2 -> 0; 1 | read by `change_music` (Next / Previous) |
| Gain | word 0 Low / 1 High | `PLAYSET GAIN` | >= 2 -> 0; 0 | click is a no-op while Line Out is set; the store arg must be 1; no volume change |
| ReplayGain | word 0/1/2 | `PLAYSET REPLAYGAIN` | >= 3 -> 0; 0 | live, the hciplayer is told; re-applied by `config_mplayer` |
| Digital Filter | word 0..7 | `PLAYSET FILTER` | >= 8 -> 0; 3 | live (driver ioctl); not re-applied by `config_mplayer` |
| DSD Output Mode | word 0/1/2 | `SYSSET DSDMODE` | no clamp, set ignores >= 3; 0 | stop and restart of playback only on USB audio |
| Digital Output | byte | `PLAYSET DIGITALMODE` | >= 2 -> 0; "0" | `mclSetLineOut` ioctl; the byte also drives the status bar and pull-down digital-out glyph ([lineout](lineout.md)); unrelated to the Line Out byte |
| USB Volume | `usbvol_mode` 0 Fixed / 1 Variable | `SYSSET USBVOLMODE` | >= 2 -> 1; 1 | only the USB branch of `set_devicevolume`: Fixed sends 100 to the DAC, Variable sends `volume` |
| Max Volume | `max_volume` 0..100 | `PLAYSET MAXVOLUME` | >= 101 -> 100; 100 | read by the volume keys, the volume dialog, config_init (clamps `volume` at boot) and SyncLink; 0 is allowed |
| Default Volume | `boot_volflag` + `boot_volume` | `BOOTVOLFLAG`, `BOOTVOLUME` | flag >= 2 -> 0; volume >= 101 -> 30 | used at boot only: with the flag 0, `volume = boot_volume`, then clamped by the max |
| Channel Balance | `balance` 0..20, centre 10 | `PLAYSET BALANCE` | >= 21 -> default; 10 | acts only through `set_devicevolume` on built-in and Bluetooth; Line Out and USB ignore it |
| Folder Album Cover | byte | `PLAYSET FOLDERCOVER` | >= 2 -> 0; default on | selects the folder cover on the stock folder row; the cover task skips its folder branch when 0 |

**`set_devicevolume(v)`** is how every volume change reaches the hardware:

1. Line Out byte set and output way 0: `mclSetVol(100, 100)`; level, balance and max are ignored.
2. Output way 2 (USB audio): `mclUsbAudioSetVol` with 100 when Fixed, else `v`.
3. Otherwise (built-in, Bluetooth): apply Balance (`balance < 10` lowers the right level by
   `10 - balance`, `> 10` lowers the left; clamped 0..100), then `mclSetVol(left, right)`.

`headset_output == 2` is Bluetooth: the Max Volume and Balance handlers then lower and save
`volume` but do not call `set_devicevolume`. At boot, with Line Out set, `config_init` forces gain high
without changing the word or the saved `GAIN` (`mclSetGainMode(1, 0)`). The Line Out byte also
makes the volume keys inert and disables the Gain row, the pull-down Gain tile and the Output tile's
gain path.

**Other stock writers.** The pull-down Gain and Output tiles and `audiosetting_page` (Gain, Filter,
Max Volume, DAC Charging, Balance, opened from the AirPlay, Bluetooth receiver and USB mode pages)
still open stock's pages, so stock's `filter_page`, `maxvol_page` and `balance_page` stay in the
asset tree. The Output tile's Line Out toggle asks `msg_lowarn`, then `mclSetGainMode(1, 0)` going to
Line Out and `mclSetGainMode(mclGetGainMode(), 0)` coming back. Stock's own list can still be reached
from the Home grid's Play Settings icon (Developer > Open Shanling Home).

## Limits

- `mclSetGainMode(v, 1)` at boot relies on `a1` surviving `atoi`; if not, the word is never loaded
  from `GAIN`.
- The gain, filter, DAC and digital-output setters do nothing when the mcl driver fd is not open;
  the config save still happens.
- Stock does not clamp the Bluetooth volume to the max, and SyncLink's `responseSetVolume` does not
  clamp to it either.
- Which hardware effect High gain and the Digital Output ioctl have is not read.
- What Resume's Track and Location do differently, and Folder Skip's branch in `change_music`, are not
  traced.
