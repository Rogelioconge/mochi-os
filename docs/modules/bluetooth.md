# Bluetooth

Settings > Bluetooth is replaced by an own page built on stock's own state and calls (as [Buttons & Power](keyspower.md) and [Wi-Fi](wifi.md) were): "The page" (after "Control layer") is the page and its Audio Codec picker, "The device page" the page of one paired device.
Sections 1 to 8 are the static analysis of stock V2.1 `demo` for Settings > Bluetooth (`systemset/bluetooth_page`) and its two sub-pages
(`systemset/btquality_page`, `systemset/btvolume_page`), written so that the own page needs no new reading of the disassembly; "Control layer" (after
section 6) is `patch/btset.c`, which repeats stock's handlers without widgets. All addresses are `demo` virtual addresses, read from
`work/cache/demo.dis` (`tools/disasm.py`); the page's rows are built in code (the assets' lists are empty). Nothing here is run on a device: the
Bluetooth radio cannot be exercised in the emulator. Section 8 lists what was inferred rather than read.

Stock's code for the page spans `0x4a2830..0x4a4288` (the first helpers sit under the neighbouring symbol `systemset_autosynctime_page_init`,
and `systemset_brightness_page_init` at `0x4a47dc` really holds the brightness page's init and then the Quality page's click handler at
`0x4a4850`), `btquality_*` at `0x4a4d28..0x4a5050`, the Quality init `0x4a5050` and the Volume page `0x4a50bc..0x4a52d8`. The backend is
`0x4d2268..0x4d6860` (`openBluetooth`, `switchBluetooth`, `checkBluetoothStatus`, the link list, the scan) plus `libbtctl.so` (`btctl_*`
through the GOT). `bt_thread_run` `0x63858c` is not part of it: it is an AWTK input-thread starter (`open`, `tk_thread_create`).

## Summary

| Item | Stock fact |
|---|---|
| On/off state | byte `bluetoothflag` `0xa05ac0` (0/1), saved as `[SYSSET] BLUETOOTH` by `switchBluetooth` `0x4d516c`; the page never writes it |
| Choice of codec | word `btcoding` `0x97caf4` (0..7), saved as `[SYSSET] BTCODING` by the Quality row's handler |
| Page rows | switch, name (display only), Quality, Headset Volume Control, Search, then up to two headers and the device rows |
| Name | read only (`getLocalBtName` `0x4d31c4`, from `btctl_get_controller_info`); no row edits it |
| Receiver mode | no row, no switch on this page; the direction is derived from the connected device (section 5) |
| Scan | started by `btStartSearch` `0x4d3d50`; its 10 s count-down and result refresh are run by the page's own 200 ms timer |
| Connect / pair / unpair | on the UI thread the handlers only start work: connect and pair run in a detached thread (`bluetoothLink` `0x4d2778`) |

## 1. The page as stock builds it

**Asset** (`ui/systemset/bluetooth_page.bin`): `navigationbar_view` (`label_title`, `btn_return` 80 x 50, `btn_backtoplayer` 60 x 50),
`list_view` `bluetooth_listview` 320 x 400 at y 50 (`default_item_height` 64), `scroll_view` `bluetooth_scrollview` 310 x 400,
`scroll_bar_m`. A `widget_foreach` over the window (`0x4a2a68`, from init `0x4a411c`) binds `btn_return` (click, `0x4a29cc`),
`btn_backtoplayer` (`on_backtoplayer_onclick` `0x4cd58c`) and sets `label_title` to `wifiset_bt` ("Bluetooth" / 蓝牙).

**The list.** `0x4a3734(win)` (the rebuild) destroys the children of `bluetooth_scrollview` (`widget_destroy_children`) and creates the rows
again from scratch, every time: `n = getBluetoothNum()` (`0x4d3dd4`) rows, row `i` by this table (`list_item_create(scrollview, 0, 0, 0, h)`):

| Row `i` | Condition | Layout fn | Height | Item name | Click bound |
|---|---|---|---|---|---|
| 0 | always | `btswitch_listitem_layout` `0x4a2e94` | 64 | `"0"` | yes |
| 1 | Bluetooth on | `btname_listitem_layout` `0x4a2f6c` | 64 | none | no |
| 2 | Bluetooth on | `bluetoothquality_listitem_layout` `0x4a3038` | 64 | `"2"` | yes |
| 3 | Bluetooth on | `btvoladj_listitem_layout` `0x4a3150` | 64 | `"3"` | yes |
| 4 | Bluetooth on | `btsearch_listitem_layout` `0x4a320c` | 64 | `"4"` | yes |
| `P` = first header | at least one paired device | `btmsginfo_listitem_layout` `0x4a332c`, text `bt_paireddev` | 42 | none | no |
| `C` = second header | at least one unpaired device | the same, text `bt_compatiabledev` | 42 | none | no |
| any other | a device | `btdevice_listitem_layout` `0x4a33c8` | 64 | `"%d"` = the row index | yes |

Counts (`getBluetoothNum` `0x4d3dd4`, `getBtMessageIndex` `0x4d3e4c`): with `bluetoothflag` 0 there is one row (the switch). Otherwise with
`n` = size of `pdeq_btshowlist` and `p` = size of `pdeq_btpairlist`: `5 + n + (p > 0) + (n - p > 0)` rows. `P` = 5 when `p > 0`, else none;
`C` = `p + 6` when `p > 0` and `n - p > 0`, = 5 when `p == 0` and `n > 0`, else none. The show list holds the paired devices first
(section 2), so rows `6 .. 5+p` are the paired devices and the rest follow `C`; the show-list index of a device row is `row - 6`, or
`row - 7` after both headers. (`bluetoothflag` 1 with an empty show list: five rows.)

Row content (`label` = `hscroll_label` with `hscroll_label_set_speed`; helper `0x4a2d2c(item, text, y, w, plain)` creates one at x 12,
h 21, style `srlabel_leftwhite21_style`, `plain` 0 = a device name set as utf8 text, 1 = a tr key; `0x4a2c30(item, key, w)` creates the grey
second line at x 12, y 32, h 28, `srlabel_item_gray18_style`, a tr key; `0x4a2cc0` adds the `bt_del` icon, an image 25 x 25 at x 283, y 18):

| Row | Content |
|---|---|
| switch | label `wifiset_bt` at y 20, w 200; image at x 251, y 16, 57 x 28: `sset_on` when `bluetoothflag`, else `sset_off`; style `list_item_style` |
| name | label (tr text) of `getFormatString("bt_name")` run through `tk_snprintf(.., localBtName)` ("Bluetooth Name:%s"), y 20, w 296; style `list_item_notpress_style` |
| Quality | label `bt_quality` (y 10, w 220), second line the **preferred** codec `get_bluetoothcoding_text(btcoding)` (`0x4da15c`, table below, not the codec in use), `right_arrow` image (x 295, y 0, 13 x 60) |
| Headset Volume Control | label `bt_adjvol` (y 20, w 220), `right_arrow` |
| Search | label `bt_search` (y 20, w 200); icon image at x 283, y 18, 25 x 25, name `bt_search_icon`: image `bt_scan` while `bt_searchtime` is 0, else `search<N mod 8>` |
| headers | `label_create` 320 x 42, style `navbar_centerlabel_white`, row style `list_item_black_style` |
| device | name label `btdevice_listitem_layout` (below) at y 10 with a second line, or at y 20 alone; `bt_del` icon on paired rows |

Device row (`0x4a33c8(item, i, P, C)`): the device is `pdeq_btshowlist[idx]`, its name at `+0x24`, MAC at `+4`; the *last* link-list item
(`getBtLinkItem(getBtLinkSize() - 1)`) supplies a status word and a MAC. Cases, in this order:

1. device MAC equals the last link item's MAC and `bt_connectstatus` (`0xa038b4`) == 1: name (y 10) and second line `msg_connecting`;
2. same MAC, link status 3 and `bt_showcoding` (`0xa03898`) in 1..4 or 13: name and `msg_connected`;
3. otherwise, `checkPairDev(mac)` (`0x4d38f8`) true: name and `msg_paired`;
4. otherwise: the name alone (y 20).

Cases 1 to 3 add the `bt_del` icon (`0x4a2cc0`) when `checkPairDev` is true (always for 2 and 3). A device that is connected but whose codec is
not yet known (`bt_showcoding` 0) shows "Paired". The item gets the name `%d` of its row index (`tk_snprintf`), style `list_item_style`.

Texts (`work/stock/rootfs/release/assets/default/raw/strings`, en_US / zh_CN):

| Key | English | Chinese |
|---|---|---|
| `wifiset_bt` | Bluetooth | 蓝牙 |
| `bt_name` | Bluetooth Name:%s | 蓝牙名称:%s |
| `bt_quality` | Quality | 无线播放品质 |
| `bt_adjvol` | Bluetooth Headset Volume Control | 蓝牙耳机音量调节 |
| `bt_search` | Bluetooth Searching | 蓝牙搜索 |
| `bt_paireddev` | Paired Device | 已配对设备 |
| `bt_compatiabledev` | Compatible Device | 可连接设备 |
| `msg_connecting` / `msg_connected` / `msg_paired` | Connecting / Connected / Paired | 正在连接 / 已连接 / 已匹配 |
| `msg_unpairing` / `msg_unpaired` | unpair? / Unpaired | 是否取消配对? / 已取消配对 |
| `msg_disconnected` | Disconnected | 连接已断开 |
| `msg_btinit_run` | Bluetooth Starting | 蓝牙初始化中 |
| `msg_closesynclink` | Please close SyncLink | 请关闭SyncLink |
| `msg_btreconnect` | Reconnect Bluetooth? | 是否重连蓝牙? |
| `msg_bt_open` | Wi-Fi is turned on.Do you want to turn off Wi-Fi before using Bluetooth? (reworded by the coexistence patch) | WiFi已打开,是否关闭WiFi再开蓝牙? |
| `msg_disonnectbt` / `msg_openbluetooth` / `msg_btabnormal` | Please disconnect the bluetooth device / Please turn on Bluetooth / Bluetooth abnormal | 请断开蓝牙设备 / 请打开蓝牙 / 蓝牙异常 |
| `msg_pair_code` | Bluetooth Code | 蓝牙配对码 |

