# Pull-down

**Sources:** `tools/mod_pulldown.py`, `tools/mod_icons.py` (look), `patch/pulldown.c`,
`tools/pod.py` (`PULLDOWN_*`), `tools/pod_pages.py` (tile order and page), `PULLDOWN_PINS`,
`PULLDOWN_FLAG_PINS`, `TSDOWN_PINS` in `tools/pod_pins.py`. **Tests:** `test/pod/pulldown.py`
(look), `test/pod/pdtiles.py` (tiles, flags, swipe gates).

The stock pull-down (`dialog/dropdown_dialog`) restyled, with tiles the user can hide, show and
reorder, six tiles of ours, and two repairs for a pull-down that stops opening. One hook on the
dialog's init and one on touch down ([payload](payload.md)).

## Look

`mod_pulldown.py` runs after the font step on `ui/dialog/dropdown_dialog.bin`.

- The status bar (`view_sysbar`) is laid out from the same table as the real bar
  ([theme](theme.md) "Status bar"), so the two are identical in 12 h and 24 h mode.
- Tile captions go from 18 to 16 px (disabled and focused 14). The caption boxes are 71 x 40 instead
  of 57 x 40 (same centre), because `Bluetooth` is 60 px at 16 and AWTK broke it mid-word. The tool
  refuses a Latin word wider than the box in English or Chinese. A few long captions in other
  languages still overflow, clipped as in stock.
- **Tile art:** every tile image is one 50 x 50 ring style, 2 px ring, 24 px glyph. Off is a
  `#777777` ring and glyph, on is a filled white disc with a `#141414` glyph, disabled is `#444444`.
  Gain has custom 2- and 5-bar glyphs, Output the text "PO" / "LO" in Inter Medium 17 px. A white
  disc, not a white ring: a ring is only a brightness step from the grey ring, and the disc is what
  stock does with its orange fill. With an accent the ON disc is the accent ([accent](accent.md)).

## Tiles: hide, show and reorder

Settings > Appearance > **Control Center** (`m1plus_pulldown`) edits the eight stock tiles and the
six of ours (fourteen rows, at most eight shown). It is the Main Menu page's twin ([menu](menu.md)):
one row per tile with a switch and, on every shown row but the first, an up arrow. The row takes
every tap: the arrow moves the tile one place up, elsewhere shows or hides it, and a tile shown joins
the end. Each change is saved at once and atomically; a failed save is undone. The code is a copy of
`menu.c`'s (`pg_*`).

- Row labels are short texts of ours: Wi-Fi, Bluetooth, Button Lock, Gain, USB Mode, Output,
  Playback, System. Stock captions did not fit beside the arrow, and Gain and USB Mode show state in
  stock. Each row has its tile's 24 px glyph. The one label that does not fit (Russian Playback)
  ends in an ellipsis and scrolls while focused.
- Turning on a ninth tile is refused with the toast "Up to 8 controls".

**File** `/mnt/data/m1plus/pulldown-tiles`: `<shown ids in order>[-<hidden ids>]`, optional newline.
Ids `0`-`7` are the stock slots in order (Wi-Fi, Bluetooth, button lock, gain, USB mode, output,
playback settings, system settings); ours are `8` Sleep Timer, `9` Settings, `a` Equalizer,
`b` Power Off, `c` AirPlay, `d` DLNA. A tile not in the shown part is hidden.

- Invalid or missing means the default: the eight stock tiles in stock order, ours hidden. Invalid
  is an unknown character, an id twice, a second `-`, an empty file, 20 bytes or more
  (`PULLDOWN_FILE_MAX`) or more than eight shown. A bare newline or `-` hides every tile.
- The page writes `<shown>-<hidden in id order>`. Model: `pod_pages.parse_pulldown` /
  `format_pulldown`. The Settings Files page lists the file (first 12 characters, like `home-menu`).

## The hook

`dialog_dropdown_dialog_init` is wrapped by `m1plus_pulldown_init` (pinned prologue, resumed by the
trampoline). Its only caller is the navigator's dialog-init dispatcher, so it runs only when the
pull-down is built and is never boot-reachable. `PULLDOWN_PINS` pins the resume word, the
dispatcher, the pointer binds and the tile visitor's click bind.

- The stock init runs first and its result is returned. Then the eight tile images and captions are
  looked up; **if any lookup fails nothing changes**.
- The file is read. Shown tile k takes the place of stock tile k (positions read from the widgets)
  and its caption keeps its own offset; the other tiles and captions get `visible=false` **and**
  `sensitive=false`. The default file moves nothing. No widget is renamed or deleted.
- Stock handlers find tiles by name, so a moved or hidden tile keeps working. Stock code never sets
  a tile's visibility or position. The dialog binds pointer events only, so hardware keys cannot
  reach a hidden tile; `sensitive=false` stops a touch (this AWTK hit-tests hidden widgets,
  [ui-rules](ui-rules.md)).
- The dialog keeps its stock height, so hiding tiles leaves empty room.

## Settings tiles and the window stack

