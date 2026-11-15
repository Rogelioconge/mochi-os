# Virtual iPod

**Sources:** `patch/ipod.c`, `patch/ipod_render.c` (slides), `patch/ipod_theme.c` (appearance),
`patch/ipod_cf.c` ([Cover Flow screen](ipod-coverflow.md)), `tools/pod_ui.py` (`build_ipod_page`,
`ui/m1plus_ipod.bin`), `tools/mod_icons.py` (`ipod_wheel`, `ipod_placeholder`, `ipod_podcasts_pane`),
`IP_*` in `offsets.inc`. **Tests:** `test/pod/ipod.py`. **Preview:** `tools/preview/preview_ipod.py`.

The optional Pod item opens a fullscreen iPod Classic-style page: a 240 px display above a 240 px
touch-wheel area. It is hidden from the main menu by default. Code keeps the `ipod` and `IP_*`
names; the device label is Pod (a brand, plain text in every language). The row's glyph
(`pod_ic_ipod`) is `assets/icons/custom/ipod.svg`.

**No stock hook and no boot work.** The page owns its `EVT_AFTER_PAINT`, pointer grab,
foreground/background/destroy events and one page timer, using stock calls shared with Albums,
Songs, the mini player and Cover Flow.

**The Pod shows only Pod levels.** Every row opens a Pod level, never one of our full pages; a
function without a Pod-designed level is left out.