The last row's keys are not used by this page (`msg_disonnectbt` is the SyncLink enable path, `0x4ad2e0`); the others are all from this page.
`bt_scan`, `search0..7`, `bt_del`, `right_arrow`, `sset_on`, `sset_off`, `list_item_style`, `list_item_notpress_style` and
`list_item_black_style` are stock image and style names.

**Quality page** (`ui/systemset/btquality_page.bin`): navbar as above (title `bt_quality`) and `btquality_listview` /
`btquality_scrollview` 320 x 400. `btquality_initlayout_face` `0x4a4f60` rebuilds the scroll view with eight rows (`i` = 0..7, item name `"%d"`,
`list_item_style`, click `0x4a4850`): a label with `get_bluetoothcoding_text(i)` at x 12, y 20, w 200 and a 26 x 26 check image at x 273,
y 17 named `image_choice<i>`: `selected` when `btcoding == i`, else `unselect` (`btquality_item_righticon` `0x4a4d28`). The names come from the
table at `0x97ca08` (8 pointers); what `switchBtPriority` `0x4d3024` does for each value is the third column (jump table `0x74a4b0`, the
three libbtctl calls are `btctl_set_codec_priority(a)`, `btctl_set_ldac_quality(b)`, `btctl_set_sbc_quality(c)`, return 1):

| `btcoding` | Key | English | Chinese | `(a, b, c)` |
|---|---|---|---|---|
| 0 | `btcode_ldachq` | LDAC HQ | LDAC音质优先 | `(0x13, 0x16, 1)` |
| 1 | `btcode_ldacst` | LDAC Standard | LDAC标准 | `(0x13, 0x16, 1)` (same jump target as 0) |
| 2 | `btcode_ldacauto` | LDAC Connection (auto) | LDAC连接优先(自动) | `(0x13, 0x18, 1)` |
| 3 | `btcode_aptxhd` | aptX HD | aptX HD | `(0x12, 0x18, 1)` |
| 4 | `btcode_aptx` | aptX | aptX | `(0x11, 0x18, 1)` |
| 5 | `btcode_aac` | AAC | AAC | `(2, 0x18, 1)` |
| 6 | `btcode_sbchq` | SBC HQ | SBC HQ | `(0, 0x18, 2)` |
| 7 | `btcode_sbc` | SBC | SBC | `(0, 0x18, 1)` (any value >= 7 does the same) |

**Volume page** (`ui/systemset/btvolume_page.bin`): navbar (title `bt_adjvol`) and two 100 x 100 buttons, `btn_dec` at (30, 124) with icon
`bt_dec`, `btn_add` at (190, 124) with `bt_add`. No label, no value display. The foreach `0x4a50bc` binds the navbar buttons, the title and the two
clicks (`btn_dec` `0x4a525c`, `btn_add` `0x4a5228`).

## 2. State

