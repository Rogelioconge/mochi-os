# UI rules

**Sources:** `tools/pod_roles.py` (colour and size roles), `tools/awtk_text.py` (text model),
`tools/pod_ui.py`, `tools/mod_polish.py`, `patch/common.c`. **Tests:** `test/pod/` (hit tests in
`test/pod/harness.py`, widths in `test/pod/i18n.py`).

Rules every UI step follows.

## Widgets and layout

- **Preserve names.** Restyle, move or hide named widgets; never rename or delete them.
  `widget_lookup(win, name, TRUE)` is recursive, so reparenting is safe.
- **Hit testing ignores `visible`.** Hide = `visible=false` + `sensitive=false`; decorative overlays
  are `sensitive=false`. AWTK takes the first child (from the top) that is enabled and sensitive and
  contains the point. The tools model it (`check_touch` in `mod_lockscreen.py` /
  `mod_nowplaying.py`: the centre of every control reaches that control, at least 44 px each way)
  and `test/pod/` runs demo's own hit test on the built page trees.
- **A button inside an insensitive parent never gets its touch.** The keyboard's field `kb_field` is
  sensitive for its clear button, and a page puts its eye button after the field, so over it. A page
  test asks the hit test itself, on the page as the payload left it (`touch_misses` in
  `test/pod/harness.py`); a paint order alone proves nothing.
- **Trailing controls of a card are one column, and a control with nothing to do is hidden.** The
  clear button's disc and the eye's glyph share a centre (x 287); the eye shows only while there is
  typed text behind the dots.
- **Normal windows are 450 px tall** (under the 30 px `system_bar`); only fullscreen windows
  (`screensaver_page`) get 480. Lists use the stock structure `list_view` > `scroll_view` +
  `scroll_bar_m` with stock `list_item` rows: an `hscroll_label` themed `srlabel_leftwhite21_style`
  and the `right_arrow` image, a 13 px widget at x 285 so its ink is the shared chevron at x 288..298.
  The text ends at 278 and the hairline at 310. Bare `list_item`s fall to the light default theme
  (white on white).
- **Window theme first.** A widget's style is resolved in its window's theme
  (`styles/<window name>.bin`, or its `theme` property) before `styles/default.bin`. Page-local
  styles change one page only.