Borrowed numbers, own code: the look follows [iPlayr](https://github.com/keremersu35/ipod-player)
(MIT, Kerem Ersu: values, metrics, timings, behaviour) and the wheel's tiers and thresholds follow
Apple's Music 404-page iPod; q2-pod was navigation research only. No code or media was copied. The navigation display model and timer
integration are specific to this firmware.

## Layout (320 x 480)

The window is fullscreen (as the lock screen's `screensaver_page`; the stock status bar is not
drawn), colour `#C6C9CE`. The screen `ipod_screen` (320 x 240, insensitive) is painted by
`ip_on_paint`; the wheel view `ipod_wheel` (220 x 220 at (50, 250)) is the touch target with a
decorative insensitive picture over it.

| Part | Rule |
|---|---|
| Title bar | 24 px, four-stop gradient (`#FDFDFD`, `#E7E7E7`, `#D8D8D8`, `#ABABAB`), 1 px divider `#6A6A6A`; title on the left (16 px, x 8), no clock; play-state glyph and battery on the right |
| Text rows | seven 30 px rows (24 + 7 x 30 = 234, never cut at the bottom); 18 px, padding 8 px (`IP_TEXT_X`); every text cut with an ellipsis |
| Cover rows | four 54 px rows (Albums, an artist's albums, Playlists); the cover fills the row's left 54 px, text at x 62 |
| Selection | five blue stops `#3EABE3`..`#1584D3`, highlight and rule lines, white text and chevron; only the selected row has a chevron |
| Split menus | list x 0..160 (`IP_SPLIT_X`), cover pane x 160..320, no rule between, soft shadow over the pane's left edge |
| Battery | read from `*system_bar` (`pgbar_battery`, `img_battery`): 24 x 12 frame, green fill (red at 20 % or less), full green while charging; no bar, no fill |

Decisions:

- **The screen is white in both appearances** (as the reference and a real iPod).
- The window is fullscreen, no close animation.
- Battery from the system bar: no new stock function.
- **Song lists are plain text rows** (title only, seven visible, a speaker on the playing track): Songs
  and every list of tracks show no cover, and the row worker does no cover work for them.
- All text is the device font (Inter Medium); hierarchy is size and colour only.
- A list opened from a record is titled with it (album, artist, playlist).

Text styles are ten hidden labels in the asset (`label_ip_*`). Values in settings are 14 px blue on
white, white on the selection.

**Main menu:** Music, Cover Flow, Podcasts, Shuffle Songs, **Now Playing** (only while something
plays or is paused), Settings. When the row appears or goes the cursor stays on the same item.

**Now Playing screen:** the playing cover at (10, 30), 150 px, flat and square, with a 20 row
reflection under it (made once per cover or appearance change). Text column at x 176: title 18 px,
artist and album 16 px grey, and `n / N` for the queue place. The active stock play mode is marked
top right (shuffle, repeat or repeat one; none in list play). The progress bar is a 14 px glossy
blue track with `mm:ss` on the left and `-mm:ss` on the right.

- **Now Playing never blinks.** While the player changes track it briefly has no time or no track,
  so the bar is drawn from the last valid position and length, and the last text and cover stay for
  `IP_NP_GONE` (3) looks. Only then does it say `Not Playing` and the cover becomes the placeholder.
- Nothing queued: `Not Playing`.

## The wheel

Touch events come from the wheel view (`EVT_POINTER_DOWN/MOVE/UP/ABORT`); the view is grabbed for
the touch so the release arrives wherever the finger goes. Touch outside radius 110 is ignored.

| Rule | Value |
|---|---|
| Regions | radius < 45 (`IP_HUB_R`): centre button; 45..110: ring |
| Angle | `ip_angle`, degrees clockwise from 12 o'clock in sixteenths, integer code (error under 0.2 degree) |
| Step | one row per 15 degrees (`IP_STEP`); the leftover carries; a push or pop clears it |
| Ends | **hard stop**: no wrap, no bump, no timer touched |
| Chord dead zone | `IP_DEAD_R` 11 px: a move whose line passes closer than that to the centre is rejected; a drag that began on the centre button turns nothing |
| Reversal | `IP_REVERSE` 8 degrees: opposite travel is swallowed until it reaches 8, so the first reverse step comes after 8 + 15 degrees |
| Long lists (> `IP_LONG` 16 rows) | tiers of 1, 2, 3, 5, 8, 13, 21, 34 rows a step, climbing every `IP_TIER_MS` 500 ms while speed stays above `IP_FAST` 180 degrees a second; speed clamped at `IP_VMAX` 400 degrees a second, smoothed by 0.15, reset by a gap over `IP_PAUSE_MS` 250 ms or a reversal; shorter lists always move one row |
| Tap | a touch that turned no step and moved under `IP_TAP_PX` 12 px |
| Long press of MENU | `IP_LONG_MS` 500 ms: pops every level to the main menu; on the main menu it does nothing |

A tap on the centre button selects. On the ring, by sector: top MENU (back; on the main menu
`navigator_back` closes the page), bottom play/pause, left previous, right next (the skip calls read
the event time, as stock ignores a click within a second of the last). An abort ends the touch and
acts on nothing. On Now Playing, rotation does nothing and select is play/pause.

## The cover pane

The split pages (main, Music, Settings) show album art in the right pane (160 x 240) edge to edge.
The menu casts a 10-column shadow on it (52 % opaque at x 160, falling like a gaussian), one RGBA
bitmap made at open. All pane work is on the page's one timer; paint only copies.

- **Pan:** a cover pans across a 24 px margin in 7.5 s, every other cover the other way, at 1/256 px
  fixed point and counting only time shown. The placeholder stands still.
- **Rotation:** up to 8 random albums that already have a cached cover; a cross-fade of 1.5 s
  every 6 s. The playing album's cover replaces the rotation. No cached covers: the placeholder.
- **Sharp sources:** the playing album uses stock's own `/tmp/coverpic.jpg` or `externpic.jpg` when
  ready; the next rotation album is extracted at 264 px into one RAM file `/tmp/m1plus-pane.jpg`
  by the shared builder's worker, never onto the card. Otherwise the 168 px cache file is used (see
  [covercache](covercache.md)).
- Slots: two 264 x 264 bitmaps and one pane-sized mix bitmap (about 710 KB), freed at destroy.
- **Timer:** 40 ms while a split page is in front with a cover, 50 ms during a fade, 500 ms
  otherwise, 1 s while the screen is off (no pan, decode or repaint). A frame invalidates only the
  pane's rectangle.

On the main menu, the Podcasts row shows the still asset `ipod_podcasts` (`No Podcasts` when no
show has an episode file) instead of the slideshow.

## Levels and the stock library

A stack of at most 7 levels (`IP_DEPTH`). Music holds Cover Flow, Albums, Artists, Songs, Playlists
and Shuffle Songs; the root Cover Flow row is a convenience. An artist leads to albums, tracks, then
Now Playing. A list level keeps only its cursor; rows are read from the stock list while it is the
one the stock queries last made (`ip_valid`).

| Level | Query | Rows |
|---|---|---|
| Albums | `loadLocalClassList(0xf003)` | album |
| Artists | `loadLocalClassList(0xf004)` (the stock Artist / Album Artist setting applies) | title |
| An artist's albums | the artists query, then `loadAlbumList(0xf004, record)`; the stock "All Songs" record is shown first | album |
| An album's tracks | the albums query, then `loadAlbumdetailList(0xf003 or 0xff01, record)` | title, else file name |
| Songs | `loadLocalClassList(0xf001)` | title, else file name |
| Playlists | `loadLocalClassList(0xf00b)` | title |
| A playlist's tracks | playlists query, `classinfo[1]` = id, `loadLocalClassList(0xff13)` | title, else file name |

- **Artist single-album shortcut:** an artist with exactly one album (besides All Songs) skips the
  album list and opens the tracks, titled with the album as a real iPod does; MENU returns to Artists.
- Empty lists say No albums, No artists, No playlists or No songs; an empty episode list says No
  downloaded episodes.
- **Cover Flow** is the Pod's own screen (level `K_CF`, [ipod-coverflow](ipod-coverflow.md)); the
  existing page opens only when its memory is refused.
- Going back runs the chain of queries again, keeping each level's cursor.
- **Queries run only from the foreground page:** its open, a wheel step or tap, its window coming
  back to the front, and its tick while it is the top normal window (`m1_is_top`), as in
  [payload](payload.md). **Paint never queries and never reads a stale list.**
- Albums are in the stock query's order, not the Albums "..." card's order.
- **Play:** a track does what the stock Songs row does (`loadSongList`, then `start_player` and
  `force_refreshflag`), and the Pod pushes its own Now Playing level. A missing file shows the
  stock message box.
- **Shuffle Songs** loads the Songs query, picks a random first song, then plays as a tapped track
  with `pod_set_mode(MODE_SHUFFLE)` first ([shuffle](shuffle.md)). An empty library: stock's
  `Update Local Music first`; a missing first file: `Storage unavailable`, and the mode is left
  untouched.
- **Podcasts** (`K_PODCASTS`, `K_PC_EPS`) over the podcast model (`patch/pcmodel.c`): shows with at
  least one episode file, then local episodes in the show's Episode Order ([podcasts](podcasts.md)).
  An 8 px blue dot marks unplayed episodes. Play goes through `pg_episode_queue`. Local files only.

## Settings level

Three rows; a value shows right aligned instead of a chevron.

| Row | Value | Centre press |
|---|---|---|
| Shuffle | Off / Songs | `pod_set_mode(MODE_SHUFFLE)`; on, `pod_set_in_order()` |
| Repeat | Off / One / All | cycles with `pod_set_mode` |
| Appearance | Light / Dark | saves the Pod appearance, updates the live page |

**Shuffle and Repeat are one stock setting** (modes 0 List, 1 Repeat one, 2 Shuffle, 3 Repeat all),
so turning one on turns the other off; Repeat reads Off in Shuffle mode. The iPod's Shuffle Albums
value is not offered (stock has none). Other settings are absent: their setters are not pinned.

## Appearance

Light is the default. Dark turns only the case behind the wheel (`#111111`) and the wheel image
(`ipod_wheel_dark`); the screen stays white. `/mnt/data/m1plus/pod-appearance` holds `0` or `1`
(atomic write; missing or malformed is Light; a failed save leaves the live appearance). Changing
appearance invalidates pre-rendered cover projections and Cover Flow frames.

## The placeholder cover

Anything without art shows one picture: the classic iTunes Cover Flow placeholder (a grey note on a
dark gradient, supplied by the user), scaled to 256 px as `assets/icons/ipod-placeholder-256.png`
and written as `ipod_placeholder`. It serves the All Songs record, albums with no cached cover,
playlists with no art, Now Playing, the pane and Cover Flow's textures.

## Library artwork

Four page-owned 54 x 54 bitmaps hold visible covers; the timer prepares one row or decodes one
cover part per tick, paint only copies. Albums use `cc_album_key`; a playlist inspects at most 16
songs and mosaics up to four distinct albums. A reused row is checked against its record identity,
so scrolling cannot show another row's cover. Cached 168 px covers are shared with Albums and Cover
Flow ([covercache](covercache.md)); missing ones are submitted to the shared builder only when it is
idle, and Pod stops only its own worker. Without card, art or memory a placeholder stays and
navigation works.

## Page slides (`patch/ipod_render.c`)

Push and MENU pop use a 280 ms smoothstep slide (`SLIDE_MS`): 160 px between split menus (the pane
stays still), 320 px for a full-width list. Fullscreen pages (Now Playing, Cover Flow) open with
the split: the page is drawn still while the outgoing menu half slides left and the pane right;
closing runs it backwards. Wheel movement, rapid navigation, appearance changes, background and
destroy cancel a transition.

The renderer records a bounded display model (192 commands, 2,048 text words, two buffers, about 40
KB) and clones at most eight referenced images, never sampling the framebuffer. Overflow or
allocation failure falls back to immediate navigation. Paint never allocates, decodes or queries.
The page timer runs at 33 ms during a slide; cover work pauses.

## Entry, exit and timer

- **Entry:** `ACT_IPOD`, menu item id 19, hidden by default (Settings > Main Menu shows it; the
  Extras page lists it).
- **Exit:** MENU on the main menu (`navigator_back`). There is no hardware back key in the payload.
- **Timer:** `ip_first` (50 ms one-shot) starts `ip_tick`. Its interval is set in one place
  (`ip_want_ms`) and changed in place with `timer_modify`, never removed or added while the page
  lives. The tick steps the pane and checks battery, play state and mode, the playing track, the
  position and the queue size; a change repaints. The timer stops on `EVT_WINDOW_TO_BG` and returns
  on `TO_FG`, which also re-reads the list. State is one struct in `.scratch`.

## Playback limits

Now Playing rotation has no action; select toggles play/pause. Scrubbing, wheel volume and a
centre-press mode cycle are unsupported.

- **No scrubber and no held next/previous seeking:** stock `seek_time` can block the UI thread for
  2 seconds, and direct `mclSetSeek` bypasses stock's pause/DLNA handshake.
- **No wheel volume:** `set_devicevolume` depends on output-specific state, with no verified
  universal volume readback. Hardware volume keys keep the tested stock path.
- **The wheel is silent:** `hciplayer` owns the PCM at the track's exact format and rate and there
  is no dmix configuration. A second PCM opener can race a track transition, cause EBUSY or power
  the DAC/amp unexpectedly, and no process is spawned for wheel sounds.

## Limits

- No search, Genres, Composers or Folders; no cover flip in Cover Flow (the centre opens the tracks
  as a list); no clock in the title bar.
- The cover pane does not follow the row and shows only covers already in the cache.
- Long translated labels are cut with an ellipsis to the 130 px root text box (`i18n_tests` lists
  them).
- The play queue is the stock one: `start_player` copies the shown list, so a Songs list of
  thousands of rows is copied once per play, as the Songs page does.