| Word | Address | Meaning |
|---|---|---|
| `bluetoothflag` | `0xa05ac0` (u8) | 0 off, 1 on (user's choice; also 1 while still starting) |
| `btcoding` | `0x97caf4` (i32) | 0..7, the preferred codec (above) |
| `bt_initstatus` | `0xa038a4` (i32) | 0 idle; 1 while the init thread runs; `0x65` / `0x66` / 3 = the thread has finished (set by it, consumed by `checkBluetoothStatus`, which resets it to 0). The thread stores `0x65` for `bluetoothInit(0)`, `0x66` for `bluetoothInit(1)`, 3 for any other argument (`0x4d31a4..0x4d31b8`); the thread stores 0 instead when `bt_exit_init` is 1 |
| `bt_inittime` | `0xa038a0` (u8) | the page's spinner count-down, set to `0x32` by `bluetoothInit`, zeroed when the init finishes |
| `bt_exit_init` | `0xa038a8` (u8) | request to abort a starting init (set by the coexistence preamble and by `bluetoothInit` while it waits); cleared by `switchBluetooth` and by a successful trylock |
| `bt_start_scan` | `0xa0388c` (u8) | 1 = the page's timer starts a scan; set by `checkBluetoothStatus` after an init with `0x66`; cleared by `switchBluetooth`, the page's init and the timer |
| `bt_searchtime` | `0xa038b1` (i8) | scan count-down in 200 ms ticks: `btStartSearch` stores `0x32` (50 = 10 s), `btStopSearch` 0. Decremented only by the stock page's timer |
| `bt_connectstatus` | `0xa038b4` (i32) | connect thread: 0 none, 1 running, 2 thread finished (idle handler turns it into 3 while it processes, then 0); the page also reads 1 |
| `bt_linkstatus` | `0xa03894` (u8) | 1 = an A2DP link is up; cleared by `clearBluetoothStatus` `0x4d40e8` |
| `bt_showcoding` | `0xa03898` (i32) | codec in use; 0 none, 1..4 and 13 count as "connected" on the row; cleared by `clearBluetoothStatus` |
| `bt_backlinkstatus` | `0xa038b0` (u8) | remote-initiated (re)connect marker written by the link callback (1 connected, 5 disconnected) |
| `bt_a2dp_direction` | `0xa038ac` (i32) | receiver / source role of the connected device, 0 none (written by `checkBluetoothStatus`, section 5) |
| `bt_recv_volume` | `0xa0389c` (i32) | -1 none; `a2dp_eventstate` `0xa03890` (i32) |
| `bt_rtk_error` | `0xa041cc` (u8) | the chip bring-up failed (`openBluetooth` sets it); `checkBluetoothStatus` then keeps `bt_initstatus` at `0x66` and returns -1 |
| `localBtName` / `localBtMac` | `0xa0c258` (256) / `0xa0c358` (32) | filled by `getLocalBtName` (from `btctl_get_controller_info`: `+4` name, `+0` MAC) at the page's init and after each init |
| `btsource_volume` | `0x97cb0c` (i32) | `[PLAYSET] BTVOLUME` (default 50, > 100 -> 50): the player's volume while Bluetooth is the output, not read by this page |
| `wifiset_refreshflag` | `0xa05a64` (u8) | "redraw the list": set to 1 by `on_wm_idle_status` whenever `checkBluetoothStatus` returns > 0 and by the Quality handler; shared with the Wi-Fi page (`wifi.md`); consumed (cleared, then the list rebuilt) by the open page's timer |
| `synclinkflag` | `0xa05abf` (i8) | SyncLink mode (1 = over Bluetooth, 2 = over Wi-Fi); `handleBluetoothLink` returns -1 while 1 |
| `headset_output` | `0xa05a10` (i32) | the output selector: 0 / 1 the jacks, 2 Bluetooth, 3 USB ([radio](radio.md)) |
| `btrecv_pageflag` | `0xa05a00` (i32) | the Bluetooth-receiver page is up / due |
| `promptinfo_bt` | `0xa0c230` | the pairing prompt `btctl_set_prompt_callback` (`0x4d231c`) stores: byte 1 set, type at `+4` (a0 == 5 only), the code text at `+8` (0x20); consumed in `on_wm_timer_dialogresponse` (not read) |

**Config** (`/mnt/data/config.ini`, `[SYSSET]`, read by `config_init`): `BLUETOOTH` (`0x4e5b90`, value >= 2 -> 0, `andi 1`), `BTCODING`
(`0x4e5bf0`, value >= 8 -> 0), `BTLINKMAC` (the last connected device, a 17 byte MAC; `readBtLinkMac` `0x4d27e0` keeps it in `0xa041d0` only when
`strlen` is 17; written by the static function at `0x4d23a4`, which `checkBluetoothStatus` calls after a link comes up), `[PLAYSET] BTVOLUME`
(above). The A2DP role per device is a text file `/mnt/data/bta2dpfile` (sections `[A2DP-SOURCE]`, rewritten through `/tmp/tmpa2dpfile`;
`btA2dpDirectionCheck` `0x4d5710`, `Write` `0x4d5904`, `Delete` `0x4d6500`); the PCM for the connected device is `/mnt/data/asound.conf`, written
by `SaveBlueAlsa` `0x4d2458` (connection time, not on codec changes).

**Lists** (`deque` = `_create_deque("stBtDeviceInfo")`, made by `initBluetoothParam` `0x4d3f5c`, called from `config_bt_init` `0x4d6ac8` at boot).
Every item is `0x124` bytes:

| Offset | Size | Field |
|---|---|---|
| `+0x00` | 4 | status: 0 in the pair and show lists; in the link list 1 connecting, 3 connected, 4 disconnected, 5..9 other link events (`updateBtLinkStatus` `0x4d4568`) |
| `+0x04` | 0x20 | MAC, text `AA:BB:CC:DD:EE:FF` (17 chars) |
| `+0x24` | 0x100 | device name (utf8) |

- `pdeq_btshowlist` `0xa041c8`: filled by `getSearchResult` `0x4d3b94` from `btctl_get_device_list` (records of 12 bytes: `+0` MAC, `+4`
  name, `+8` paired flag; records with a null MAC or name are skipped). Paired devices are `_deque_push_front`ed (so their order is reversed),
  the others `_deque_push_back`ed. It is cleared and refilled by every call, on the UI thread only (page, scan ticks, idle), with no lock.
- `pdeq_btpairlist` `0xa041c0`: the paired devices again (`push_back`, so in discovery order), same call. `checkPairDev(mac)` looks a MAC up in
  it under the mutex `0xa04528`.
- `pdeq_btlinklist` `0xa041c4`: connection attempts and links, under the mutex `0xa04528` (`getBtLinkSize` `0x4d4364`, `getBtLinkItem(i, &status, mac)`
  `0x4d4938`, `addBtLinkItem(mac, status)` `0x4d43d4`, `updateBtLinkStatus(status, mac)`, `getBtLinkStatus(mac)` `0x4d4658` (0 when absent),
  `clearBtLinkList` `0x4d3f00`). Written from three places: `handleBluetoothLink` (adds `(mac, 1)`), the connect thread and the libbtctl
  device-status callback `0x4d4738` (registered by `openBluetooth`; its event codes 3..9 are written as the item's status).

**Who runs what.** The page's handlers and its timer run on the UI thread. `bluetoothInit` `0x4d269c` starts a detached thread (`pth_btinitid`, body
`0x4d3104`: `openBluetooth` `0x4d2968`, then `switchBtPriority(btcoding)` unless `bt_exit_init`), which holds the mutex `0xa044f8`;
`bluetoothLink` `0x4d2778` starts the connect thread (`0x4d4d50`). The callbacks `openBluetooth` registers (`btctl_device_status_callback`,
`btctl_set_prompt_callback`, `btctl_set_a2dp_callback`) run on libbtctl's thread (that they are on one thread was not checked).

Blocking, as read:

| Call | Where it blocks |
|---|---|
| `bluetoothInit` | UI thread: `pthread_mutex_trylock(0xa044f8)` in a loop with `usleep(100000)` while an earlier init thread still runs (it sets `bt_exit_init` to make that thread give up); otherwise only `pthread_create` |
| init thread | `openBluetooth`: `PD20` GPIO, `rtk_hciattach` and the files `/tmp/rtk_init_success`, `/tmp/bt_startup`, `bluetoothd &`, `hciconfig hci0 reset`, `bluealsa2 &`, with `usleep` polls (`bt_exit_init` is checked in them); seconds, never timed here |
| `switchBluetooth` off path | UI thread: `btStopSearch`, `btDisconnectAll` (one `system("hcitool dc <mac>")` per link item with status 3), `clearBluetoothStatus`, `closeBluetooth` `0x4d2d3c` (five `system()` kills / `rm`s, the GPIO), `set_devicevolume`, `save_start_player` |
| `handleBluetoothLink` | UI thread: `save_stop_player` (150 ms sleep, `mclStop`, [radio](radio.md)) when the output is Bluetooth, `btDisconnect` / `btDisconnectAll` (`btctl_disconnect_device`, `hcitool dc`), up to two `system("hciconfig -a hci0 ...")`; the link itself in the thread |
| connect thread | 100 ms polls on the link item: pairing up to `0x97` = 151 polls (15.1 s), connect up to `0x65` = 101 polls (10.1 s), disconnect wait the same, an extra `usleep(500000)` once the link reports status 4; ends with `bt_connectstatus` = 2 |
| `getSearchResult` | UI thread: `btctl_get_device_list` + `btctl_free_device_list` (a D-Bus round trip), run every 25 ticks (5 s) and at the end of a scan |
| `btStartSearch` / `btStopSearch` | `btctl_start_discovery` / `btctl_stop_discovery`; `btStartSearch` returns at once while `bt_searchtime` is non-zero, then also calls `getSearchResult` |
| `handleBluetoothPair` | UI thread: `btDisconnect`, `removePairDev` (`btctl_untrust_device`, `btctl_remove_device`), `btA2dpDirectionDelete` (a file rewrite) |

## 3. Click handlers

Row handler `0x4a3a7c` (`0x4a3a88` body), one for rows 0, 2, 3, 4 and the device rows, bound by the rebuild with `widget_on(item, 0x10c, ..., item)`;
`a0` = the item, `a1` = the event. It runs, in order:

1. `win = widget_get_window(item)`. If `bt_initstatus != 0`: a `msginfo_dialog` toast (`{kind 1, ms 0x7d0 = 2000, text}`, text `msg_btinit_run`); return 0.
   Applies to every row, the switch included.
2. `idx = atoi(item->name)`. Then by row:

| Row | Handler does, in order |
|---|---|
| 0, switch, off -> on | `bluetoothflag == 0`: if `wififlag` (`0x97caf8`) is set: a confirm context (kind 5, text `msg_bt_open`) and `navigator_to_with_context("dialog/confirminfo_dialog")` (`0x4a3b4c`); a result other than `0xa` skips to the rebuild. After OK: when `wififlag` is still set, `wifi_switch(1)` (`0x4a3b6c`; the coexistence patch turns the `beqz` at `0x4a3b64` into `b`, so Wi-Fi stays on); then `switchBluetooth(bluetoothflag, 1)` (`0x4a3b84`) and the rebuild `0x4a3734(win)` |
| 0, switch, on -> off | `switchBluetooth(bluetoothflag, 1)` (the same call; the first argument is the current state), rebuild. No confirm |
| 2, Quality | `navigator_to("systemset/btquality_page")` |
| 3, Volume | `navigator_to("systemset/btvolume_page")` |
| 4, Search | `btStartSearch()`. Nothing else: no stop on a second tap (the call is ignored while a scan runs), no rebuild |
| device row | below |

`switchBluetooth(on_now, scan)` `0x4d516c`, for `on_now` 0 (turning on): `bt_exit_init = 0`, `bt_start_scan = 0`, `bluetoothflag = 1`,
`bluetoothInit(scan)` (so `scan` 1 gives init status `0x66`, which makes the idle handler set `bt_start_scan`); for `on_now` != 0 (turning off):
the same two stores, `stop_btsynclink` when `synclinkflag == 1`, when `mclGetOutputWay() == 1` and `judge_outputdevice(headset_output, 2)`
differs: `save_stop_player`, `headset_output` = it, `set_outputchannel(headset_output, 3, 0)`; `btStopSearch`, `btDisconnectAll`, `clearBluetoothStatus`,
`closeBluetooth`, `set_devicevolume(volume)`, both lists cleared, `save_start_player(1)`, `bluetoothflag = 0`. Both paths end with
`write_int_config(bluetoothflag, "SYSSET", "BLUETOOTH")` (`0x4d52c8..0x4d52e0`, a tail call) and return. The init-in-progress guard is only the
toast at the top of the row handler; the function itself has none (the coexistence preamble and the Control Center tile check `bt_initstatus`
themselves, section 5).

**Device row** (`idx >= 5` and not a header; the row is ignored, return 0, when `bt_connectstatus != 0`): `btStopSearch()`;
`getBtMessageIndex(&P, &C)`; the show-list index `s` as in section 1; `onClinkDelPair(s, event->field_0x18)` (`0x4d39c4`: returns
`checkPairDev(showlist[s].mac)` only when the click's x (`+0x18` of the event) is at least `0xe6` = 230, i.e. on the `bt_del` icon, else 0).

| Tap | Does, in order |
|---|---|
| on the `bt_del` icon of a paired device (forget) | confirm (kind 1, `msg_unpairing`, `confirminfo_dialog`); other than `0xa`: return. `handleBluetoothPair(s)` `0x4d66e4`; a result other than 1 or 2 returns. For 2 (it was the connected one) the handler repeats the output restore: `judge_outputdevice(headset_output, 2)`, and when it differs `mclGetSavePlayStatus` != 1: `set_outputchannel(headset_output, 3, 0)`. Then a toast (kind 1, 4000 ms, `msg_unpaired`), `getSearchResult()`, `save_start_player(1)`, the rebuild |
| anywhere else on a device row | `r = handleBluetoothLink(s)` `0x4d5308`: -1: toast (2000 ms, `msg_closesynclink`) and nothing else (no rebuild); 1: the output restore above, a toast (2000 ms, `msg_disconnected`), `save_start_player(1)`, the rebuild (no `getSearchResult`: the branch at `0x4a3f58` jumps past it to `0x4a3dec`); 0 or 2: the rebuild only |

`handleBluetoothPair(s)` (`0` for a bad index): copies `showlist[s].mac`; when `getBtLinkStatus(mac) == 3` and `mclGetOutputWay() == 1`:
`save_stop_player`, the output restore (`judge_outputdevice`, `set_outputchannel`), then `btDisconnect(mac)` and `clearBluetoothStatus`, result 2;
always `removePairDev(mac)` and `btA2dpDirectionDelete(mac)`; result 1 when it was not connected.
`handleBluetoothLink(s)` `0x4d5308` (0 for a bad index; `st` = `getBtLinkStatus(mac)`): with `mclGetOutputWay() == 1`: `save_stop_player` and the
output restore; then `st == 3` (this device is connected): `btDisconnect(mac)`, `clearBluetoothStatus`, result 1. Otherwise `synclinkflag == 1`: -1.
Otherwise: `btDisconnectAll`, `clearBluetoothStatus`, `clearBtLinkList`, `addBtLinkItem(mac, 1)`, `a = checkPairDev(mac)`; when not paired:
`checkLegacypair(mac)` (from `btctl_get_device_info`, field `+0x24`) picks `system("hciconfig -a hci0 sspmode 0")` + `"... auth"` (legacy) or
`sspmode 1` + `noauth`; `bluetoothLink(a)` (0 = pair first, 1 = connect), result 2. The connect thread then polls (section 2) and the idle
handler finishes the link (section 5).

**Name row**: not clickable (no `widget_on`) and no function anywhere writes a new name (`localBtName` is only filled from the controller info).
**Header rows**: not clickable.

**Quality row's page** (`btquality` choice handler `0x4a4850`, bound to every row item; `a0` = the item): `win = widget_get_window(item)`;
return 0 when `bt_connectstatus != 0`; `c = atoi(item->name)`; return 0 when `c == btcoding`. Then, when `bt_linkstatus != 0` and `bt_showcoding > 0`
(a device is connected): confirm (kind 1, `msg_btreconnect`); other than `0xa`: return. On OK: `save_stop_player`, `bt_linkstatus = 0`,
`bt_showcoding = 0`, `bt_a2dp_direction = 0`, `bt_recv_volume = -1`, `a2dp_eventstate = 0`, `headset_output = judge_outputdevice(headset_output, 2)`
(`set_outputchannel(.., 3, 0)` when it changed and `mclGetSavePlayStatus() != 1`); then, and in the not-connected case directly:
widget `image_choice<old btcoding>` -> `unselect` (looked up by name in the window), `image_choice<c>` -> `selected`, `btcoding = c` (stored in
the delay slot of the next call), `switchBtPriority(c)`, `write_int_config(btcoding, "SYSSET", "BTCODING")`; only in the connected case
`bluetoothLink(2)` (the reconnect); finally `wifiset_refreshflag = 1`. Neither `SaveBlueAlsa` nor a bluealsa restart is part of it; the new
priority only applies to a link made afterwards, and `bluetoothLink(2)` is that new link. `systemset_btquality_page_init` `0x4a5050` is only the
foreach binding and the rebuild; the page is re-entrant (the rows are rebuilt on each init).

**Volume page**: `btn_dec` -> `adjustA2dpVolume(0)`, `btn_add` -> `adjustA2dpVolume(1)` (`0x4d28ac`); both return 0 to AWTK. `adjustA2dpVolume(up)`:
does nothing unless `bluetoothflag`, `bt_linkstatus`, `bt_showcoding > 0` and `btrecv_pageflag == 0`; reads
`btctl_transport_get_volume()` (a u8 on a 0..127 scale; a reading >= 128 is ignored) and calls `btctl_transport_set_volume(v - 10)` clamped at 0
or `(v + 10)` clamped at 0x7f (any `up` other than 0 and 1 sets the volume it read). It answers 1 in every case, acting or not. No config, no display, no state word.

**Back / return**: `btn_return` `0x4a29cc`: `btStopSearch()`, the timer removal `0x4a28f0`, then a tail call of `window_close` (`0x675b70`).
`btn_backtoplayer` is `on_backtoplayer_onclick` (shared).

**Long press / other**: none bound by the page.

## 4. Timers and events

`systemset_bluetooth_page_init` (`0x4a411c`, returns `0x10` for a null window): `widget_on(win, 0x12e, 0x4a28bc)` (a handler that only calls
`btStopSearch`), `widget_on(win, 0x12c, 0x4a2a20)` (to background: the timer removal, then `btStopSearch`), `widget_on(win, 0x12d, 0x4a3a28)`
(to foreground: the rebuild `0x4a3734`, then the timer `0x4a2b68`), the foreach; then `bt_searchtime = 0`, `wifiset_refreshflag = 0`,
`bt_start_scan = 0`; with `bluetoothflag` and `bt_initstatus == 0`: clears `localBtName`/`localBtMac`, `getLocalBtName`, **`btStartSearch()`** (a scan
starts as the page opens); in every case the rebuild and the timer.

The timer: `widget_add_timer(win, 0x4a3fa0, 200)` (`0x4a2b68`; the id is stored as the window property `timer_idex`, so a second call is a no-op while one
exists; the removal `0x4a28f0` uses it and sets -1). Callback `0x4a3fa0` (`a0` = the timer, window at `+0x24`), each 200 ms, returns 8 (repeat):

1. `wifiset_refreshflag` set: cleared, rebuild.
2. `bluetoothflag` 0: nothing more.
3. `bt_initstatus > 0` (init running): when `bt_inittime > 0`: decrement and set the spinner image (`bluetooth_searchicon` `0x4a2dd4`: looks up the
   widget `bt_search_icon` by name in the window and sets image `search<n mod 8>`).
4. `bt_initstatus == 0`: if a scan runs (`bt_searchtime > 0`): decrement (`0x4a4060..0x4a4070`); when the new count is 1: `btStopSearch()`
   (it sees a non-zero count, calls `btctl_stop_discovery` and stores 0), `getSearchResult()`, rebuild; when it is a multiple of 25
   (`0x4a40c4..0x4a40e4`, jumping into the same code after the stop): `getSearchResult()` and rebuild without stopping; otherwise only the spinner
   image for the new count. A scan thus lasts 49 ticks (9.8 s) with one refresh at 5 s and the last at the stop. If no scan runs and
   `bt_start_scan` is set: `btStartSearch()` and `bt_start_scan = 0` (`0x4a40f8..0x4a4110`).

**What must keep happening without the stock page.** Everything in the timer is page-local: nothing but the timer decrements `bt_searchtime`
or refreshes the results, so a scan started by another caller never stops and `btStartSearch` stays a no-op (it returns while the count is
non-zero). The backend work runs regardless: the init thread, the connect thread, libbtctl's callbacks, and `checkBluetoothStatus` from
`on_wm_idle_status` (`0x4ce9b0`, every main-loop idle pass, registered by `home_page_init`), which also sets `wifiset_refreshflag`.

## 5. Other writers and entry points

- **`checkBluetoothStatus` `0x4d5a10`** (UI thread, `on_wm_idle_status`): when `bt_initstatus` is `0x65`/`0x66`: with `bt_rtk_error`, sets `0x66`
  and returns -1; otherwise clears the status, refreshes `localBtName` / `localBtMac`, runs `system("hciconfig hci0 class 6c020c")`,
  `getSearchResult`, then `start_btsynclink` (when `synclinkflag == 1` and `bluetoothflag`) or `stop_btsynclink` followed by
  `autoLinkBluetooth` `0x4d4488` (auto-reconnect: needs `bluetoothflag`, `synclinkflag != 1`, a 17 character `BTLINKMAC` that is a paired device,
  `bt_linkstatus == 0`, `bt_connectstatus == 0`, `bt_initstatus == 0`; then `addBtLinkItem(mac, 1)`, `bluetoothLink(3)`), sets `bt_start_scan`
  after `0x66`, zeroes `bt_inittime`, returns 1. With `bt_connectstatus == 2` it finishes a link (reads the device info, sets the link status
  to 3, saves `BTLINKMAC`, `getSearchResult`, `SaveBlueAlsa(mac)`, `bt_linkstatus = 1`, `getBtService(mac)`, sets `bt_a2dp_direction`
  through the file); on failure it clears the status, restores the output (`judge_outputdevice`, `set_outputchannel`, `set_devicevolume(volume)`,
  `save_start_player`). Further branches (disconnect from the remote, `bt_backlinkstatus`, the A2DP event state and the AirPods retry that prints
  `airpods 2回连失败`, the output change to Bluetooth with `set_outputchannel(2)` and `set_devicevolume(btsource_volume)`) were skimmed, not
  followed. A result > 0 makes `on_wm_idle_status` set `wifiset_refreshflag` and call `check_headset_status` `0x4cdea8`; a result of 2 also
  sets `btrecv_pageflag` when it was 0 (the receiver page).
- **Receiver mode**: this page has no row for it. `bt_a2dp_direction` / `btrecv_pageflag` come from the connected device's role
  (`getBtService` `0x4d37a0` maps the device-info field `+0x28`: 7 -> 1, 8 -> 2, 9 -> 3, else 0) and `/mnt/data/bta2dpfile`.
  `adjustA2dpVolume` refuses while `btrecv_pageflag` is non-zero.
- **Control Center tile** (`img_btswitch`, code `0x474cc0..0x474e20`, our own tile in [pulldown](pulldown.md) calls the same stock handler): checks
  `bt_initstatus` and the Wi-Fi flag, `msg_bt_open` confirm, `wifi_switch(1)` (patched out by the coexistence patch), `switchBluetooth(bluetoothflag, 0)`
  (`0x474db0..0x474dbc`: no scan afterwards), then sets `wifiset_refreshflag`. The Wi-Fi tile and the Wi-Fi settings handler
  (`0x4b0be4`) cancel a Bluetooth start (`bt_exit_init`, waits on `bt_initstatus`) and call `switchBluetooth(1, 0)`; SyncLink's enable path
  (`0x4ad40c`) calls `switchBluetooth(0, 0)` (init without scan) when Bluetooth is off.
- **Status bar / pull-down faces** (`show_sysbar_face`, `dropdown_showface`) read `bluetoothflag`, `bt_linkstatus`, `bt_showcoding`. They do not
  write.
- **Boot**: `config_bt_init` `0x4d6ac8` (from `platform_init`) runs `initBluetoothParam`, then `bluetoothInit(0)` when `bluetoothflag` or
  `toolsGpioSetValue` to power the chip off. `init_usersetting` (`0x4e0c1c..0x4e0c5c`) and `into_standby` (`0x4e768c` `closeBluetooth`,
  `0x4e781c` `bluetoothInit`) and `into_poweroff` (`0x4e73d8` `btDisconnectAll`) call the backend; what they decide was not read.
- **SyncLink**: `stop_btsynclink` `0x511958` / `start_btsynclink` `0x511a90` are called by `switchBluetooth` and the idle handler; `SetBtCommandReq`
  (the protobuf command) was not looked up.
- **The `dialog/btscan_dialog` init** (`dialog_btscan_dialog_init` `0x470f6c`, calls `bluetoothInit` and `getSearchResult`) is reachable only
  through the init dispatch table (`0x4d1718`); no `navigator_to("dialog/btscan_dialog")` was found.

**What our page must re-read on every return to the foreground and on open**: `bluetoothflag`, `btcoding`, `bt_initstatus`, `bt_connectstatus`,
`bt_linkstatus`, `bt_showcoding`, the three lists and the local name (the pull-down tile, the idle handler, an incoming connection and a
SyncLink toggle all change them while a page is up), and treat `wifiset_refreshflag` as the redraw request while the page is open.

## 6. Call surface for an own page

Read (all pinned as `DATA` entries checked against dynsym, as `keyspower.c` does): `bluetoothflag` `0xa05ac0` (`BT_FLAG` already exists in `tools/pod.py`),
`btcoding` `0x97caf4`, `bt_initstatus` `0xa038a4`, `bt_connectstatus` `0xa038b4`, `bt_linkstatus` `0xa03894`, `bt_showcoding` `0xa03898`,
`bt_searchtime` `0xa038b1`, `bt_start_scan` `0xa0388c`, `localBtName` `0xa0c258`, `localBtMac` `0xa0c358`, `pdeq_btshowlist` `0xa041c8`,
`pdeq_btpairlist` `0xa041c0`, `pdeq_btlinklist` `0xa041c4`, `wififlag` `0x97caf8`, `synclinkflag` `0xa05abf`, `wifiset_refreshflag` `0xa05a64`.
The item layout (`0x124` bytes: status, MAC, name) is a pinned assumption.

| Call | Address | Signature | Notes |
|---|---|---|---|
| `switchBluetooth` | `0x4d516c` | `int(int on_now, int scan)` | the switch; UI thread, may block (section 2); the page passes `(bluetoothflag, 1)`; a confirm and `wifi_switch(1)` come first when Wi-Fi is on (coexistence) |
| `btStartSearch` / `btStopSearch` | `0x4d3d50` / `0x4d3840` | `void()` | start sets `bt_searchtime` 50; our timer must count it down and call stop, and stop on every exit (`0x12c`, `0x12e`, close) |
| `getSearchResult` | `0x4d3b94` | `int()` | refills show and pair lists; D-Bus call |
| `getBluetoothNum` / `getBtMessageIndex` | `0x4d3dd4` / `0x4d3e4c` | `int()` / `(int *P, int *C)` | only to follow stock's row numbering; our rows need only the list sizes (`deque_size`) |
| `checkPairDev` | `0x4d38f8` | `int(const char *mac)` | takes the mutex `0xa04528` |
| `handleBluetoothLink` / `handleBluetoothPair` | `0x4d5308` / `0x4d66e4` | `int(int show_index)` | the connect / disconnect and forget; results as section 3; blocking on the UI thread; touch no widget |
| `adjustA2dpVolume` | `0x4d28ac` | `int(int up)` | |
| `switchBtPriority` | `0x4d3024` | `int(int coding)` | three libbtctl calls |
| `bluetoothLink` | `0x4d2778` | `int(int mode)` | starts the connect thread; `2` after a codec change while linked |
| `get_bluetoothcoding_text` | `0x4da15c` | `int(int i, char *out)` | copies the tr key of codec `i` into `out` and answers 1; -1 for `i >= 8` (a signed test: a negative `i` reads before the table) |
| `getBtLinkSize`, `getBtLinkItem` | `0x4d4364`, `0x4d4938` | `int()`, `(int i, int *status, char *mac)` | the last item gives the row's connecting / connected state |
| `getLocalBtName` | `0x4d31c4` | `(char *name, char *mac)` | |
| `write_int_config` | `0x4d6a2c` | `(int v, "SYSSET", key)` | for `BTCODING` |
| `save_stop_player`, `save_start_player`, `judge_outputdevice`, `set_outputchannel`, `set_devicevolume`, `mclGetOutputWay`, `mclGetSavePlayStatus` | `0x4e2304`, `0x4e23e8`, `0x4d70ac`, `0x4d6f68`, `0x4d6cf8` | | the output restore the handlers repeat after a disconnect or forget; they are *not* repeated inside `switchBluetooth` / `handleBluetoothLink` for the Quality path |
| `wifi_switch` | `0x507a8c` | `(int)` | as the Wi-Fi page already pins it |

Stock handlers that cannot be called: the row handler `0x4a3a7c` and the Quality choice handler `0x4a4850` look their widgets up by name
(`bluetooth_scrollview`, `image_choice%d`, `bt_search_icon`), read `item->name` as the row number, and open stock dialogs and pages; the rebuild
`0x4a3734` rebuilds stock's scroll view. So the own page reproduces their sequences with the calls above, in the same order (the tables
in section 3). Hazards:

- **`btStartSearch` without a timer.** With `bt_searchtime` stuck at 50 the next `btStartSearch` is ignored and discovery never stops. Stop on the
  window's `0x12c`, `0x12e`, close, and when `bluetoothflag` goes to 0.
- **UI-thread blocking.** `switchBluetooth` (off), `handleBluetoothLink`, `handleBluetoothPair` and `getSearchResult` block the UI thread as stock does
  (tens to hundreds of ms; not timed); the long waits are in the threads. The spinner animation stops while they run; stock has the same limit.
- **`bluetoothInit` can wait** in a `usleep(100000)` loop on the UI thread while an earlier init thread is still alive.
- **Order matters** where the Quality handler sets `btcoding` before `switchBtPriority` (delay slot) and, in the connected case, zeroes five state
  words and re-routes the output before the reconnect; `switchBluetooth`'s off path stops a SyncLink first; the forget path disconnects before
  `removePairDev`.
- **Re-entrancy.** The idle handler's `checkBluetoothStatus` runs between our UI events and changes the same words (finishing a link, restoring the output,
  clearing the lists). It never runs inside our handler, but a list index taken before a blocking call can be stale after it: re-read the sizes.
