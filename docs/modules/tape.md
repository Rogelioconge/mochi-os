# Cassette Mode

**Sources:** `patch/tape.c`, `tools/tape_art.py`, `tools/pod_ui.py` (`build_tape_page`),
`tools/mod_icons.py`, `TP_*` in `offsets.inc`.
A fullscreen 480 x 320 cassette-style Now Playing page, opened from the More sheet's Display Mode
page or by the Idle Display timer ([bigcover](bigcover.md)). Tap the cassette to pause/resume, tap
the top-left screw to close. No hook or boot work, one page timer. The art is generic, without brand
names or logos; the visual references are Sony's NW-A100/NW-ZX500 cassette screen and FiiO Tape mode.

## Themes and assets

Settings > Now Playing > Theme: **Normal, Chrome, Metal, Auto** (default). A chosen theme shows the
same cassette for every track; Auto follows the track's quality (see "Quality").
`/mnt/data/m1plus/cassette-theme` stores `0\n`..`3\n` atomically (`TP_THEME_AUTO` 3). `tape_theme`
accepts `0`..`3` with an optional newline; anything else, or no file, is Auto. A failed save changes
neither file nor label. The page reads the setting once at open.

| Theme | Shell | Label | Band | Hub |
| --- | --- | --- | --- | --- |
| Normal | smoky dark grey | off-white paper, dark ink | blue | white |
| Chrome | black-graphite | silver paper | red | silver |
| Metal | black | black label, gold print | dark with gold hairlines | gold |

Each theme also has its own tape colour, text colours and fine print (TYPE I NORMAL, TYPE II CHROME,
TYPE IV METAL). Shared assets: `tape_top`, `tape_screw`, `tape_tex`, `tape_badge`; per theme:
`tape_shell_<theme>`, `tape_hubs_<theme>`, `tape_marks_<theme>`. The rebuilt rootfs may not exceed
stock size (`fwtool` enforces it).

## Landscape and rotation

The panel is portrait 320 x 480; the page is drawn landscape 480 x 320 and turned 90 degrees
clockwise into the framebuffer (the player is held with its right edge up). **Landscape pixel (x, y) is framebuffer row x, column 319 - y**
(`tp_pix`; `tools/tape_art.py` `rot`). Touch maps back the same way: portrait (column c, row r) is
landscape (r, 319 - c) (`tp_local`). The cassette is 470 x 300 at (5, 10) on a #111 surface with a
soft shadow.

**Rotated text.** AWTK text drawing cannot rotate. The page blends the font's own glyph bitmaps
(`font_get_glyph`, `font_get_vmetrics`, already pinned for Cover Flow's landscape captions) into its
own frame through `tp_pix`, using AWTK's advance and vertical metrics. The font object comes from a
hidden label (`label_tp_font`), so no new stock function is needed.

## The page

- **Window:** fullscreen, colour #111112, one view `tape_view` (320 x 480, the touch target, painted
  by the payload in its `EVT_AFTER_PAINT`) and a hidden, insensitive holder with `label_tp_font` and
  `label_title`.
- **Frame:** a 320 x 480 RGBA bitmap the page owns (the turned picture, freed on destroy). It starts as
  the shell, and only what changes is drawn. The paint blits it 1:1 and the timer invalidates only the
  changed rectangle (`widget_invalidate_force`, `TAPE_PINS`).
- **Pictures** are built by `tools/tape_art.py`, installed as PNGs and decoded once at open. A missing
  or wrong-size picture fails the open.

  | Picture | Holds |
  | --- | --- |
  | `tape_shell_<theme>` 320 x 480 opaque | the cassette, smooth (the page adds grain and knurl); no text, tape, rings or hubs |
  | `tape_top` 74 x 280 | the holes' gear rings and lips, the window's scale and bevel (what lies over the tape) |
  | `tape_hubs_<theme>` 30 x 720 | the reel hub in 24 frames 5 degrees apart; the picture repeats every 120 degrees |
  | `tape_marks_<theme>` 26 x 78 | play mark, pause mark and repeat arrow in the band ink |
  | `tape_tex` 320 x 480 | red = knurl strength, green = grain amplitude; same for every theme |
  | `tape_badge` 24 x 52 | the quality sticker (gold foil, no text); missing = no sticker |
  | `tape_screw` 26 x 26 | the close screw pressed |

- **Reels** (`tp_reel_px`): per landscape pixel, the shell, then the tape packs (seen only through the
  two holes and the window), then `tape_top`, then the hub sprite. Pack radii follow the position
  with `r_supply^2 + r_takeup^2 = 66^2 + 16^2` (tape area conserved), the take-up's area growing
  linearly with `pos / len` (`tp_radii`). A pack is redrawn when its radius changes by 1/4 px, a hub
  when its 5 degree frame changes.