Stock marks "inside settings" in two flags (`syssetinto_flag`, `playsetinto_flag`). The page inits
set them to 1, Back clears them and Home's foreground callback clears both. The tile visitor
disables a tile and skips its click while its flag is positive. The Now Playing button opens the
player over the page and closes nothing, so the settings window stays in the stack with its flag
set. Both tiles then stayed disabled everywhere until Home cleared the flags.

- **Reconcile.** `m1plus_pulldown_init` first makes the flags match the window stack
  (`pd_reconcile`). A page is inside settings (flag 1) when its window is in the stack and none of
  `playing_page`, `m1plus_radionp` or `home_page` is above it; otherwise 0. So a page in front is
  stock (its tile disabled), and a page behind the player has its tile enabled.
- **Open.** The two `navigator_to` calls in `on_wm_tsmove_fun` are `pd_open_settings` (payload hook
  22). If the page's window is still in the stack it is brought to the front with
  `m1_restack_window` ([playmore](playmore.md)) and its flag set to 1; otherwise, or if the restack
  fails, stock's `navigator_to` runs, and a failed open clears the flag.
- **The Playback tile opens our page** ([playset](playset.md)): restacked if in the stack, else
  opened like the Settings row, and stock's list only when ours will not open. `pd_reconcile` treats
  either window as the Playback page. Before restacking, its sub-pages left in the stack are closed
  (`pd_close_subpages`), because a page of ours keeps one window and a second instance would leave
  the first without its refresh. The System tile is unchanged.
- No flag is touched on a Now Playing tap, in the main loop or on paint.

## Tiles of ours

Six tiles can take any of the eight slots (hidden by default): four are actions, two are switches.