- **Pins** (`tools/pod_pins.py` `BLUETOOTH_PINS`, a mismatch fails the build; the words are listed there as runs, see "Control layer"): the data words above; the call sequences of `switchBluetooth` (stores and calls from
  `0x4d5178` to `0x4d52e4`), `handleBluetoothLink` `0x4d5340..0x4d5548`, `handleBluetoothPair` `0x4d672c..0x4d685c`, the switch row in the handler
  (`0x4a3ad8..0x4a3b94`), the device-row decisions (`0x4a3c20..0x4a3f58`), the Quality handler (`0x4a485c..0x4a4af0`), the timer (`0x4a3fa0..0x4a4114`),
  `getBluetoothNum` / `getBtMessageIndex`, `switchBtPriority`'s jump table (`0x74a4b0`), the codec table (`0x97ca08`), the config clamps (`0x4e5b60..0x4e5c28`);
  take the words with `tools/disasm.py words`.

## Control layer (`patch/btset.c`)

`patch/btset.c` / `btset.h` are what the page calls: no widget is made or touched, every action is stock's own sequence (sections 3 and 4) with stock's functions
and words, in stock's order. The page (`patch/btpage.c`, below) calls it; the one entry point nothing calls (`bs_codec_key`, stock's key of a codec; the page uses its own keys) is kept by `tools/pod.py` `BS_KEEP`. Action functions
answer `BS_REBUILD` (stock rebuilds its list after this action: read the state again, lay the page out again) or `BS_NONE`. A device is named by its MAC string
(`struct bs_dev.mac`); the show-list index stock's functions take is looked up in `pdeq_btshowlist` right before the call, because the lists are refilled by
`getSearchResult` (the tick, the idle handler, an action) and an index kept from the last draw can mean another device. Every action that stock's row handler
guards answers a toast "Bluetooth Starting" (kind 1, 2000 ms) and nothing else while `bt_initstatus != 0`; device taps and the codec choice are ignored
while `bt_connectstatus != 0`.

