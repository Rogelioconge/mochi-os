# The iPod page's Cover Flow screen

**Sources:** `patch/ipod_cf.c` (the screen), the level `K_CF` and a few call-ins in
`patch/ipod.c`, the shared renderer `patch/coverflow.c` / `patch/coverflow.h`, `IPCF_*` in
`patch/offsets.inc`.
The iPod Classic's Cover Flow inside the virtual iPod ([ipod](ipod.md)): the iPod main menu's
**Cover Flow** row opens a screen of the iPod page, not the full-screen Cover Flow page
([coverflow](coverflow.md), which the Home menu and the Artists page still open). No new hook,
widget, timer or event: the screen is a level of the iPod page, painted in the page's one
`EVT_AFTER_PAINT`, steered by the page's wheel, run by the page's one timer. The shelf's numbers are
tuned against a photo of an iPod classic's Cover Flow.

The depth renderer, the cache files and keys, the decode (`cc_decode`), the wheel, the albums query,
the tracks level and the play path are the existing ones; the new parts are `ipod_cf.c`, the
shared shelf struct's `tail` and `bg` fields, `K_CF` and the 33 ms pace in `ip_want_ms`.

## The screen

The 320 x 240 screen follows Pod's Light/Dark appearance under its own title bar (**Cover Flow**
left, play glyph and battery right). The covers are a 320 x 192 frame at y 24.

| Part | Value |
|---|---|
| Centre cover | faces you at 128 px (`IPCF_ART`), top at frame y 18 (screen y 42..170) |
| Side covers | turned 75 degrees (`IPCF_TURN`), 62 px back (`IPCF_Z1`), outer edges as tall as the centre; 34 px apart, three either side, running to the screen edges |
| Covers shown | seven: a light linear dim to `IPCF_TAIL` three out, fading out by 3.5 out (the full-screen page shows five and a half and keeps the stock fade) |
| Reflection | 40 px at the centre (`IPCF_REFLECT`), ending at screen y 204, fading into the background |
| Captions | album title (y 192) over artist (y 214), 18 px, centred, ellipsis; they follow the centre album, which changes at the slide's half-way point |
| Background | `IPCF_BG` white in Light; Pod's dark background in Dark, including the distance fade and reflections |

Textures are the 168 px cache files shared with the Cover Flow page and Albums grid
([covercache](covercache.md)), drawn nearest-neighbour. An album without a cached cover shows the
Pod placeholder; this screen never builds the cache. Memory: the 240 KB frame and 9 textures
(1.0 MB), one `calloc` at entry, freed on leaving Cover Flow and at destroy. If the allocation
fails, the row opens the full-screen Cover Flow page instead.

## Albums and wheel

Entering pushes `K_CF` over the main menu. Its list is the stock albums list
(`loadLocalClassList(0xf003)`, stock query order, not the Albums "..." card's order), read and
re-read by the iPod page's machinery; paint never queries.

- **Wheel:** the page's own (15 degrees a step, reversal hysteresis, chord dead zone). The tiers
  are 1, 2, 3, 5, 8, 13, 21, 34 albums a step on more than 16 albums, fewer always one. **Hard stop**
  at the first and last album.
- **Centre button:** the album's track list (`K_TRACKS` over `K_CF`), an iPod list in the page's
  look; the centre button plays it. The iPod's flip of the cover to show tracks on its back is not
  done: the list replaces the screen.
- **MENU:** Now Playing, the tracks, Cover Flow on the same album, the main menu (frame and
  textures freed), then the page closes. `|<<`, `>>|`, `>||` keep their playback meaning.

## The slide and the timer

`pos` and `target` (16.16 albums) are the slide's position and goal. Each tick eases `pos` towards
the target by `dt / (dt + IPCF_TAU_MS)` of the gap (70 ms, about 150 ms per album; ends within 1/64
album). A far target starts the slide at most `IPCF_NEAR` (4) albums short, so the covers on screen
are the ones being decoded.

The page keeps **one timer** whose interval is chosen in one place (`ip_want_ms`) and changed in
place with `timer_modify`: 500 ms normally, `IP_DRIFT_MS` while the main menu's cover pans, and 33 ms
(`IPCF_FRAME_MS`) while Cover Flow is in front and busy. The timer is never removed or added while
the page lives.

**Decoding** is one cover per tick on the UI thread: nearest the centre first, then alternately on
the side the slide moves towards; 7 wanted in 8 slots, a slot reused from the farthest cover, keyed
by album key. **Paint** renders only from what is resident and reuses the frame when nothing
changed; it never decodes, queries or allocates.

Entering or leaving this screen uses the Pod's navigation slide (`SLIDE_MS` 280 ms in
`ipod_render.c`, see [ipod](ipod.md)). The outgoing display model owns a clone of the frame, so
Cover Flow's buffers can be freed during the slide. Decoding pauses during the slide.

## Limits

- No flip of the cover to the track list, no search-by-letter, no artist or sort setting.
- The tiers move the cursor and the slide only follows: a 34-album step slides the last four albums
  in, not 34 covers.
