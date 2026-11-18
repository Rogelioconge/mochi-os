# Cover Flow

**Sources:** `patch/coverflow.c`, `patch/coverflow.h`.
A cover carousel over the stock Local Music albums, after q2-pod's Cover Flow design, for the
320x480 touchscreen (wheel-only parts left out). Opened from the menu's Cover Flow row, and per
artist from the artist's Albums page button. No hook: everything runs from the page's own widgets,
one timer and one worker thread. The cover files and their builder are in
[covercache](covercache.md).

The first open builds the missing thumbnails (`CC_MISSING`) on a "Preparing covers... n/m" screen
with Cancel (a cancelled build resumes). A 250 ms timer polls the counters; Cancel, Back and closing
stop it (`cc_build_stop`), and `EVT_DESTROY` removes the timer and stops the worker. Rebuild Covers
is not this page's: it is Home's job ([homecover](homecover.md#rebuild-covers)).

Not ported from q2-pod: Sort and Refresh cards, the rated scope, A-Z jump, the album split by
album-artist/folder, the audiobook filter, the ffmpeg WebP fallback, wheel/ringnav.

## Shelf

- One cover per album; every shelf has ends, nothing wraps. The centre cover faces you at 168 px
  (`ART_SIZE`); the neighbours turn 60 degrees inward, step back and dim (`CF_BRIGHT1` 192,
  `CF_BRIGHT2` 128 of 256, gone three out), each with a 26 px reflection. Geometry is in
  `offsets.inc` (`CF_*`, `DRAG_PX`): change the constants together and re-run `test/coverflow.py`.
- **Renderer:** `coverflow_render` (after Rockbox PictureFlow via q2-pod), all integer, declared in
  `coverflow.h`; the iPod page's screen uses it too ([ipod-coverflow](ipod-coverflow.md)). `bg` is
  the page background (black, the washed black on Tinted with an accent, paper in Light): 0
  composites over black, nonzero blends faded covers towards it so the frame never shows as a block.
- One 320x276 RGBA frame, 9 textures of 168^2 and a placeholder: about 1.48 MB of heap while open.
  The frame is drawn from the touch layer's `EVT_AFTER_PAINT`; an unchanged position reuses it.
- **Flat fallback:** if an allocation fails the page shows flat covers in a stock `slide_menu`
  (`ART_NEAR` 3 either side), driven through its public properties. It has no rubber band (the drag
  is clamped) and no landscape.
- **Position:** depth mode owns it (`cfpos`: committed album, offset) and has no widget per album.
  Stock's `slide_menu` re-lays out every child on each change, O(albums) per drag step with up to
  4000 children, so it is only the fallback. Both modes read through one set of accessors in stock's
  units (`CF_VIEW_H` per cover). Ends, captions and the last-album memory follow `set_value`.
- **Start:** the page always sets its start album (stock's `slide_menu` starts on item 1). The main
  page remembers the last album in `/mnt/mmc/.m1plus/coverflow-position`: the centre key as 8 hex
  digits and a newline, written on close (`m1_card_write`, card mounted only). A missing, short,
  junk or all-zero file means none. It lives outside the cover cache so a cache wipe keeps it.
- **Captions:** `label_album` / `label_artist` are `hscroll_label`s set up like Now Playing's info
  lines (22 px white, 18 px `#AAAAAA`, centred, back-and-forth scroll for long titles). They are
  insensitive and never hidden, and lie over the frame's black rows, so a tap on the name reaches
  the touch layer.
- **Repaint:** AWTK paints dirty rectangles only and the stock `slide_menu` invalidates just its
  own rectangle, so every offset or album change calls `widget_invalidate_force` on the touch layer
  (`redraw()`, always the frame's rectangle).

## Touch

A transparent full-size touch layer takes pointer down, move, up and abort, and grabs the pointer.

- A horizontal drag starts after `DRAG_START` 5 px along the carousel and no more across; a mostly
  vertical gesture moves nothing.
- A release is a tap only if no drag started, no animation was interrupted and the excursion stayed
  within `TAP_SLOP` 12 px. The centre cover (`|x - 160| < 84`) opens the album; a side cover comes
  to the centre.
- **Fling:** velocity from the oldest sample in the last `FLING_WINDOW` 80 ms, coasting
  `FLING_MS` 120, at most 3 albums; a finger that rested has none.
- **Snap:** eases `1 - (1 - p)^3` by elapsed time (`SNAP_BASE_MS` 120 + 60 ms per album, at most
  360) on a 16 ms one-shot timer, exactly on target when time is up. A refused timer commits at
  once. A press during the snap stops the shelf where it is.
- **End stops, rubber band:** the shelf stops at the first and last album, as Apple's does. Past an
  end only the finger goes: the shelf follows at half speed and saturates at 2/5 of a cover
  (`rubber()`), and the release eases back to the end cover. A press on a stretched shelf takes the
  drag up from where it is, no jump (`unrubber()`). Fling and tap are clamped by `bound()`. A
  one-album shelf is both ends.
- The thresholds and times are trials to tune.

## Textures

- Paint never touches a file: it renders from resident textures, a placeholder standing in for a
  cover not decoded yet.
- A one-shot page timer (`on_load`, `LOAD_MS` 1) decodes one wanted cover per callback on the UI
  thread (`widget_load_image` is not known to be thread-safe, so the worker never decodes).
- **Nearest first:** the centre, then the ring alternately ahead of and behind the travel, then the
  next cover ahead. A slot is reused from the cover farthest from the centre that is not wanted, so
  the one just left behind survives a reversal. Nothing past the ends is wanted.
- Building the shelf decodes only the centre cover; the ring follows one per tick.
- A decode blocks the UI thread for its length.

## Landscape

**Settings > Library > Landscape** (a switch in `m1plus_library`; the file
`/mnt/data/m1plus/coverflow-landscape`, `1` = landscape, written atomically, read when the covers
screen is first built) turns the page, main or per artist, into a landscape presentation in the
320x400 body under the navbar. The presentation does not change while the page is open, and no
global LCD orientation changes.

- The content is turned 90 degrees clockwise (the player held turned counter-clockwise). The
  renderer writes the logical frame through a column stride, so the turn costs no copy and no second
  bitmap. `cfg_t` (`cf_portrait`, `cf_land`) holds each shelf's geometry (`CFL_*`).
- The centre cover stays 168 px, two covers show either side, the outer ones cut by the edge. A tap
  beyond the first side cover's outer edge brings the second in.
- The frame is the body (500 KB); the new one is made before the old goes, so a refusal leaves the
  page as it was. Textures are shared.
- `view_covers` and the touch layer move to the body, the caption labels are hidden, and the frame
  draws the captions itself in the page's font.
- `where()` turns the pointer back, so drags and flings along the long side behave as in portrait.
- A tap on the centre cover (`|x - 200| < 84`) opens the album; a side tap brings that cover in.

## Volume buttons

**Settings > Library > Cover Flow > Volume Buttons** (off by default; file
`/mnt/data/m1plus/coverflow-volume-keys`, `1` = on). On the main and artist shelves, volume down
steps one album right and volume up one left, also in landscape. Quick presses accumulate from the
running snap's destination; the ends stop.

- No hook: the window binds `EVT_KEY_DOWN` / `EVT_KEY_UP` (`0x10f` / `0x113`). `0x110` is long
  press, not key down (evidence: `VOLKEYS_PINS` in `tools/pod_pins.py`).
- The window's `RET_STOP` keeps the wm from opening the volume dialog. `ROTATEMODE == 1` swaps the
  keys as stock does.
- Keys are taken only with the switch on, the backlight lit, the covers screen built and no finger
  down. A taken down resets the power timers; its release is swallowed. Everything else goes to
  stock. The Pod's Cover Flow and the Preparing screen keep stock volume behaviour.

## Artist page

- **Order:** the artist's shelf follows the Albums "..." card's order ([albums](albums.md)), with
  Artist read as Title, and the saved direction. The All albums card stays last; cache keys are
  indexed through `cf.order`.
- **Navbar:** one glass capsule, **Songs | Now Playing**, for one album or many. On a composer's page
  too. Not shown while preparing or for "No albums".
- **Songs toggle:** Songs opens our Songs page on all the artist's songs (`songs_open_artist`; see
  [songs](songs.md)). The covers and the list are two views of the artist: the list stays its own
  window over the covers, and its capsule's left cap closes it again. One list window at a time, so
  toggling never stacks pages. Back from either view leaves the artist, to the scoped Albums page it
  came from, or to Now Playing from Look up artist.
- The All albums card on the shelf is not an album: it opens the same Songs page, and falls back to
  the stock page on the All songs row if ours will not open.
- On an artist page the title ends at x 214; the main page keeps its full width.

## Album open

Tapping the centre cover opens our album page ([album-page](album-page.md)), else the stock
`albuminfo_page` as a stock Albums row does (`cc_open_album`, the same call the Albums grid makes).
The queries repeat on every tap, since anything may have reused the list or the browsing record in
between: `loadAlbumList` puts the stock list back, `albumcoverinfo_init` rebuilds the cover-task
list, `batchadd_albumcover_task(0, 0)` releases the cover thread, then the page opens. Back
returns to the covers.
