# Network Services and Wi-Fi Transfer

Settings > Network Services (`m1plus_netservice`, `NETSERVICE_PAGE`) and its Wi-Fi Transfer page (`m1plus_wifitransfer`, `WIFITRANSFER_PAGE`) replace stock's `systemset/netservice_page` and `systemset/wifitransport_page`
(All System Settings keeps stock's own row and pages as they are). Sources: `patch/netservice.c`, `patch/m1plus.c` (rows, open, exits), `tools/pod_pages.py`, `tools/pod_pins.py` `NETSERVICE_PINS`, `test/pod/netservice.py`.
The state is stock's own bytes, nothing of ours is saved. Addresses below were read in `work/cache/demo.dis`.

## Pages

| Page | Rows |
|---|---|
| Settings (first card) | Wi-Fi, Bluetooth, **Network Services** (glyph `network`, ACT_PAGE) |
| Network Services | AirPlay (switch, ACT 166, `airplay`), DLNA (switch, 167, `+dlna:filled`), a gap, **SyncLink** (link, `ACT_STOCK` `STOCK_SYNCLINK`, `link`: stock's synclink page, Back returns here), **Wi-Fi Transfer** (link, 168, `folder-sync`) |
| Wi-Fi Transfer | no rows; centred, top to bottom: a hero (a 64 px `#2C2C2E` tile, radius 16, with the white 36 px `wifi` glyph `pod_hero_wifi`; the title in 22 px white; a grey 14 px description of at most two lines), one 60 px address card (`<ip>:8888`, no `http://`, 22 px white in the bold face `lyrics`), and a grey 13 px footer note (own texts, 13 languages); the layout items are `Hero`, `BigCard` and `Note(center=True)` (`tools/pod_pages.py`, `tools/pod_ui.py cards_hero / cards_bigcard / cards_cnote`) |

Keys: `Network Services` (stock's `sset_netservice` is the singular "Network Service"), `Wi-Fi Transfer` (stock's `netservice_wifitrans` is "Wi-Fi file transfer"), the description and the footer note are our own keys translated in all 13 languages
(machine translations, checked for fit); `AirPlay` and `DLNA` are brands. Stock's `wifits_info1` / `wifits_info2` are not used: the English text is long and crowded on a 320 px screen. The Chinese title is "Wi-Fi 传输" / "Wi-Fi 傳輸". The title fits the navbar in every language
(`test/pod/i18n.py` fit checks). Only SyncLink opens a stock page; Wi-Fi Transfer is ours.

## Stock facts

- **The switches.** The rows' click handlers are bound at `0x4a8920` (listitem0, DLNA, handler `0x4a8b14`), `0x4a8954` (listitem1, AirPlay, `0x4a8a84`) and `0x4a8980` (listitem2, Wi-Fi transfer, `0x4a8c2c`). The two switch handlers look up their image,
  call `dlna_switch` (`0x507674`) or `airplay_switch` (`0x5076a8`) and show the byte (`dlnaflag` `0xa05abe`, `airplayflag` `0xa05abd`); **no guard**: the only test is the lookup's null check (`0x4a8abc`, `0x4a8b4c`). Stock's page therefore also lets
  AirPlay be switched while a session plays (the Control Center tiles refuse it: [pulldown](pulldown.md) "AirPlay and DLNA"); ours repeats the page. Neither function starts anything: the network-status timer (`0x4cfd94`) follows the byte only while Wi-Fi is connected.
- **The Wi-Fi transfer row** (`0x4a8c2c`): `networkGetConnectStatus` (`0x4a8c48`); a nonzero answer calls `navigator_to("systemset/wifitransport_page")` (`0x4a8c80`), zero opens `dialog/msginfo_dialog` with `msg_notnetwork` (`0x4a8ba4`).
- **The transfer page's init** (`0x4b1664`): binds window events `0x113` (EVT_KEY_UP, handler `0x4b14d0`) and `0x12e` (EVT_WINDOW_CLOSE, handler `0x4b14ec`) (`0x4b16ac`..`0x4b16e8`), then `networkGetIPAddr(0, buf)` (`0x4b1710`), `stop_player` (`0x4e08c4`, `0x4b1720`),
  `switch_wifitransport(1)` (`0x4b1730`), and prints `http://%s:8888` (`0x4b1794`) into `label_ip`.
- **`switch_wifitransport`** (`0x5075e4`): 1 runs `toolsSystemd("thttpd -C /etc/thttpd.conf")` and stores 1 in `wifitransport_flag` (`0xa05abc`); 0 runs `system("killall -9 thttpd")`, removes `/tmp/thttpd.log` and `/tmp/thttpd.pid` and stores 0.
- **The key filter** (`0x4b14d0`): answers RET_STOP for the key codes `0xd5` .. `0xd7` and RET_OK for every other key (`v1 = 0xb`, `movz v1, zero` unless the code minus `0xd5` is below 3), so those three keys never reach the window manager's key-up handler.
- **The only exit stock handles** is the close event: `0x4b14ec` calls `switch_wifitransport(0)`. `switch_wifitransport` has no other caller (`stock.py callers 0x5075e4`: the init and that handler). Stock's Now Playing button restacks the player over the
  page, nothing is closed, so **stock leaves the server running** there. The byte is also read by `on_wm_tsmove_fun` (`0x4cd7f0`: no pull-down while it is set), `to_poweroptions` (`0x4ce668`, `0x4ce730`: no standby / shutdown countdown) and three DLNA
  renderer functions (`dmrActionGetTransportInfo`, `dmrNotifyPlayStatus`, `dmrNotifyPlayStatusNotStop`); nothing watches Wi-Fi, USB or the lock screen for it, so stock does not stop the server on a Wi-Fi drop.

## Behaviour

- **Switches** (`ns_airplay_toggle`, `ns_dlna_toggle`): call stock's switch, show the byte. Turning one on without Wi-Fi (`networkGetConnectStatus() <= 0`) shows the existing toast "Connect to Wi-Fi first" (as the tiles do; the byte is still stored, it is a preference).
- **Wi-Fi Transfer row** (`ns_transfer_ok`): Wi-Fi connected (status above 0): our page opens; else the toast and no window (stock opens a message dialog instead).
- **Opening the page** (`wt_opened`, after `open_page`): in stock's order, the key filter (same decisions as `0x4b14d0`, own handler), the close handler and a destroy handler are bound, then `stop_player()` and `switch_wifitransport(1)`. A bind that is
  refused starts nothing. The address card's label `pod_big0_t` shows `<ip>:8888` (`wt_url_text`, `networkGetIPAddr` while connected, `-` otherwise; stock prints `http://%s:8888`, ours leaves the scheme out) as the page opens and each time it is back in front (`wt_show`); it takes no tap. The hero's description and the footer are wrapping labels (`pod_note0_t`, `pod_note1_t`, turned on by `wrap_notes`).
- **Leaving the page**: EVT_WINDOW_CLOSE (Back, Home, any close) calls `switch_wifitransport(0)` exactly as stock's handler; EVT_DESTROY does the same for a window that never saw the close event (once per window). **Deliberate difference:** the Now Playing
  button stops the server (stock leaves it running under the player, with the pull-down and the standby countdown blocked); the page starts it again, without stopping the player a second time, when it is back in front (`wt_front`, EVT_WINDOW_TO_FG).
  Wi-Fi dropping, USB, the lock screen and power-off are as in stock (nothing is stopped; the shutdown path is stock's).
- The web page that thttpd serves is unchanged ([wifi-transfer](wifi-transfer.md)).

## Tests (`test/pod/netservice.py`)

`state_tests`: pins; each switch against stock's own click handler (`0x4a8a84`, `0x4a8b14`) from all four byte states (same bytes, one switch call each, no AirPlay-playing guard); the toasts; the row's gate; the address text (`<ip>:8888`); stock's key filter (`0x4b14d0`) and close
handler (`0x4b14ec`) run for real. `page_tests`: pages, rows, titles, ids 166 .. 168, last in `PAGE_ORDER`, glyphs, 13-language keys, the asset (hero, address card and footer geometry, the worst-case width, no scrolling); the open without and with a network (call order, binds, address); our key filter against stock's for 0xd0 .. 0xdf;
the close, destroy, close + destroy, the Now Playing button (two handlers, stop, no second stop), back in front (start, once), the window gone (never started again); a refused bind of each event. Stock's init is not run (its widget visitor needs a widget tree): its order
and binds are pinned.

## Device only

NET-01 AirPlay and DLNA switches change the real services within a second (shairport starts / stops, the DLNA renderer shows up) and survive a reboot. NET-02 Wi-Fi Transfer with Wi-Fi off: the toast, no page, music keeps playing. NET-03 with Wi-Fi: music stops, the address
opens the web app from a computer, and uploads work. NET-04 Back, Home and the Now Playing button each stop thttpd (`ps`; the web app stops answering) and the pull-down works again. NET-05 Now Playing, then Back to the page: the app answers again. NET-06 media keys
(`0xd5` .. `0xd7`) do nothing on the page, volume keys work. NET-07 the address with a three-digit-group IP fits on one line (worst case `255.255.255.255:8888`: 200 px in the 22 px bold face, in a 300 px card). NET-08 the description and footer read well in all 13 languages (the description wraps to two lines, the footer to three) (not reviewed by speakers). NET-09 Wi-Fi dropped while the page is open: the address
turns to `-` the next time the page refreshes (back in front), the server is stopped when the page closes. NET-10 the lock screen over the page and back.