- **Hubs turn while playing**, counterclockwise at constant tape speed: angular speed x pack radius is
  `TP_SPIN`. A 70 ms tick turns the fastest reel under half the 60 degree period, so no wagon wheel.
  Paused, they stand still. A late tick turns them as 250 ms would.
- **Marks:** the play triangle or pause bars (`mclGetPlayStatus`) and the repeat arrow
  (`mclGetPlayMode` 1 or 3).
- **Text** is drawn by the paint. Each field restores its rectangle from the shell, clips its glyphs
  and ends in an ellipsis when too long.

  | Field | Where (landscape) | Source |
  | --- | --- | --- |
  | title | x 40, middle 49, 22 px | title, else file name; `Not Playing` |
  | artist, album | 40 / 70 at 16 px; 40 / 89 at 13 px | the tags |
  | bias line | right end 435, 70, 11 px | fixed per theme (`NORMAL BIAS · 120µs EQ`, `HIGH BIAS · 70µs EQ`, `METAL BIAS · 70µs EQ`) |
  | sticker | lower left, 11 px bold | `HI-RES` or `DSD`, else none |
  | elapsed, -remaining | right end 428, 89, 12 px | `get_playtimeandlength` |
  | A, fine print | 58 / 146 bold 54 px; 40 / 206 12 px | fixed per theme |
  | status line | right end 428, 206, 12 px (else 11), 212 px room | below |

  The status line is `VOL 42 | FLAC 16/44.1 | 21:07 | 60%`. Volume is the status bar's
  `label_volume` text, read only, never set. Format: see "Quality". Clock: `localtime` `HH:MM`.
  Battery: read as the Pod does (20 % steps, `+` while charging). A missing status bar gives
  `VOL 0`. If it does not fit 212 px it drops
  the clock first, then the format (`tape_art.status_line`, shared with the mock and the test).
- **Refresh only on change:** each tick compares track, position, play state, repeat, battery, volume
  text and clock minute, and redraws only what differs.

### Grain and knurl

The shell pictures are smooth: grain and knurl are texture no PNG packs, so the page lays them on its
own copy of the shell once at open (`tp_finish`; `tape_art.finish` is the same integer arithmetic and
the test's reference).

- **Grain:** per pixel a hash byte moves it towards white or black by `|n - 128| * amplitude >> 7`,
  the amplitude from `tape_tex`'s green (14 shell, 16 paper, 13 band, 22 panel, 20 arrow, 0 on
  screws, holes and window; Metal's two gold hairlines take the band's 13).
- **Knurl:** a 4 x 4 cell at the landscape place (groove, lit top/left edge, shaded bottom/right edge,
  face), scaled by `tape_tex`'s red.
- One map serves every theme; the knurl is masked off the label, screws and holes.
- A missing or wrong-size `tape_tex` leaves the shell smooth; the page still opens.

## Touch

Taps only. The page binds pointer DOWN, UP and ABORT of its view: no MOVE handler, no `widget_grab`,
no swipe detection, and every handler returns `RET_OK`, so the stock pull-down from the top edge sees
every drag ([home-guard](home-guard.md)). The decision is made on UP from where the touch began:

| Touch (landscape) | Does |
| --- | --- |
| began on the top-left screw (50 x 50 area) and ends in it | `navigator_back()` |
| began on the screw and left it before lifting | nothing |
| a move under 14 px anywhere else, page opened from the More sheet | `playpause_quick_click` |
| the same tap, page opened by Now Playing's timer (`tape_open_idle`) | `navigator_back()`; nothing plays or pauses |
| anything else, an abort | nothing |

`tape_open_idle` (called only by `bc_timed_open`) is `tape_open` plus `tp.idle = 1`. The flag lives
in the page state, so destroy clears it. A timed open on a page that already exists leaves its flag as
it was. While the finger is on the screw it is drawn darker and turned (`tape_screw`). The screw's
corner is inside the pull-down zone, so a drag down from it opens the control centre. There is no
click sound (`hciplayer` owns the PCM).

## Timer and the page's life

`tp_first` (a 50 ms one-shot at open) starts `tp_tick` at 70 ms while playing, 500 ms paused
(`TP_PLAY_MS`, `TP_IDLE_MS`). `tp_retime` changes the one timer's interval in place with
`timer_modify`. The timer is removed on `EVT_WINDOW_TO_BG` and added again on `TO_FG`; destroy removes
it, frees the bitmaps and the distance table and clears the state.

**Idle power.** While the screen is off (`m1_screen_lit()`), `tp_tick` does no visual work and the
timer runs at `POD_DARK_MS` (1 s). The first tick after the light returns catches up without a jump
(the reel step is capped at 250 ms). A page opened with the screen off waits for the light before its
first full draw. Nothing here stops the stock screen-off: no wake lock, no input read but the page's
own touches.

## Safety and fallbacks