| Function | Does | Returns / the page does |
|---|---|---|
| `bs_on()`, `bs_starting()`, `bs_scanning()` | `bluetoothflag != 0`; `bt_initstatus != 0`; `bt_searchtime > 0` (a signed byte) | 0 / 1 |
| `bs_codec()` | `btcoding`, 0 when not 0..7 (as `config_init`) | the row's check |
| `bs_codec_key(i)` | stock's tr key of codec `i` through `get_bluetoothcoding_text` | the key (valid until the next call) or 0 for `i` outside 0..7; the page shows `TR(key)` |
| `bs_name()` | `localBtName` (refreshed by `bs_open` and by stock after each init) | the controller's name; the row's text is `bt_name` with it |
| `bs_devices(out, max)` | the show list in stock's order (paired first), per entry `mac`, `name`, `paired` (`checkPairDev`), `state` | the count; `state` `BS_DEV_CONNECTING` / `BS_DEV_CONNECTED` give the second line "Connecting" / "Connected"; else "Paired" when `paired`, else none. The state rule is `btdevice_listitem_layout`'s: only the last link item counts (same MAC; Connecting while `bt_connectstatus == 1`; Connected while its status is 3 and `bt_showcoding` is 1..4 or 13). The `bt_del` icon of stock is on paired rows and on a connected one |
| `bs_volume_ok()` | the conditions under which `adjustA2dpVolume` acts: Bluetooth on, link up, codec known, no receiver page | show the Headset Volume Control row only then (the volume reading, which stock ignores at 128 and up, cannot be known) |
| `bs_modal()` | 1 while a stock dialog of ours is up | the page's tick returns at once then (as `wp.modal` in the Wi-Fi page); stock's own timer keeps running under its dialogs |
| `bs_init_guard()` | the toast above | 1 when it was shown: the page must call it first for the rows that do not call an action (Quality, Volume rows) |
| `bs_toggle()` | the switch row: with Bluetooth off and Wi-Fi on a confirm `msg_bt_open` (kind 5; OK keeps Wi-Fi on, as `tools/coex.py` leaves stock's handler: no `wifi_switch` call), then `switchBluetooth(bluetoothflag, 1)` | `BS_REBUILD` (also after Cancel, as stock), `BS_NONE` while the init runs. May block (section 2) |
| `bs_open()` | stock's page init without widgets: `bt_searchtime`, `wifiset_refreshflag`, `bt_start_scan` cleared; with Bluetooth on and no init: `localBtName` / `localBtMac` cleared, `getLocalBtName`, `btStartSearch` | call it once when the page opens; then lay out |
| `bs_tick()` | stock's 200 ms timer without widgets: consumes `wifiset_refreshflag`; Bluetooth on: init spinner count-down (`bt_inittime`) or the scan count-down (count 1: `btStopSearch` + `getSearchResult`; multiples of 25: `getSearchResult`), or `bt_start_scan` -> `btStartSearch` | a bit set: `BS_T_REBUILD` lay the list out again; `BS_T_SPIN` set the spinner image `search<n mod 8>` with `n = BS_T_SPIN_N(r)` (signed). Run it from the page's own 200 ms timer, and only while the page is in front; nothing else decrements `bt_searchtime` |
| `bs_close()` | `btStopSearch()` | the page calls it on return, to-background, close (stock's `0x4a29cc`, `0x4a2a20`, `0x4a28bc`) and when the switch turns off |
| `bs_search()` | the Search row: `btStartSearch()` (ignored while a scan runs) | `BS_NONE`; the spinner follows from the tick |
| `bs_link(mac)` | a device row: `btStopSearch`, `handleBluetoothLink(index)`; -1: toast `msg_closesynclink` (2000 ms); 1 (it was connected, now disconnected): output restore, toast `msg_disconnected` (2000 ms), `save_start_player(1)` (no `getSearchResult`, as stock); 0 / 2: nothing more | `BS_REBUILD` except for -1 and an ignored tap; a device no longer listed: only `btStopSearch`, `BS_REBUILD` |
| `bs_forget(mac)` | the tap on `bt_del`, from stock's confirm on: `btStopSearch`, confirm `msg_unpairing` (kind 1), `handleBluetoothPair(index)` (index looked up again after the confirm); results other than 1 / 2 stop; 2 (it was the connected one): output restore; toast `msg_unpaired` (4000 ms), `getSearchResult`, `save_start_player(1)` | `BS_REBUILD` after an unpair; `BS_NONE` for Cancel, a device that is not paired, a failed unpair |
| `bs_codec_set(c)` | the Quality choice: refused for `c` outside 0..7, while a connect runs, or when it is the current one; connected (link up and codec known): confirm `msg_btreconnect` (kind 1), `save_stop_player`, the five words (`bt_linkstatus` 0, `bt_showcoding` 0, `bt_a2dp_direction` 0, `bt_recv_volume` -1, `a2dp_eventstate` 0), output restore; then `btcoding = c`, `switchBtPriority(c)`, `write_int_config(btcoding, "SYSSET", "BTCODING")`, `bluetoothLink(2)` only when connected, `wifiset_refreshflag = 1` | `BS_REBUILD` when the choice was taken (move the check; the redraw flag is also set), else `BS_NONE` |
| `bs_volume(up)` | `adjustA2dpVolume(up)` (1 volume up, 0 down) | whether `bs_volume_ok()` held |

The output restore is stock's: `headset_output = judge_outputdevice(headset_output, 2)` when that differs (stored before the next call), then
`set_outputchannel(headset_output, 3, 0)` unless `mclGetSavePlayStatus() == 1`. The confirms and toasts are stock's dialogs filled as stock fills them (the
confirm through `pod_confirm_dialog` with its dim scrim, the toast through the new `pod_toast_ms` in `patch/shuffle.c`, which `pod_toast` now calls with
2000 ms); the texts are `TR(key)` of stock's keys. They are modal: the call returns once the dialog is closed.

Hazards for the page: the actions block the UI thread as stock does (section 2); after any action read the state again (the three lists, `bluetoothflag`,
`bt_connectstatus`), never keep an index; `bs_devices` fills `struct bs_dev` of 290 bytes each, so give it a static array; `wifiset_refreshflag` is shared with
the Wi-Fi page and with `checkBluetoothStatus` (the idle handler sets it on every status change), `bs_tick` consumes it; `btrecv_pageflag` is the word
`DROPDOWN_BUSY` names in `tools/pod.py` (`0xa05a00`, the pull-down tile handlers test it too).

**Pins.** `BLUETOOTH_PINS` (`tools/pod_pins.py`) are stock's words, as runs, for: the row handler's guard, switch, Search, device-tap, forget and link-result
sequences and its init toast (`0x4a3abc..0x4a3f9c`); the timer (`0x4a3fa0..0x4a4118`); the page init (`0x4a411c..0x4a4270`); the return, to-background and close
handlers; the Quality handler (`0x4a4898..0x4a4aec`, `0x4a4bf0..0x4a4c24`); `switchBluetooth` (`0x4d5178..0x4d5304`); the entries of `handleBluetoothLink` /
`handleBluetoothPair`; the last link item, the MAC compare, status 3 and the codec test of `btdevice_listitem_layout`; `adjustA2dpVolume`'s conditions;
`get_bluetoothcoding_text` and the eight table entries at `0x97ca08`; `getBtLinkItem`'s range check; `config_init`'s `BTCODING` clamp. `0x4a3b64` is pinned as
stock's `beqz` (`tools/coex.py` turns it into a branch later in the build). The words are `DATA` entries of `tools/pod.py` (`BT_*`, dynsym-checked) and
`FUNCTIONS` entries (`switchBluetooth`, `btStartSearch`, `btStopSearch`, `getSearchResult`, `checkPairDev`, `getBtLinkSize`, `getBtLinkItem`, `getLocalBtName`,
`switchBtPriority`, `bluetoothLink`, `adjustA2dpVolume`, `get_bluetoothcoding_text`, `handleBluetoothLink`, `handleBluetoothPair`, `judge_outputdevice`,
`mclGetSavePlayStatus`).

**Tests** (`test/pod/btset.py`, Unicorn). Stock's handlers run on the built `demo` (so the switch row is as coex leaves it) with the backend, the output calls and
the page's helpers (`0x4a3734` rebuild, `0x4a2dd4` spinner, the label helpers) mocked as recorders that log every call with its arguments and the state words at that
moment; ours runs on the same state; the final words, the ordered calls and the state at each must be equal, and ours' answer must say what stock's rebuild did.
`switch_tests`: bluetooth on/off x Wi-Fi x confirm x init status (24 states), no `wifi_switch`. `scan_tests`: the page init over 48 states, the timer one tick at a time
over 792 states, the whole count-down (60 ticks, started by the page init, by `bt_start_scan`, by the Search row: refreshes at 5 s and at the end), Search and the three
close handlers. `link_tests`: every device row of four list shapes x link result -1/0/1/2 x output-restore variants x connect/init guards (stock's row numbers, the
index handed to stock). `forget_tests`: every paired row x confirm x pair result 0..3 x variants, plus not paired, not listed and a list refilled under the confirm.
`codec_tests`: 3 old codecs x 8 choices x 6 link states x confirm x restore variants x `bt_connectstatus` (1728). `volume_tests`: stock's `adjustA2dpVolume` run for
real over 336 states, `bs_volume_ok` against whether it reads the volume. `list_tests`: `bs_devices` against `btdevice_listitem_layout` on 15 link lists x 4 rows (MAC
compare, connecting, connected, paired, none, the icon). Not covered: the radio, `getSearchResult` and `handleBluetoothLink` themselves (mocked), the dialogs' look.

## The page

`patch/btpage.c` + `ui/m1plus_bluetooth.bin` (`tools/pod_ui.py build_bluetooth_page`, `Page` `BLUETOOTH_PAGE`, page index 113) and the Audio Codec picker `m1plus_btcodec` (`BTCODEC_PAGE`, index 114; both near the end of `PAGE_ORDER`, followed by the device page). It is the [Wi-Fi page](wifi.md)'s layout and numbers (the Settings cards in the stock list under our navbar, 52 px rows, the same pieces, hairlines, check, spinner `wf_spin0..7` and info glyph `wf_info`; no image was added) with the Bluetooth rows; `bp_*` helpers of the card list (`wp_put`, `wp_vis`, `wp_piece`, `wp_pos`, `wp_clamp`, `wf_on_scroll`, `wk_subst`) are the Wi-Fi page's, made non-static and declared in `patch/entries.h`. The page only lays out and calls the control layer above; it touches no Bluetooth word and no backend function.

**Rows** (display order, widget names; every row child is insensitive, the row takes the tap; hidden rows are also insensitive):

| Widget | Shown | Content |
|---|---|---|
| `bt_row_sw` (`bt_sw_label`, `bt_sw_img`, `bt_hair_sw`) | always | the Bluetooth switch (`sset_on` / `sset_off`); the single card when off, the top of card 1 when on |
| `bt_row_codec` (`bt_codec_label`, `bt_codec_val`, `bt_codec_chev`) | on | Audio Codec, value = stock's `btcoding` by `bp_codec_text` (below), Settings chevron; the value takes the room its text needs (`bp_value_fit`, 140 px at most; the label keeps the rest). Tap = `bs_init_guard()`, then the picker |
| `bt_note` (`bt_note_t`) | on, name not empty | grey note `This player is shown as “<bs_name()>”` (the cards pages' 15 px note, `wk_subst` into the translated template; the name goes through `wf_utf8`) |
| `bt_hdr_my` | a paired device | "My Devices" |
| `bt_row0 .. 7` (`bt_chk`, `bt_name`, `bt_info`, `bt_hair`) | the paired devices, in the list's order | check when `BS_DEV_CONNECTED`, a `wf_spin` frame while `BS_DEV_CONNECTING`, nothing otherwise; the name (UTF-8, cut with an ellipsis to the label's room by `az_fit_room`: 206 px); the info glyph at x 274 |
| `bt_hdr_oth` (`bt_hdr_oth_t`, `bt_hdr_oth_spin`) | on | "Other Devices", the header spinner after its text (measured: `bp_spin_place`) while `bs_scanning()` or `bs_starting()` |
| `bt_row8 .. 23` | the unpaired devices | the same row without the info glyph (name room 238 px); a tap = `bs_link(mac)` = pair and connect |
| `bt_row_search` (`bt_search_label`) | on, not scanning and not starting | "Search Again", the last row of the Other Devices card (text at x 54 as the Wi-Fi page's Other...); alone as a single card when nothing was found; `bs_search()` |

While scanning with no device found there is no card, only the header and the spinner. Off: the switch row alone. The scroll view and list carry stock's names `bluetooth_scrollview`, `bluetooth_listview`.

**Pools.** 8 paired rows (`BP_MY`), 16 other rows (`BP_OTH`), and the show list is read up to 32 devices (`BP_DEVS`; paired first, so a long paired list can push the unpaired out of the 32). Stock's lists are unbounded; the Wi-Fi page's pools (16 saved, 32 found) hold networks seen on a scan, here a player pairs a handful of devices and a scan finds the few in range. A `struct bs_dev` is 290 bytes, so the page's state is about 10 KB of the payload's `.scratch`. Devices past a pool are dropped (a paired one beyond the 8th is not listed; the others are not shown in its place).

**Actions and state.** Every action is followed by a full read of the state and a layout (`bp_layout` calls `bs_on`, `bs_starting`, `bs_scanning`, `bs_codec`, `bs_devices`, `bs_name`); no index is kept, a tap hands the device's MAC (copied first) to `bs_link`. The switch calls `bs_toggle` (and `bs_close` when it is off afterwards); a device row `bs_link(mac)`; the info glyph (a tap at x 264 or right of it on a paired row) `bp_open_info(mac)`; Search Again `bs_search`; the codec row opens the picker. Taps are ignored while `bs_modal()`.

**Timer and life.** One 200 ms timer owned by the page (stock's period). `bp_tick` does nothing while the page is not in front (`EVT_WINDOW_TO_BG` clears the flag, `TO_FG` sets it) or `bs_modal()`; else it calls `bs_tick` and lays out again on `BS_T_REBUILD` (a search count-down result, stock's redraw flag), or when what the layout shows (Bluetooth on, starting, scanning) differs from `bs_on` / `bs_starting` / `bs_scanning` (a change nobody flagged); otherwise it only moves the spinners (`bp_spinner`: one `wf_spin` frame a tick; `BS_T_SPIN` is not used). `btpage_open()` runs `bs_open()` after the timer exists (the search starts as the page opens, with Bluetooth on and no init running) and lays out; `EVT_WINDOW_WILL_OPEN` lays out again (names are measured in the style the window resolves), `EVT_WINDOW_TO_FG` reads everything again. `bs_close()` (the search is stopped) runs on Back, Now Playing (`bp_on_back`, `bp_on_player`, then stock's handlers), to-background, `EVT_WINDOW_CLOSE` and destroy, and when the switch turns off. A window or asset that will not open, or a timer that does not start, returns -1 with nothing started (the caller opens stock's page).

**Audio Codec picker.** The generic check rows of `patch/m1plus.c` (`pick_tab`: `{-1, VK_NONE, ACT_BTCODECSET, bp_codec, bp_codec_set}`), eight rows in stock's order (`btcoding` 0 .. 7). `ACT_BTCODECSET` = 166 is the only action id added (arg = `btcoding`); `bp_codec_set(c)` = `bs_init_guard()`, `bs_codec_set(c)`, then 0 when `bs_codec() == c` (the check moves) else -1 (a cancelled "Reconnect Bluetooth?", a connect running, the init guard: the check stays). Opened by `pod_open_btcodec()`. Texts: the three LDAC rows are our keys `LDAC HQ`, `LDAC Standard`, `LDAC Connection` (stock's Thai LDAC HQ reads "SyncLink", its Spanish, Polish, Russian and Ukrainian ones do not fit a row; "(auto)" is dropped from Connection), the others are stock's keys `btcode_aptxhd`, `btcode_aptx`, `btcode_aac`, `btcode_sbchq`, `btcode_sbc` (the same brand text in every table); the codec row's value uses the same eight keys (`bp_codec_text`, so the value is not `bs_codec_key`'s stock text).

**Entries.** Settings > Bluetooth stays the `ACT_STOCK` row (`STOCK_BLUETOOTH`, its On / Off value): `m1plus.c` calls `btpage_open()` first and opens `systemset/bluetooth_page` only when it returns -1. The All System Settings hub's Bluetooth row (thunk `0x4b1408`) has its `jalr navigator_to` at `0x4b1428` hooked ([payload](payload.md) hook 32, `BTHUB_SITE`, `bt_hub_open`): our page, stock's with `/mnt/mmc/m1plus-off` or where ours will not open, as the Wi-Fi hub row (hook 21). The Control Center Bluetooth tile is unchanged.

**i18n.** New English-keyed texts in `tools/pod_i18n.py`: `Audio Codec`, `LDAC HQ`, `LDAC Standard`, `LDAC Connection`, `My Devices`, `Other Devices`, `Search Again`, `This player is shown as “%s”` (13 languages each; `Bluetooth` exists), and the stock keys `btcode_*` of the five brand rows in `STOCK`. The Audio Codec label is short in German, Spanish, Italian, Russian and Ukrainian ("Codec", "Códec", "Кодек") and Thai, so that it fits beside the longest value (`LDAC Connection`) in the value row's 254 px; the note drops "This player" in the languages where it was too long beside a 16 character name.

**Tests** (`test/pod/btpage.py`, the control layer's backend mock of `test/pod/btset.py`): `asset_tests` (stock's names and list geometry, display order, every row's boxes against the Wi-Fi page's, texts and styles, the hidden start state, the picker asset, every text against its room in the 13 languages), `layout_tests` (off, on and scanning, found and paired devices, search ended, starting, connected / connecting, names UTF-8 / long / bad bytes, the pools and the 32 read, to-foreground, will-open), `action_tests` (each tap and the stock call and index it reaches, the info glyph, the stale list, the init guard, Back and Now Playing), `timer_tests` (the 49-tick count-down, only in front, none under a dialog, a flagged and an unflagged change), `life_tests` (every exit stops the search, a second open, a stale destroy, assets and timers that fail), `codec_tests` (the check per `btcoding`, the tap, the reconnect question cancelled or confirmed, the init guard), `settings_tests` (the Settings row, the hub hook, its pins, the kill switch). `test/pod/settings.py`, `wifipage.py`, `scrobpage.py` and `i18n.py` follow the new page, the id and the texts.

**Deviations from stock's page:** the layout is ours (cards, My Devices / Other Devices, check or spinner and an info glyph instead of the Connecting / Connected / Paired lines and the `bt_del` icon); no Bluetooth Name row but a grey note; no Search row: the search starts as the page opens (stock's init does that too) and Search Again closes the Other Devices card once it ended; the Quality row is Audio Codec with its picker (and no "Quality" wording); Forget and Headset Volume Control are on the device page (below); "Paired Device" / "Compatible Device" are My Devices / Other Devices; the device list shows no second line.

**Not verified:** everything on a device (BT-01 .. BT-14 above apply to this page). The page's layout against the real list under the real window styles, the info glyph's 264 px hit line on a device row, the header spinner's place in the languages, the picker through a real reconnect.

## The device page

`patch/btpage.c` (`bd_*`) + `ui/m1plus_btdevice.bin` (`tools/pod_ui.py build_btdevice_page`, `Page` `BTDEVICE_PAGE`, page index 115, last of `PAGE_ORDER`; no action id, no hook). The info glyph of a paired device's row (a tap at x >= 264, `BP_INFO_X`) calls `bp_open_info(mac)`, which opens it (`bd_open`); a tap left of the glyph is still the row's connect / disconnect. It is the [Wi-Fi info page](wifi.md)'s look and mechanics: the Settings cards under our navbar, one centred label per single-row card, 20 px gaps between cards, the same Back and Now Playing buttons. The page keeps the device's MAC (copied at open; no list index is kept) and reads the device from the show list by it every time.

| Widget | Shown | Content / action |
|---|---|---|
| `label_title` | always | the device's name (UTF-8, cut with an ellipsis by `az_fit`) |
| `bd_nm0`, `bd_nm1` (`bd_name0`, `bd_name1`) | only when the title was cut | the whole name above the cards in one grey line, or two (`wf_name_lines` / `wf_name_put`, the Wi-Fi info page's code made shared; names of up to 128 characters, a longer one ends with an ellipsis) |
| `bd_row_link` (`bd_link_t`) | always | "Disconnect" while `bs_devices` says the device is `BS_DEV_CONNECTED`, else "Connect"; a tap = `bs_link(mac)`, then the state is read again (the page stays). While the device is `BS_DEV_CONNECTING` the text is "Connect" at 60 % opacity (`BD_DIM`, as the dimmed rows of other pages) and the row is insensitive; stock ignores a tap while any connect runs |
| `bd_gap0` | always | 20 px |
| `bd_row_vol` (`bd_vol_t`, `bd_vol_dn`, `bd_vol_up`), `bd_gap1` | the device is the connected one and `bs_volume_ok()` | "Headset Volume" and two keys at the right, minus and plus: buttons 46 x 52 px (a 38 x 34 pill centred in each) with the images `pod_ic_btvol_dn` / `_up` and their lighter pressed twins `_down` (`tools/mod_icons.py`, neutral greys, white glyph). Each key = `bs_init_guard()`, then `bs_volume(0)` or `bs_volume(1)`: one step per tap, no repeat, no value (stock's `btvolume_page` has no readout either). The row has no handler and its pressed picture is its normal one: a tap beside the keys does nothing |
| `bd_row_forget` (`bd_forget_t`) | always | "Forget This Device" in the label ink the Wi-Fi page's Forget This Network has (white, 21 px, centred); `bs_forget(mac)` asks stock's "unpair?" and shows the toast itself. The page closes when the device is no longer paired afterwards (back to the Bluetooth page), and stays when the question was cancelled, the unpair failed or a connect is running |

Hidden widgets, the keys included, are insensitive. The scroll view is `btdevice_scrollview`.

**Reading and the timer.** `bd_read` takes `bs_devices` into the Bluetooth page's own array (the page is below this one and lays itself out again when it returns) and finds the device by MAC; it is the same call the Bluetooth page's tick makes, and it reads the link list, `bt_connectstatus` and `bt_showcoding` stock's idle handler keeps up to date (`checkBluetoothStatus` on every status change), so a link that completes while no scan timer runs shows without a tap. The page never calls `bs_tick` (the search is stopped when the Bluetooth page goes to the background and nothing here starts one) and never reads or clears `wifiset_refreshflag`, so the Bluetooth page's own re-read is not starved. One 500 ms timer (`bd_tick`) runs `bd_refresh` only while the page is in front and `bs_modal()` is 0; `EVT_WINDOW_TO_FG` reads again at once (not under a dialog of ours); every action reads again after it. The name is fitted at open and again from the whole name on `EVT_WINDOW_WILL_OPEN` (`bd_fit_name`: the title and the name lines are measured in the style the window resolves), and the page is laid out again. The layout is redone only when what it shows changed (the device's state and whether the volume card is up). When the device is not in the list or no longer paired, or Bluetooth is off (the Control Center tile), the page closes once (`navigator_back`); a device that left the list between the row's draw and the glyph tap opens no page and the Bluetooth page lays out again.

**Pools.** None: one device. The page state is about 330 bytes of `.scratch`; the device array is the Bluetooth page's.

**i18n.** `Connect`, `Disconnect`, `Headset Volume` and `Forget This Device` (13 languages; the last is the Wi-Fi key's wording). `Headset Volume` has 174 px beside the keys: Russian reads "Громкость", Spanish "Volumen auricular".

**Tests** (`test/pod/btpage.py`): `dev_asset_tests` (registration and index, names and display order, the boxes against the Wi-Fi info page's, the Forget ink equal to Forget This Network's, the key buttons and their images and pressed twins, neutral greys, the hidden start state, every text against its room in 13 languages), `device_tests` (layout for a device that is not connected, connected and connecting; each tap and the stock call and MAC it reaches; Connecting then Connected by the timer alone; Disconnect and its toast; SyncLink; Forget confirmed, cancelled, failed, of the connected device, under the init guard; Back and Now Playing), `devlife_tests` (the timer reads the list only and leaves the redraw flag and the search alone; to-foreground and to-background; no read or tap under a dialog; the Bluetooth page's re-read on return; the device gone, Bluetooth off, no longer paired; destroy, reopen, wrong asset, no timer, no window), `devvol_tests` (the card's visibility rule, one condition at a time, both keys, the init guard), `devname_tests` (short, cut, two-line, non-ASCII, long and 255 byte names; a name fitted again in the title's style when the window is about to open; the page follows its device by MAC when the list changes).

**Deviations from stock:** stock's Headset Volume Control is a row of the Bluetooth page that opens `btvolume_page` (two 100 px buttons); here its two keys are on the device page, only for the connected device, and `btvolume_page` is not opened. Forgetting is a button, not the `bt_del` icon; connecting and disconnecting are on the page as well as on the row. **Not verified:** everything on a device (BT-06, BT-08, BT-10, BT-12 below); the opacity of the dimmed "Connect" and the touch size of the keys; the 500 ms timer's cost with 32 devices.

## 7. Tests

Emulator tests of the control layer are in "Control layer" below (`test/pod/btset.py`). `getBluetoothNum`, `getBtMessageIndex`, `switchBtPriority`
(libbtctl calls mocked; the three arguments per value), the config clamps, `getSearchResult` and the link-list functions are not run there; they could
run with `deque_*` and `pthread_*` mocks and a fake `btctl_get_device_list`. No emulator test can show that a radio, a pairing, a codec negotiation or
an AVRCP volume works.

Device checks (hardware only):

| Id | Check |
|---|---|
| BT-01 | Open the page with Bluetooth off: one switch row; switch on: "Bluetooth Starting" toast on any tap until the init finishes, then the rows appear and a scan starts (the header spinner) |
| BT-02 | Switch off while connected: the output returns to the jacks, playback restores, rows collapse to one |
| BT-03 | Switch on with Wi-Fi on: the confirm, OK leaves Wi-Fi on (coexistence), Cancel changes nothing |
| BT-04 | A scan lasts about 10 s, results refresh at about 5 s and 10 s, the spinner stops and Search Again appears and starts a new scan |
| BT-05 | Leave the page during a scan (back, to-background by the pull-down, power key, opening a device page): the scan stops and a later one starts |
| BT-06 | Paired device: a tap on its row, or Connect on its device page, shows the spinner ("Connect" dimmed on the device page) and then the check ("Disconnect"), with no tap, also when the connect ends while the device page is open; Disconnect (page or row) shows the "Disconnected" toast and the page reads "Connect" |
| BT-07 | Unpaired device: a tap pairs (legacy and SSP devices) and connects within 15 s plus 10 s; a failed pairing returns the row to normal |
| BT-08 | Forget This Device (device page): the confirm, "Unpaired" toast, back on the Bluetooth page the device is under Other Devices; Cancel stays on the page; forgetting the connected device restores the output |
| BT-09 | Audio Codec: each of the 8 rows saves `BTCODING`, survives a reboot, and the reconnect confirm appears only while connected; Cancel leaves the old choice |
| BT-10 | Headset Volume (device page, connected device only): the minus and plus keys change the headset's volume by about 10/127 per tap, light up while pressed, and the card is absent when not linked and for the other paired devices |
| BT-11 | Two taps while connecting are ignored; a tap while SyncLink over Bluetooth is on shows "Please close SyncLink" |
| BT-12 | A connection made from the other side (a paired headset powering up, auto-reconnect at boot) shows in the open Bluetooth page and in an open device page without a tap |
| BT-13 | The Control Center tile and our pages agree after toggling one from the other; switching Bluetooth off from the tile closes an open device page |
| BT-14 | The note under the Audio Codec row shows the controller's name; a very long device name and a non-ASCII name are cut with an ellipsis in a row, in the device page's title and above its cards, and do not corrupt anything |

## 8. Not verified

- Anything on a device (all BT-xx above).
- The event codes of the libbtctl status callback (`0x4d4738`) beyond 3 (connected), 4 (disconnected) and 5 (written when a remote connects
  while no link was started by us): 6..9 are written through `updateBtLinkStatus` but their meaning was inferred from the poll loops only. That
  link status 1 means "connecting" is from `handleBluetoothLink`'s own `addBtLinkItem(mac, 1)`.
- The thread the libbtctl callbacks run on, and whether `btctl_*` calls are safe from another thread; `btctl_create_daemon_thread` was not read.
- `bluetoothLink`'s mode argument: 0 (pair first), 1 and 3 (connect), 2 (disconnect, wait, connect) is read from the thread's branches, not from
  every path; the exact wait loops (which status ends which loop) were read only as polls with the counts above.
- `checkBluetoothStatus` beyond the init finish and the connect finish: the remote disconnect, `bt_backlinkstatus`, the AirPods retry, the A2DP event
  state and the route to Bluetooth were skimmed through their stores and calls (section 5), not traced path by path. Which return value is 2
  was not traced either; the receiver-page trigger is inferred from `on_wm_idle_status` `0x4ce9d4..0x4ce9ec`.
- That the click's x is `+0x18` of the event (compared with `0xe6`); inferred from AWTK's `pointer_event_t` layout, not from `libawtk` code.
- That `0x12e` is `EVT_WINDOW_CLOSE` (it follows `0x12d` in AWTK's numbering; the pull-down doc lists it as a non-click event).
- That `msginfo_dialog` returns only after it closes (the code after it, `getSearchResult`, `save_start_player`, the rebuild, assumes it can run
  after; the dialog is modal for `confirminfo_dialog`, [overlays](overlays.md)).
- What `init_usersetting`, `into_standby` and `into_poweroff` decide before calling `closeBluetooth` / `bluetoothInit` / `btDisconnectAll`.
- `SetBtCommandReq` (SyncLink) and whether it can change Bluetooth state; `stop_btsynclink` / `start_btsynclink` bodies.
- What `0x4d231c`'s prompt type 5 is (a passkey or a confirmation) and how `on_wm_timer_dialogresponse` shows `promptinfo_bt`.
- `btcoding` 0 and 1 jump to the same target in `switchBtPriority`'s table (read, not understood: LDAC HQ and Standard make the same calls).
- The libbtctl argument values (`0x13`, `0x16`, `0x18`, `0x12`, `0x11`, 2, 0) as codec masks or enums; only the numbers are known.
- That no other writer of `bluetoothflag` or `btcoding` is reached through data pointers (only direct GOT-based xrefs were searched); the xrefs
  of `bluetoothflag` itself were not enumerated for writers beyond `switchBluetooth` and `config_init`.
- The Chinese strings for the rows are the stock values; whether other languages use usable translations was not checked.