- **No close animation on windows a "play from here" loop can pop:** library pages, album detail,
  jump list, Now Playing and M1+ Music pages. See
  [slides audit](boot.md#settings-slide-safety-audit-static-on-stock-demo).
- **Naming:** the user sees "M1+ Music"; internal names (`m1plus-*` files, `m1plus_*.bin`, widget
  and C identifiers) are `m1plus`.
- The rebuilt rootfs must not exceed stock (`fwtool` enforces it); one change per package where
  possible.
- **The Pod is its own view:** every Pod row opens a Pod level, never one of our full pages. A
  function without a Pod-designed level is left out of the Pod ([ipod](ipod.md)).

## Text width

`demo` links AWTK statically with its stb_truetype backend; there is no FreeType. `canvas_draw_text`
draws glyph by glyph and steps `x += advance + 1`, and `canvas_measure_text` adds the same.

- **Width = truncated glyph advance + 1 px per glyph.** The scale is `font_size / (hhea ascender -
  descender)`, each advance truncated. For the stock font (256 units/em, ascender 230, descender
  -69) size 18 draws an em at 15.4 px.
- No hinting, no kerning, no OpenType features, no per-glyph fallback (one font file covers every
  script). Composite glyphs only with plain offsets.
- `canvas_measure_text` counts a glyph the font cannot give as 4 px. Only `glyf` outlines; cmap
  format 4 is looked up by a binary search that trusts `searchRange` / `entrySelector` /
  `rangeShift` (`mod_boot.stb_lookup` is a line-for-line port, used by the font checks).
- `hscroll_label` clips to its box inset by `margin_left` / `margin_right` (default 2).
- Use `StbText` (`tools/awtk_text.py`): `StbText(ttf, px).layout(text)` returns each glyph's pen and
  the width AWTK measures. `awtk_width`, `fit_size` and `worst_case_text` size the lock clock and
  date. Always measure the font of the tree being built. `tools/stb_raster.py` rasterises the same
  way for the previews.

## Text and colour roles

The role names are in `tools/pod_roles.py`; page constants take them.

| Role | Value |
|---|---|
| ink (`INK_RGB`) | `#FFFFFF` |
| rest surface (`SURFACE_RGB`: Settings cards, cache pill, fields, flat pills, dialog buttons, EQ cards) | `#1C1C1E` |
| raised surface (`RAISED_RGB`) | `#2C2C2E` |
| line (`LINE_RGB`) | `#333333` |
| thumbnail placeholder (`THUMB_RGB`) | `#2B2B2B` |
| secondary text (`SUB_RGB`, `HINT_RGB`: sub lines, footers, values, keys, credits, hints) | `#AAAAAA` |
| album page meta line (15 px; the least that passes the 4.5:1 scan on a pressed row) | `#9C9C9C` |
| field placeholder (`PLACEHOLDER_RGB`) | `#8E8E93` |
| list chevron (`CHEV_RGB`) | `#8A8A8A` |
| a row's "..." and the muted partner / pressed glyph grey | `#8C8C8C` |
| the one red (`RED_RGB`: a destructive row's label and glyph) | `#FF6B6B` |

- **Pressed surfaces are `#333333`** (rows, keys, the queue drawer's bottom button). It is stored as
  the role colour `#333334` so the accent can map it ([accent](accent.md)). `#3A3A3A` is the edge
  colour (hairline borders, the index letter); `#555555` is the pressed disc and the inactive dot.
- **Toggles:** on = light grey pill with a black (dark) glyph or knob, off = dark grey with a white
  or grey glyph or knob. They read by brightness and knob side, not by hue
  ([theme](theme.md) "Switches").
- **Track rows** on the album page use the list title size (`LIST_TITLE_PX` 21) for the number and
  title.

## Headings

- A **group caption** names a group of rows (Settings, Wi-Fi, Search and Extras pages): 18 px
  `SUB_RGB` in a 40 px strip, the label 22 px high 14 px down it, its text on the left of the rows'
  glyph ink (x 24 on a card page, 18 on Extras) (`pod_roles.CAPTION_*`).
- A **content section title** heads the content itself (Songs' A-Z letters, Podcasts sections, the
  Recently Played and Made for You shelves): 20 px `INK_RGB` (`pod_roles.SECTION_PX`).
- Never mix: a new heading takes one of the two.

## Empty and loading states

A page with no rows shows one grey line (`HINT_RGB`: 20 px, 18 px when it wraps) or its loading
spinner. It is centred across the page and centred in the room between the header the page keeps
and the window's bottom:

- the navbar's bottom when the content is hidden (library pages, Radio's captions, Podcasts with no
  shows: `room_y` in `tools/pod_ui.py`, window y 250);
- the large title's bottom on a source's page that keeps the title (`ls_room`, `patch/libsrc.c`);
- the header's bottom on a Podcasts level (`pg_paint_hint`, [podcasts](podcasts.md)).

Exceptions: the keyboard pages (Search, AutoEq) centre the line between the field and the keyboard.
A status that belongs to a row stays in the row (Navidrome's status line and Sync Now, the Wi-Fi
rows, the login page's Connecting line).

## Bottom sheets and segmented control

- **Bottom sheets** (the track rows' menu, the Podcasts and Radio sheets, Now Playing's More
  sheet): 50 px rows, a 24 px glyph at x 14, the 18 px label from x 48, the scrim `PL_DIM`. The
  Albums "..." sort card (50 px rows) and the Playlists menu (20 px glyphs) are floating cards, not
  sheets.

## Segmented control

One painter, `m1_segmented` (`patch/common.c`; constants `SEG_*`, model `tools/pod_show.py
segmented`): a fully rounded `#1C1C1E` track, the selected segment a fully rounded `#D1D1D6` thumb
(black label) floating 3 px inside it, the other labels white, a short `#3A3A3C` hairline (half the
track high) between two unselected segments and none beside the thumb. Neutral (no accent). First
user: the Podcasts Discover level's Shows | Episodes ([podcasts](podcasts.md)).

## Confirm dialog

Our yes/no questions use the stock confirm dialog: see [overlays](overlays.md) "Confirm dialog".

## Polish decisions

Navbar title facts: [navbar](navbar.md). Decisions of the consistency audit, so they are not
re-litigated:

- **Applied:** secondary text grey is `#AAAAAA` everywhere (Home artist line, Now Playing times,
  artist and album lines); `#8C8C8C` stays the muted partner grey. Pressed surfaces are `#333333`.
- **Rejected:** the lock screen's `#DDDDDD` artist line (it sits on a wallpaper) and the queue's
  stock muted rows (derived from the stock style).
- **Rejected:** merging the disc greys `#777777` / `#555555` / `#666666` / `#444444`. Each has one
  job (disc, pressed disc, unlit glyph, disabled tile).
- **Rejected:** unifying glyph stroke scaling (Home discs 3.2 px, 40 px discs 2.2 px, tiles 2.3 px,
  status 1.5 px). Strokes are 2 px on the icon sets' 24 grid scaled to the glyph size, so the weight
  is the same ratio.
- **Rejected:** unifying the font size ladder (22/20 titles, 21 rows, 18 second lines, 16 captions,
  15/16 meta), row heights (52, 60/64, 56, 50, 44) and margins 12 vs 16. They are code-built
  geometry or stock dialogs, and changing one moves hit targets.