- No hook, no patched word. `TAPE_PINS` pins the stock words the page newly relies on; every other
  stock call is already pinned by the payload.
- A page that fails to open frees what it made, goes back with `navigator_back` and returns -1. The
  More sheet closes only after the page is up (`pm_on_tape`).
- The only visible, sensitive widget is `tape_view`; the picture is painted, not widgets.

## Quality

The page reads the player's stream record via `mclGetInfo` (bit rate at 0, sample rate at 4, codec
name at 0x10, bits a sample at 0x30; 1 = DSD), the record stock's own quality line prints.
`tp_quality` turns it into:

| Stream | Status line | Auto's tape | Sticker |
| --- | --- | --- | --- |
| lossy (MP3, AAC, OGG ...) | `MP3 320` | Normal | none |
| lossless up to 16 bit / 48 kHz | `FLAC 16/44.1` | Chrome | none |
| lossless over 48 kHz, or 24 bit from 44.1 kHz (`get_hrflag`'s rule) | `FLAC 24/96` | Metal | `HI-RES` |
| DSD (1 bit) | `DSD64`, `DSD128` .. | Metal | `DSD` |

- Lossless is the codec name as `get_hrflag` spells it, or a lossless file extension, so an ALAC
  `.m4a` is lossless and an AAC one is not.
- With no record (nothing playing, a stream the player does not describe), everything follows the
  file extension: `FLAC` alone, Chrome for a lossless extension, Metal and `DSD` for `.dsf` / `.dff`,
  Normal otherwise.
- **A change of track is one event.** The page holds the last track's title, artist, album, time,
  packs, format, sticker and tape until the record is the new track's, then changes everything in one
  update. The record is the new track's when it has a stream, a length, and that length differs from
  the last track's or its position is below the last one's. `TP_INFO_MS` (600 ms) is the fallback.
  Not held: the first look, a full redraw, nothing playing, the same file (the next CUE track). A
  second change inside the hold restarts it for the newest track; the skipped one is never shown.
  (The player's record trails a track change by a 200 ms poll.)
- The bit rate is not compared after the hold, so a VBR file shows the first look's rate. Exception:
  a record that may still be the last track's (`tp.unsure`) also compares the bit rate.
- **Auto** (`tp.automatic`): the page opens with the playing track's tape (nothing playing: Normal).
  When the tape changes, `tp_theme_load` loads the new shell, hubs and marks and the page redraws
  everything. A theme whose pictures will not load is not retried for that track. A chosen theme never
  changes its tape; the format and sticker follow the stream in every theme.

## The cassette

- **Symmetry:** everything static is symmetric about x 240 (cassette 5..475, label 37..443, reels 132
  / 348, screws 24 / 456). The intended asymmetries are the light (shadow
  right and down, bevels and hubs lit from the top left).
- **Shell:** matte moulded plastic with a crisp knurl of raised squares on a 4 px pitch laid on at 1:1
  on the pixel grid (never downsampled), a smooth rim band, fine grain, a bevel, a moulded step and
  one soft light from the top left that falls off across the shell (`shell_parts`). The label has
  paper grain and shadows. No brand mark.
- **Screws:** four recessed Phillips screws in the corners and one at the bottom centre, each with its
  own slot angle (`SCREW_TURN`; the close screw's is 0).
- **Label:** paper on a raised frame with index lines for title, artist and album, elapsed and
  -remaining on the album line, a colour band with a big "A", the fine print, a printed direction
  arrow (`foil()`) and the status line. Play / pause and repeat are printed marks at the band's right
  end.
- **Window:** a black inner panel with two round reel holes (28 px radius, six-tooth hub) and a clear
  smoked-glass window between them with a centre scale. The packs show progress through them.
- **Depth:** the label is set into the shell; the bottom section is a raised trapezoid with pinch-roller
  holes, two small square holes and the head opening.
- Nothing off the cassette: no LED, no counter box. Paused, the reels stand still and the label shows
  the pause mark.

### The pack

Tape packs are drawn at run time per pixel by `tp_pack`; the arithmetic is `pack_rgb` in
`tools/tape_art.py`, which the test and preview call, so the emulated frame is the payload to the
bit. The visual target is a smooth near-black brown (#22150E) with a static bow-tie sheen towards
#6C4F38 and fine windings; the sheen does not turn with the reel. The tape's colour follows the theme
(`theme_pack`): ferric brown for Normal, greyer brown for Chrome, blue-black for Metal.

## Limits

Cover-derived band tint, a control strip, rewind/fast-forward, track-skip swipes, a lock-screen skin
and hardware Back handling are not implemented. Seek needs a reviewed stock path; see
[virtual iPod limits](ipod.md#playback-limits).

Background: Sony picks its tape from codec and bitrate; our Auto uses three tapes for the same idea
(lossy, lossless, hi-res / DSD).
