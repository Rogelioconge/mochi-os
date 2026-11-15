# Vinyl Mode

**Sources:** `patch/vinyl.c`, `tools/vinyl_art.py` (design drawing code and installed layers),
`tools/pod_ui.py` (`build_vinyl_page`), `tools/mod_icons.py` (pictures and the `pod_ic_vinyl` glyph),
`VN_*` in `offsets.inc`. **Tests:** `test/pod/vinyl.py`. **Preview:** `tools/preview/preview_vinyl.py`
(emulated frames in `out/preview/vinyl-emu-*.png` beside the design), `preview_vinyl_themes.py`.

A fullscreen portrait turntable Now Playing page, opened from the More sheet's Display Mode page or
by the Idle Display timer ([bigcover](bigcover.md)). The record lies off the left edge, its label is
the playing track's cover and turns at 33 1/3 rpm while playing. A tonearm on a raised plate rests
on the groove (outer to inner as the track plays) and parks straight down when paused. Three round
keys at the bottom right: previous, play / pause, next. Tap the record to pause or resume, the
top-left chevron to close. No hook, no boot work, one page timer. Neutral greys only; no brand marks.

## The page

- **Window:** fullscreen, one view `vinyl_view` (320 x 480, the touch target, painted by the payload
  in its `EVT_AFTER_PAINT`) and ordinary AWTK labels over it: `vn_title` (22 px, #F4F4F6) with a twin
  `vn_title2` one pixel right for weight, `vn_artist` (15), `vn_times` (12, `m:ss  -m:ss`),
  `vn_status` (10, `VOL 42 | FLAC | 21:07`). They are insensitive `hscroll_label`s that never scroll
  and end in an ellipsis, placed from `vinyl_art.TEXT`. Portrait, so no rotated-text path.
- **Frame:** a 320 x 480 RGBA bitmap the page owns, composed from the layers below. The paint blits it
  1:1 and the timer invalidates only what changed.

| Picture | Holds |
| --- | --- |
| `vinyl_base` 320 x 480 opaque | plinth, arm plate and base, the record (grooves, gaps, weak static sheen, shadow), keys at rest, chevron |
| `vinyl_lid` 160 x 160 at (16, 116) | over the turning label: pressed step, gloss, white rim, spindle |
| `vinyl_arm`, `vinyl_armsh` 353 x 59 | the arm pointing +x (pivot at (73, 22), premultiplied) and its shadow (5 px right, 7 down) |
| `vinyl_cap` 32 x 32 at (262, 56) | the gimbal cap over the pivot |
| `vinyl_keys` 286 x 58 | the key band cut in cells: play at rest and pressed with play / pause glyph, previous and next pressed |
| `vinyl_label` 152 x 152 | the label of a track without a cover: light grey paper |
| `vinyl_grain` 320 x 480 (Graphite only) | grain weight in red: 255 on the plinth, 0 on record, plate, keys, chevron |
| `vinyl_rec` 258 x 324 at (0, 34) | the Cover record's map t in red, 0 where the base stays |

- **Grain.** Film grain is noise no PNG packs, so the page adds it once when it loads the base
  (`vn_grain`): soft-light blend with a hash of the pixel's place (`VN_GRAIN` 6) by the weight, all
  integer (`vinyl_art.grain_apply`). Key cells are cut from the grained frame so they match. Snow has
  no grain.
- **Encoding.** `tools/png_pack.py` writes these PNGs: the smallest of RGBA or an 8-bit palette
  picture with a tRNS chunk (the payload's `vn_load` needs four channels), pixel-identical to a plain
  PNG (asserted).
- **Composition** (`vn_compose`, per pixel of a rectangle above the key band): the base; inside radius
  77 of the record centre (96, 196) the label, inverse-mapped through its turn (fixed point, sines
  from a 91-entry table), bilinear over the 152 px picture; the lid by alpha; the arm's shadow and the
  arm, sampled bilinear through the arm's turn about the pivot (276, 70); the cap. Keys are copied
  cell by cell. The test model has the same arithmetic and compares whole frames pixel for pixel.
- **The label** is, in order: for a server track ([subsonic](subsonic.md)) the source's own cover
  (`sba_rec_cover`, a placeholder while it is on its way; never the library album of the same
  name); the album's cached cover
  (`/mnt/mmc/.m1plus/covers/<key>-168.jpg`, box-reduced to 152 px); the playing track's `/tmp` cover
  once demo has written it (looked at again every 500 ms, 8 times, after a track change); else
  `vinyl_label`. Grooves and sheen are static, so only the label's square is composed while it turns.
- **The record** turns clockwise at 200 degrees a second (`VN_SPEED`), speeding up over
  `VN_SPINUP_MS` (700 ms) and slowing over `VN_SPINDOWN_MS` (2 s). Paused, it stands still.
- **The arm.** Playing, the stylus sits on the groove at the track's fraction (`vn_groove`, 33 turns
  outer to inner, `vinyl_art.groove_table16`). Paused, it stays until the record has stopped, then
  parks straight down (`VN_PARK`), so its swing never shares a tick with the label's. Nothing playing:
  parked. It redraws when its turn changes by a quarter degree. A change of more than a degree swings
  it there, eased (smoothstep) over `VN_SWING_MS` (300 ms) + 1 ms per 1/16 degree on the page's capped
  clock; a target that jumps starts a new swing from where the arm is (`vn_arm_next`).
- **The text** is set only when it changes: title (file name without one; `Not Playing`), artist,
  times each second, and the status line from the status bar's volume (read only), file extension and
  clock. No status bar: `VOL 0`. No battery: 20 % steps would read as false precision. The status
  colour is #BCBCC2 (the build's contrast scan wants 4.5:1).

## Record colours

Settings > Now Playing > Vinyl Mode > **Record** (picker `m1plus_vinylrec`, "Applies the next time
Vinyl Mode opens."): **Black** (default) or **Cover** (the record tinted from the playing track's
cover; black for a grey cover or none). Saved as `0` / `1` (only `1` is Cover) in
`/mnt/data/m1plus/vinyl-record` by `vinyl_record_set` (atomic); the page reads it once at open.
Black is the installed base and `vinyl_rec` is not even loaded.

- **Picture.** `vinyl_rec` holds one 8-bit map t in red: the record outside the label, grooves, gaps,
  a slightly darker rim (no bright bead, which read as a white outline) and a weak sheen baked into
  luma (`SHEEN_COVER` 0.30, `GLOW_COVER` 0.06). It carries no plinth, so it is the same under every
  theme.
- **Colour.** Five stops at t = 0, 118, 190, 235, 255 (`tint_stops`) make a 256-entry table
  (`vn_ramp`). A pixel the disc covers only partly (1/8 px coverage) is the base plus the colour's
  difference from the black record's rim grey (`VN_REC_K`) by the coverage, so the edge blends into
  any theme. The base's rim pixels are saved at the first recolour (`vr.rim`) and every later
  recolour blends from those.
- **Where it runs.** `vn_recolour` composes the record into `vn.base`, the page's own copy, at the
  first look and whenever the cover changes (`vn_retint`). `vinyl_rec` is decoded, read and freed at
  once. A `vinyl_rec` that will not load leaves the page Black.
- **Cover tint.** `vn_tint` runs when the label's cover changes: a 16 x 16 grid of cell means of the
  decoded 152 px cover, the chroma-weighted mean of the cells with at least the mean chroma,
  saturation clamped to 170..235, value to 125..190, hue kept. A mean chroma under 24 is grey: black.
  The same tint changes nothing; a grey or missing cover restores the black record from a fresh
  decode of `vinyl_base`. `vinyl_art.cover_tint_px` is the Python mirror.

## Themes

Settings > Now Playing > Vinyl Mode > **Base**: **Graphite** (default) or **Snow** (matte off-white
plinth, silver arm, grey keys, dark text). Picker `m1plus_vinyltheme` ("Applies the next time Vinyl Mode opens."); saved as `0` / `1` (only `1`
is Snow) in `/mnt/data/m1plus/vinyl-base` (`vinyl_theme`, `vinyl_theme_set`), read once at open. The
designs are `vinyl_art.THEMES` (`use(theme)`).

- A theme changes six pictures: `vinyl_base`, `vinyl_lid`, `vinyl_arm`, `vinyl_armsh`, `vinyl_cap`,
  `vinyl_keys`. Snow's names end in `_white` (`vinyl_art.tname`, `vn_names`). `vinyl_label` and
  `vinyl_rec` are shared.
- Label colours live in the page asset: `m1plus_vinyl` (Graphite), `m1plus_vinyl_white` (Snow,
  `vinyl_art.text_rgb`; `vn_pages` opens the saved one). No stock call is needed to recolour.
- No run-time cost: the page loads its theme's pictures instead of Graphite's.

## Touch

Taps only. The view binds pointer DOWN, UP and ABORT: no MOVE handler, no `widget_grab`, every handler
returns `RET_OK`, so the stock pull-down works (see [tape](tape.md) "Touch"). What a touch began on
decides; it must end on the same thing.

| Began and ended on | Does |
| --- | --- |
| the chevron, (0, 0)..(52, 44) | `navigator_back()` |
| the play key's column (x 223..269, y 420..480) | `playpause_quick_click()` |
| the previous / next column (170..223 / 269..318) | `prev_quick_click(e, 0)` / `next_quick_click(e, 0)` with the UP event (stock ignores a click within 1 s of the last) |
| the record (radius 162, above the band), moving under 14 px, opened from the More sheet | `playpause_quick_click()` |
| the same tap, page opened by Now Playing's timer (`vinyl_open_idle`) | `navigator_back()`, like the chevron |
| anything else, a drag, an abort | nothing |

`vinyl_open_idle` (called only by `bc_timed_open`) is `vinyl_open` plus `vn.idle = 1`. The flag lives
in the page state, so destroy clears it. A timed open on an existing page leaves its flag as it was.

A key is drawn pressed from DOWN until the touch ends, and only its cell is invalidated. After an
action the page looks again at once. Previous / next are the stock functions the Now Playing buttons
call (`IPOD_PINS`). No click sound.

## Timer and idle power

`vn_first` (a 50 ms one-shot) makes the first full draw and starts `vn_tick` at 50 ms while anything
moves (playing, the record slowing, the arm swinging) and 500 ms at rest, changed in place with
`timer_modify`. It is removed on `EVT_WINDOW_TO_BG` and added again on `TO_FG`; destroy removes it
and frees the bitmaps. While the screen is off (`m1_screen_lit`) a tick draws nothing and the interval
is `POD_DARK_MS` (1 s); the first lit tick catches up, its step capped at `VN_DT_MAX` (100 ms). A page
opened dark waits for the light. Nothing here stops the stock screen-off.

**Cost.** Per-tick cost is budgeted in `motion_tests`. `vn_arm_draw` composes each row once over the
columns the old or new arm can touch, so arm swings stay under the 50 ms tick.

Stock's `play_pause_music` mutes and then sleeps 150 ms on the UI thread before pausing, so no page
can draw during it. `VN_DT_MAX` keeps the tick after it from leaping.

## Safety and fallbacks

- No hook, no patched word, no new pin: every stock call is already pinned.
- A page that fails to open (no window, widget or picture, wrong size, no memory) frees what it made,
  goes back with `navigator_back` and returns -1. The More sheet closes only after the page is up
  (`pm_on_vinyl`).
- The labels are insensitive; the only visible, sensitive widget is `vinyl_view`.

## Limits

No arm-drag seek, scratch gesture, picture-disc record, 45 rpm choice, lock-screen skin or hardware
Back handling.
