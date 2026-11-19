# Bluetooth

**Sources:** `patch/btset.c` / `btset.h` (control layer), `patch/btpage.c` (pages), `tools/pod_ui.py`
(`build_bluetooth_page`, `build_btdevice_page`), `tools/pod_pages.py` (`BLUETOOTH_PAGE`,
`BTCODEC_PAGE`, `BTDEVICE_PAGE`), `tools/pod_pins.py` `BLUETOOTH_PINS`, `tools/mod_bluealsa.py`.
Settings > Bluetooth is our own page on stock's own state and calls, as [Wi-Fi](wifi.md) and
[Buttons & Power](keyspower.md) are. Three layers:

- **Control layer** (`btset.c`): repeats stock's handler sequences without widgets, in stock's order.
- **The page** (`btpage.c`): Bluetooth switch, Audio Codec picker, My / Other Devices.
- **The device page**: Connect / Disconnect, Headset Volume, Forget.

The radio itself is stock's (`libbtctl`, `bluetoothd`, `bluealsa`); we add no backend and change one
capability bit ([AAC at 48 kHz](#aac-at-48-khz)). One hook
(32) sends the All System Settings hub's Bluetooth row to our page ([payload](payload.md)).

## Stock behaviour relied on

Read from stock V2.1 `systemset/bluetooth_page` and its two sub-pages (`btquality`, `btvolume`).

- **State words.** `bluetoothflag` (0/1, saved as `[SYSSET] BLUETOOTH` by `switchBluetooth`; the page never
  writes it) and `btcoding` (0..7, `[SYSSET] BTCODING`): the preferred codec, not the one in use.
- **Init.** `switchBluetooth(on_now, scan)` starts a detached init thread; `bt_initstatus != 0` while it
  runs. Stock's row handler only toasts "Bluetooth Starting" in that time; the function has no guard.
- **Scan.** `btStartSearch` sets a 10 s count-down (`bt_searchtime`, 50 ticks of 200 ms) and is ignored
  while it is non-zero. Only the page's own 200 ms timer decrements it, refreshes the results at 5 s and
  stops at the end. A scan started with no timer never stops.
- **Connect and pair** run in a detached thread (`bluetoothLink`, 100 ms polls: pairing up to 15 s,
  connecting up to 10 s). `bt_connectstatus != 0` while it runs. The UI thread only starts it.
- **Idle handler.** `checkBluetoothStatus` runs on every main-loop idle pass, finishes links, refreshes the
  lists and local name and sets `wifiset_refreshflag`, the redraw request shared with the Wi-Fi page.
- **Lists.** `pdeq_btshowlist` (paired first, then the others), `pdeq_btpairlist` and `pdeq_btlinklist`
  (connection attempts; only the last item gives a row's Connecting / Connected state). They are refilled
  by `getSearchResult` on the UI thread, so an index kept from an earlier draw can name another device.
- **Codec priority.** `switchBtPriority(c)` maps the eight values to three `libbtctl` calls; LDAC HQ and
  Standard make the same calls. It applies only to a link made afterwards.
- **Volume.** `adjustA2dpVolume(up)` steps the A2DP transport volume by 10/127 and acts only with Bluetooth
  on, a link up, a known codec and no receiver page; it answers 1 either way.
- **Config.** `BLUETOOTH`, `BTCODING` and `BTLINKMAC` (auto-reconnect) are in `config.ini`.
- **Control Center tile and SyncLink** call the same `switchBluetooth` (no scan afterwards); they change
  the state words while our page is up.

## Control layer

`btset.c` is what the page calls. No widget is made or touched. Action functions answer `BS_REBUILD`
(read the state again and lay out) or `BS_NONE`.

- A device is named by its MAC string. The show-list index stock's functions take is looked up right
  before each call.
- Every action stock's row handler guards toasts "Bluetooth Starting" (kind 1, 2 s) and does nothing else
  while `bt_initstatus != 0`. Device taps and the codec choice are ignored while `bt_connectstatus != 0`.
- After an action the page re-reads the state (lists, `bluetoothflag`, `bt_connectstatus`) and keeps no
  index. `bs_devices` fills `struct bs_dev` (290 bytes each), so give it a static array.

| Function | Does |
|---|---|
| `bs_on`, `bs_starting`, `bs_scanning` | `bluetoothflag`, `bt_initstatus`, `bt_searchtime > 0` |
| `bs_codec()` | `btcoding`, 0 when outside 0..7 |
| `bs_name()` | the controller's name (`localBtName`) |
| `bs_devices(out, max)` | show list in stock's order: `mac`, `name`, `paired`, `state` (Connecting while `bt_connectstatus == 1` and the last link item has this MAC; Connected while its status is 3 and `bt_showcoding` is 1..4 or 13; a linked device with no codec yet reads Paired) |
| `bs_volume_ok()` | the conditions under which `adjustA2dpVolume` acts |
| `bs_modal()` | 1 while a stock dialog of ours is up; the page's tick returns at once |
| `bs_init_guard()` | the toast above; 1 when shown. The page calls it first for rows that call no action |
| `bs_toggle()` | the switch. Off to on with Wi-Fi on: confirm `msg_bt_open`; OK leaves Wi-Fi on ([overlays](overlays.md)). Then `switchBluetooth(bluetoothflag, 1)`. `BS_REBUILD` (also after Cancel, as stock); `BS_NONE` while the init runs |
| `bs_open()` | stock's page init without widgets: clears scan state, reads the name, starts a scan when on and not starting |
| `bs_tick()` | stock's 200 ms timer without widgets: consumes `wifiset_refreshflag`, counts the scan down (refresh at 5 s, stop and refresh at the end), starts a pending scan. Returns `BS_T_REBUILD` / `BS_T_SPIN` bits |
| `bs_close()` | `btStopSearch()` |
| `bs_search()` | `btStartSearch()` (ignored while a scan runs) |
| `bs_link(mac)` | stop the scan, `handleBluetoothLink`: -1 toasts "Please close SyncLink"; 1 (was connected) restores the output, toasts "Disconnected", `save_start_player(1)`; 0 / 2 rebuild only |
| `bs_forget(mac)` | stop the scan, confirm "unpair?", `handleBluetoothPair` (index looked up again after the confirm); if it was the connected device restore the output; toast "Unpaired", refresh the lists. `BS_REBUILD` after an unpair; `BS_NONE` for Cancel, an unpaired device or a failed unpair |
| `bs_codec_set(c)` | refuse `c` outside 0..7, the current one, or while connecting. When connected: confirm "Reconnect Bluetooth?", stop the player, zero the five link words, restore the output. Then `btcoding = c`, `switchBtPriority(c)`, save `BTCODING`, `bluetoothLink(2)` only when connected |
| `bs_volume(up)` | `adjustA2dpVolume(up)` |

The output restore is stock's: `headset_output = judge_outputdevice(headset_output, 2)` when that
differs, then `set_outputchannel(headset_output, 3, 0)` unless `mclGetSavePlayStatus() == 1`. The
confirms and toasts are stock's dialogs through `pod_confirm_dialog` and `pod_toast_ms`; they are modal.

Rules the code obeys:

- **Stop the scan on every exit** (Back, to-background, close, switch off, device tap). Otherwise
  `bt_searchtime` stays non-zero and no later scan starts.
- **UI-thread blocking.** `switchBluetooth` (off), `handleBluetoothLink`, `handleBluetoothPair`,
  `getSearchResult` and `bluetoothInit` (it waits while an earlier init thread lives) block the UI thread
  as stock does. The spinner stops meanwhile.
- **Order matters** where stock's is fixed: `btcoding` is set before `switchBtPriority`; the connected
  codec change zeroes its words and re-routes the output before the reconnect; the forget path
  disconnects before removing the device.
- **The idle handler** changes the same words between our UI events, never inside one.

**Pins.** `BLUETOOTH_PINS` (`tools/pod_pins.py`) pins every stock sequence repeated here, the data words
and the codec table; a different stock build fails the build. `tools/coex.py` turns stock's switch-row
`beqz` into a branch, so Wi-Fi stays on.

## The page

`ui/m1plus_bluetooth.bin` (`Page` `BLUETOOTH_PAGE`) and the Audio Codec picker `m1plus_btcodec`
(`BTCODEC_PAGE`). It is the [Wi-Fi page](wifi.md)'s look and numbers (cards, 52 px rows, hairlines, check,
spinner `wf_spin0..7`, info glyph `wf_info`), and uses its card-list helpers (`wp_put`, `wp_vis`,
`wp_piece`, `wp_pos`, `wp_clamp`, `wf_on_scroll`, `wk_subst`; declared in `patch/entries.h`). The page
only lays out and calls the control layer. It touches no Bluetooth word.

| Row | Shown | Content |
|---|---|---|
| Bluetooth switch | always | the switch; alone when off |
| Audio Codec | on | value = `btcoding`'s name, chevron; tap = init guard, then the picker |
| note | on, name known | grey "This player is shown as “<name>”" |
| My Devices | a paired device | check when connected, spinner while connecting, name, info glyph |
| Other Devices | on | header spinner while scanning or starting; unpaired rows (tap = pair and connect) |
| Search Again | on, not scanning | last row of the Other Devices card (a card of its own when nothing was found); `bs_search()` |

- **Empty states.** While scanning with no device found there is only the header and its spinner. Off: the
  switch row alone.
- **Pools.** 8 paired rows (`BP_MY`), 16 other rows (`BP_OTH`), 32 devices read (`BP_DEVS`, paired
  first). Devices past a pool are dropped. The page state is about 10 KB of `.scratch`.
- **Actions.** Every action is followed by a full read and layout; a tap hands the device's MAC (copied
  first) to `bs_link`. The info glyph (a tap at x >= 264 on a paired row) opens the device page. Taps are
  ignored while `bs_modal()`.
- **Timer.** One 200 ms timer. `bp_tick` does nothing while the page is not in front or `bs_modal()`.
  Otherwise it calls `bs_tick` and lays out again on `BS_T_REBUILD`, or when Bluetooth on / starting /
  scanning differs from what the layout shows; else it only moves the spinners.
- **Life.** `btpage_open()` starts the timer, runs `bs_open()` (the search starts as the page opens) and
  lays out. `EVT_WINDOW_WILL_OPEN` lays out again (names are measured in the resolved style),
  `EVT_WINDOW_TO_FG` reads everything again. `bs_close()` runs on Back, Now Playing, to-background, close
  and destroy. A window, asset or timer that will not start returns -1 and the caller opens stock's page.
- **Audio Codec picker.** Generic check rows (`pick_tab`), eight rows in stock's order (`btcoding` 0..7);
  `ACT_BTCODECSET` 166. `bp_codec_set(c)` = `bs_init_guard()`, `bs_codec_set(c)`; the check moves only
  when `bs_codec() == c` (a cancelled reconnect question, a running connect or the guard leave it). The
  LDAC rows use our short keys (stock's do not fit in some languages); the others are stock's `btcode_*`.
- **Entries.** Settings > Bluetooth stays the `ACT_STOCK` row (value On / Off); `m1plus.c` calls
  `btpage_open()` first and opens `systemset/bluetooth_page` only when it returns -1. The hub's row is
  hooked (hook 32, `bt_hub_open`): our page, stock's with `/mnt/mmc/m1plus-off` or where ours will not
  open. The Control Center Bluetooth tile is unchanged.
- **Text.** New 13-language keys in `tools/pod_i18n.py`: Audio Codec, LDAC HQ / Standard / Connection,
  My Devices, Other Devices, Search Again, the note. The label and note are shortened where they would not
  fit.

Deviations from stock: our layout (cards, check or spinner and info glyph instead of the second line and
`bt_del` icon); no Bluetooth Name row but a note; no Search row (the search starts on open); Quality is
Audio Codec; Forget and Headset Volume are on the device page.

## The device page

`ui/m1plus_btdevice.bin` (`BTDEVICE_PAGE`, `bd_*` in `btpage.c`; no action id, no hook), opened by the
info glyph. It has the [Wi-Fi info page](wifi.md)'s look. The page keeps the device's MAC (no index) and
reads the device from the show list by it every time.

| Widget | Shown | Content |
|---|---|---|
| title | always | the device's name, cut with an ellipsis; the whole name in one or two grey lines above the cards when cut |
| Connect / Disconnect | always | "Disconnect" while connected, else "Connect"; `bs_link(mac)`, then the state is read again. While connecting: "Connect" at 60 % opacity and insensitive (stock ignores taps then) |
| Headset Volume | the connected device and `bs_volume_ok()` | minus and plus keys, one `bs_volume` step per tap, no readout |
| Forget This Device | always | `bs_forget(mac)`; the page closes when the device is no longer paired, stays after Cancel, a failed unpair or a running connect |

- **Decision:** Headset Volume is on the device page for the connected device only. Stock has a row on
  the Bluetooth page that opens `btvolume_page`.
- **Reading.** One 500 ms timer runs `bd_refresh` only while the page is in front and not under a dialog.
  It reads `bs_devices` (the link list and `bt_connectstatus` that stock's idle handler keeps current), so a
  link that completes by itself shows without a tap. The page never calls `bs_tick` and never reads or
  clears `wifiset_refreshflag`, so the Bluetooth page's own re-read is not starved. `EVT_WINDOW_TO_FG` reads
  at once. The layout changes only when what it shows changed.
- **Closing.** When the device is gone or unpaired, or Bluetooth went off (the tile), the page closes once
  (`navigator_back`). A device that left the list between the row's draw and the glyph tap opens no page.
- **Text.** `Connect`, `Disconnect`, `Headset Volume`, `Forget This Device` (13 languages).

## AAC at 48 kHz

`tools/mod_bluealsa.py` (the build step after `mod_player`) clears the 44.1 kHz bit of bluealsa's AAC
source capability (`c0 01 84 84 e2 00` at file offset `0x317b7`; octet 1 `01` → `00`), pinned by the stock
SHA-256.

- The player feeds bluealsa 48 kHz. A link the player opens picks 48 kHz AAC. A headset or speaker that
  opens the stream itself (AirPods out of the case, a speaker reopening it after idling through a long
  pause) picked 44.1 kHz, and bluealsa dropped about 8% of the AAC frames: a rhythmic stutter and audio
  that sounds fast, until Bluetooth reconnected. With the bit clear only 48 kHz is offered, which every
  AAC sink supports.
- The same stock binary and fix as q2-pod's (`docs/internals.md` "Bluetooth AAC").
- A capability bit, not a hook: the kill switch does not restore it. SBC and the other codecs are unchanged.

## Limits

- The radio, pairing, codec negotiation and AVRCP volume cannot be run in the emulator; the tests mock the
  backend and compare our sequences with stock's handlers.
- The libbtctl status callback's event codes beyond 3 (connected), 4 (disconnected) and 5 (remote
  connect) are inferred, as is the thread libbtctl's callbacks run on.
- The click x of the info-glyph hit line is taken from AWTK's event layout.
- The remote-disconnect, AirPods retry and receiver-page paths of `checkBluetoothStatus` were not traced;
  the page follows their result through the shared state words.