| Id | Tile | Art (`mod_icons.PD_OWN`) | Action |
|---|---|---|---|
| `8` | Sleep Timer | `drop_sleep` (Lucide `moon`) | our Sleep Timer page ([sleeptimer](sleeptimer.md)) via `pd_open_own`; a page behind the player is restacked, one in front is left alone |
| `9` | Settings | `drop_settings` (`layout-grid`) | our Settings root (`pod_open_settings`) |
| `a` | Equalizer | `drop_equalizer` (`sliders-vertical`) | our Equalizer page (`pod_open_peq`) |
| `b` | Power Off | `drop_power` (`power`) | the power key's long-press confirm, then `poweroff_page` ([Power Off](#power-off)) |
| `c` | AirPlay | `drop_airplay` / `drop_airplayopen` | a switch ([AirPlay and DLNA](#airplay-and-dlna)) |
| `d` | DLNA | `drop_dlna` / `drop_dlnaopen` (Simple Icons mark) | a switch |

Captions are keys of ours in 13 languages; AirPlay and DLNA are brand text. Sleep Timer is too long
for the row label in ja, fr, pl and ru (it ends in an ellipsis and scrolls when focused) and for the
caption box in ru; both are accepted. Our other captions fit the 71 x 40 box in every language.

- **Widgets are in the asset.** `mod_pulldown.py` adds to `view_switchs` an image (`pod_tile_*`,
  50 x 50, clickable) and a caption (`pod_cap_*`, a copy of `label_playset`) for each, **hidden and
  insensitive**. So the default file, the kill switch or a failed hook leave them invisible, and no
  widget is created at run time. The hook looks up all 28 widgets (any missing: nothing changes),
  moves a shown tile with its caption, binds a tap and makes it visible. Stock's tile visitor knows
  tiles by name and ignores ours.
- Art is the stock ring, off look only for the four actions: an action has no on state because the
  dialog closes on the tap.
- **The page** has fourteen rows (`pod_row0..13`) with glyphs from `POD_ROWS`.
- **Tap** (`pd_on_tile`, `pd_open_dialog`, payload hook 22). Stock's tiles never open a page from
  their click handler. They check three words (`DROPDOWN_BUSY`, `POWER_USBSTATE`,
  `airplayGetFlag()`; any equal to 2 = do nothing), call `dialog_quit(dialog, 0xd)` and set a flag.
  `on_wm_tsmove_fun` opened the dialog modally and acts on the result. Ours do the same: the click
  checks the same three words, stores the tile in `pd_pending` and quits with `0xd`; the modal call
  is wrapped, and for the result `0xd` with a pending tile it runs `pd_run(id)` once the dialog is
  gone. `pd_run` is the one place to add an action. The pending id is cleared after every modal
  call, so a stock tile's `0xd` or a drag-close never runs it.
- Because the dialog is already gone when the action runs, **a page that will not open leaves
  nothing on screen**.
- **Adding a tile:** an id in `pod_pages.PULLDOWN_CHARS` and `PULLDOWN_TILES`, `PD_N` and
  `PD_IMG` / `PD_LAB` in `patch/pulldown.c`, an image and caption in `mod_pulldown.OWN`, a `drop_*`
  art image, a `POD_ROWS` glyph, a caption key in 13 languages and a case in `pd_run` (a switch has
  none). `m1plus_pulldown_init` hides tiles that are not shown, so a new pair only needs to be in
  the asset and the arrays.

## Power Off

Tile `b`, caption **Power Off** (a key of ours: stock has only "Shutdown" and "Confirm
Shutdown?"). The tap (`pd_poweroff`) does what the power key's long press does, minus the key-code
test: nothing happens while `standby_mode` is nonzero (a confirm is already up) or `POWERKEY_BLOCK`
is 2. Otherwise it wakes the screen, sets `standby_mode` 1, opens the stock confirm "Confirm
Shutdown?" through `pod_confirm_dialog` (so our scrim dims the page below), and on Yes opens
`poweroff_page`, which does the whole stock shutdown (resume record, stop the player, DAC off,
network stop, splash, `poweroff`). Any other answer, or a `poweroff_page` that will not open, sets
`standby_mode` back to 0.

**Our code never calls `system()` or `device_reboot`:** every stock shutdown goes through
`poweroff_page`, and a direct call would skip the resume save. Pinned in `PULLDOWN_FLAG_PINS`.

## AirPlay and DLNA

Tiles `c` and `d` are **switches** for the two service settings the Network Services page has
([settings](settings.md)). Captions are the brand texts `AirPlay` and `DLNA`.

- **Stock:** `airplay_switch` and `dlna_switch` only flip a setting byte and save it
  (`[SYSSET] AIRPLAY` / `DLNA`). Nothing starts or stops: the network-status timer starts or stops
  the services to match the byte, every tick, only while Wi-Fi is connected.
- **Tap** (`pd_on_tile` -> `pd_switch`): the same three guards, so **while an AirPlay session is
  playing both tiles refuse taps**, as stock's do. Otherwise it calls the switch function, sets the
  picture from the byte and invalidates the image. **Nothing is pending and the dialog is not
  quit**: a page-opening tile has to close it, a switch does not. Our code starts no service.
- If the byte is now on and Wi-Fi is not connected, the toast "Connect to Wi-Fi first" says why
  nothing starts. The byte is still flipped: it is a stored preference. Turning off never toasts.
- **Lit look:** when the dialog is built, a shown switch tile gets its picture from the byte. The on
  pictures are the ring style's on look and are in `ACCENT_DISC`, so with an accent the lit disc is
  the accent. The picture shows the setting, not whether the service is running yet.

## Swipe gates and the window stack

After locking and unlocking while plugged in, the pull-down could no longer be slid down until a
reboot. The cause is a stale word in stock's state.

**Gates.** `on_wm_tsmove_fun` opens the pull-down only while `lockscreen_pageflag` is not 1 and
`dropdown_menu_state` is 0 (and the press began high on the screen with a move of at least 11 px
down). It stores state 1 before the open. `on_wm_tsdown_fun` stores `pressdown_y` only for state 0
or 3. The lock flag is set by the lock page's init and cleared by its close handler; the state is
set by the dialog's handlers and cleared only by its close handler. A window that goes away without
its close event leaves its word set for ever.

**A window can go without its close event** (from the disassembly): a close during an animation is
only stored in one pending slot, which a second close replaces; a forced close of the animation's
current window only ends the animation; `dialog_quit` does nothing unless the dialog's stage is
opened. While charging the device never enters standby, so the lock page is opened at wake with a
close animation.

**Rule: payload hook 30, `m1plus_tsdown`** (the prologue of `on_wm_tsdown_fun`, before stock's code
on every touch down) clears a word whose window is gone: `lockscreen_pageflag` when there is no
`screensaver_page`, `dropdown_menu_state` when there is no `dropdown_dialog` anywhere in the window
stack.

- A window under another page keeps its word: its init does not run again when the page above
  closes, so a word cleared while it was covered would stay 0 once it is in front again (a second
  pull-down over the first). Such a covered window still blocks the swipe above it, as in stock.
- Words are only cleared, never set; nothing is closed, destroyed or opened.
- Reconciling at touch down makes stock's own tsdown store `pressdown_y` for this touch, so the first
  swipe after a stale word already works.
- **Cost:** both words 0 (the normal case) is two loads and the stock call, with no
  window-manager call, file, syscall or allocation. A nonzero word reads the kill switch once and
  walks the window stack. On the kill switch the hook is stock. Pins: `TSDOWN_PINS`.

**The slide timer after the close (second cause, same symptom).** The dialog's close handler stores
state 0 and removes only the 500 ms refresh timer. The 10 ms slide timer is not removed, and the
dialog's destruction is only scheduled. A tick after the close stores state 3 on its last opening
frame with no check that the dialog is closing, so state 3 is left with no dialog and every swipe is
refused. **Repair:** `m1plus_pulldown_init` binds one more handler, `pd_on_close`, to the dialog's
close event (no new hook). It cancels the slide timer as stock's pointer-down handler does (read
the `timer_idex` property; unless it is `0xffffffff`, remove that timer and reset the property). It
stores no global and returns OK. A refused bind leaves stock's behaviour. The two repairs are
independent: the touch hook repairs a stale state, this one stops one being made.

**Limits.** A dialog on top of the stack but off-screen, a lock page on top but not shown, and a
lock page or dialog left under another page (its word stays set and blocks the swipe there) are left
to stock.
