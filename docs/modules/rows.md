# Library rows

**Sources:** `patch/rows.c`, `patch/rows.json`, `tools/mod_ipodrows.py`, `tools/mod_lists.py`.
**Tests:** `test/pod/rows.py`.

The library lists use q2-pod's compact row look (from its `patch/ipod.json`,
`compact_set_row_layout` / `compact_row_layout`). Songs (and Hi-Res, Favourites, Recent, Most
played, a playlist's songs), Folders, Artists/Genres/Composers, Albums, an album's tracks,
Playlists, Search and Now Playing's jump list get 64 px rows on a 60 px body, 52 px album art drawn
1:1, 21 px titles to a 12 px right margin, and long titles that end in an ellipsis instead of all
scrolling at once.

The rows are built by demo's row constructors, with their sizes as `addiu` immediates. An asset
can only choose the pitch, so the geometry is pinned edits plus a small payload function. Edits
are listed in `patch/rows.json`; the build checks every listed word against stock and refuses any
mismatch.

Constants: `PITCH` 64, `BODY` 60, `ART` 52, `ART_INSET` 4, title box y 7 / h 24, meta y 33 /
h 20, `ROW_RIGHT` 12. Folders divides `yoffset` by 64 with `(y + 63) >> 6`; the stock `>> 6`
divisions stay pinned.

## Page geometry

| page | stock | now |
|---|---|---|
| Songs | row 60, button 56; title 200 wide, 20 px at y 10; artist 175 at y 30 | row 64, body 60; title x 60..298 (238), 21 px in 24 at y 7; grey 18 px line at y 33 (20) full width, 213 after the MQA badge; multi-select 94..298 |
| Folders | row 64/60; title 220, chevron at 288 | title 60..277, chevron button 285..298 (ink 288..298); 60..298 for a song file |
| Artists / Genres / Composers | row 60, button 56, title 220 | row 64, body 60, title 60..277, chevron 285..298 |
| Albums | item 60, cover 60 at x 0, title 180 at y 10, chevron 296 | item 64, cover 52 at (4,4), title/artist 60..277 at y 7/33; 8 covers per batch |
| an album | track rows 60, "N title" 260 wide; header boxes 20/18 at y 10/30 | track rows 64, "N title" 12..298; header boxes 24/20 at y 7/33 |
| Playlists | items 60, name 220, create label (60,20,220,20), Import/Export (60,20,90,20) | items 64, name to 12 px before the arrow, create label (60,18,238,24), Import/Export y 18, 24 high |
| Search | tab rows 64, title 250 at y 10, album covers 60, scroll-end divides by 120 | title 238 at y 7, artist y 33, covers 52 at x 4, divides by 64 |
| jump list | row 60, button 56, text 200, rebind 250x56 | row 64, button 60, text 238, title (0,7,238,24), artist y 33, rebind 238x60 |

Every title is 21 px (`srlabel_item_white_style` / `gold20` in the page theme), the second line
`srlabel_item_gray18_style`. Labels scroll only while focused, which no row is on this touch UI.

## The demo edits

- `addiu` immediates: pitch, body, rebind size, cover width, title and meta boxes, Playlists
  labels, cover batch. The cover thread's thumbnail size goes 60 to 52 and the album page header
  cover 100 to 160. The navbar builders' heights and buttons follow the Pod navbar slots, see
  [album-page.md](album-page.md) and [navbar.md](navbar.md).
- Call sites: each ordinary row constructor's `widget_set_children_layout(row, "default(...)")`
  call becomes `compact_set_row_layout` (Folders, Songs, Artists, Albums, album tracks, Playlists,
  four Search sections). The layout string stays in the delay slot.
- Nops: the Folders, Artists and Songs rebinds' `widget_resize(title, 220/250, h)`.

## The row fit

`compact_set_row_layout(row, params)` calls the stock `widget_set_children_layout`. If the layouter
is the stock default one (checked at run time and build time) with the pinned vtable, it points
it at a copy of the default vtable in `.scratch` whose layout slot is `compact_row_layout`. On each
layout that function:

1. finds the text (first `hscroll_label`, or the first child holding one) and gives it the row
   width minus the left margin, the right margin (at least 12) and every other visible child's
   width plus spacing;
2. lays `list_item` rows out 4 px short, so children sit on the 60 px body above the separator;
3. calls the stock default layout (anything unexpected, such as no layouter, no text, more than 16
   children or a hidden title, is left to stock alone);
4. moves an x=0 row's cover to x 4 and stretches a line's last label to the view's end.

There is no relayout loop: every value is the same on every pass, and `widget_resize` /
`widget_move` return early on an unchanged size.

## The repeated disc

The Songs-family rows (Songs, Hi-Res, Favourites, Recent, Most played, Recently Added, a
playlist's songs) and the queue would show the track's file-format disc left of every title.
`rows_track_icon` replaces the `image_base_set_image(img_icon, name)` call in both rebinds. It
makes the stock call, then hides `img_icon` for any name but `icon_playing` and the place icons
(`icon_folder`, `icon_playlist`, `icon_tf`, `icon_otg`). The text then starts at the 12 px margin.

- The playing row keeps the widget as its marker. The image is `np_row_playing` (40x20, a 20 px
  wave at its right end), drawn centred, and the widget is restacked last in the row. The title is
  12..250 (238 px) and the wave sits at 278..298. A recycled row rebound to another track hides
  the widget and restacks it back before the text. Rows with a check box keep it first.
- The Artists / Genres / Composers rebind uses the same function. Those rows end in the chevron
  button, so the marker is restacked before it: name 217, marker 237..277, chevron 285..298.
  Without the marker the name is 265 px from x 12.
- Folders (icons tell folders from files), Search (types) and Playlists (a playlist is not a
  track) are untouched.

## Safety

`tools/reach.py` walks an over-approximate call graph of stock demo from `main` and
`platform_init`, except through the navigator's open-by-name dispatcher. No function holding an
edit is reachable, except `parse_albumcovertask_thd`, which starts at boot and sleeps until a
task arrives. Its only edit is the thumbnail size constant, and its producers are not reachable at
boot.

- No prologue is rewritten.
- The payload runs only where the patched instruction ran.
- `$gp` is reloaded by every patched caller from its stack slot.
- Nothing is hidden or shown by the fit, so hit testing is unchanged.
- The immediates and nops are static, so the way back from them is a stock re-flash.

## Row assets and page themes

`tools/mod_ipodrows.py` edits the five row `ui/*.bin` files (`localclass_page`, `allmusic_page`,
`playerjumpinfo_page`, `album_page`, `playlist_page`): `row_height` and `default_item_height` 60
to 64, and the jump list's template row.

`tools/mod_lists.py` writes the page themes (`folder_page`, `localclass_page`, `allmusic_page`,
`playerjumpinfo_page`, `playlist_page`, `search_page`, new `album_page`). Each is derived at build
time from the tree's own `default.bin`, so the lists follow the theme.

- `btn_tablerow_style`: list_item colours per state.
- `srlabel_item_white` / `gold20` at 21 px. `srlabel_item_gray26_style` is defined, because stock
  names it for the artist line without any theme defining it.
- Import/Export tiles in the list colours.
- Search tabs on the row colour with `#AAAAAA` labels, the active tab white over a 3 px accent
  underline.
- The Songs index letter `view_letter`: a `#262626` rounded square (radius 14, `#3A3A3A` edge),
  white letter.
- `batchadd_dialog`, `confirminfo_dialog` and `sortselect_dialog` pressed in the list colour.

Page slide transitions are left alone (loop hazard), and so is the confirm dialog's two-row layout
(its `confirminfo_bg` image draws the divider).
