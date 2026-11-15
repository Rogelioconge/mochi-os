# Now Playing

**Sources:** `patch/nowplaying.c`, `tools/mod_nowplaying.py`, `patch/common.c`.
**Tests:** `test/pod/nowplaying.py`, `test/pod/shared.py`.
Preview: `tools/preview/preview_nowplaying.py`.

The stock `playing_page` has cover-colored backgrounds, rounded artwork, elapsed/remaining
time and reformatted track information. Playback, the slider and stock lyric loading remain
stock services. [Lyrics](lyrics.md), [Queue](queue.md), [More](playmore.md) and
[podcast metadata](podcasts.md) have their own references.

## Hook and lifecycle

The init hook calls `playing_page_init` (`0x53d1e4`) through its trampoline and returns
the stock result. After successful initialization, with a window,
`np_start` attaches page listeners and a repeating timer: 500 ms lit, 1000 ms dark.
A refused timer or listener leaves stock behavior. Every tick, lit or dark, also notes the
seconds heard for [scrobbling](scrobble.md) (one `get_playtimeandlength`).

A replacement page stops the previous timer. Destroy acts only on the current window,
restores its status bar, removes timers and clears state; stale callbacks end without
touching widgets. A covered normal page skips cover, time and info work. Dialogs can leave
the page partly visible, so its data continues updating beneath them.

## Layout and assets

The window is 320 × 450 px. `tools/mod_nowplaying.py` defines widget geometry and page
styles; `tools/mod_icons.py` supplies the transport, mode, queue and favorite glyphs.
The 264 px cover has 12 px corners. Existing widget names are preserved.

The art page uses `np_tint.png`, a black gradient with alpha 38..235 over the window tone.
The info page adds `np_scrim.png`: 320 × 324 at y 8, alpha 128 in the center,
with 36-row linear edges. The lyrics page uses `np_scrim_lyrics.png`: 320 × 332 at y 0,
alpha 68 with 44-row smoothstep edges. Decorative images and time labels are insensitive.

Favorite is a filled/outline star; while a podcast plays it becomes a saved/unsaved bookmark. While a server (Subsonic) track plays, streamed or downloaded, it is the server's favourite: `np_on_fav` (bound after
stock's, so it runs first) calls `ls_favorite(&lib_nd, ...)` and returns `RET_STOP`, so stock's `manage_myfav` (`0x4ef884`) never writes the stream record into `myfav`; `np_server_fav` reads the flag through `nd_row` (cached, re-read when the
track or `sba_gen` changes) and `np_fav_sync` keeps the star's style on it ([subsonic](subsonic.md)).
Mode and queue glyphs use `#C8C8C8` (repeat-off `#6E6E6E`).
The stock mode button (`btn_playmode`) keeps its four steps and looks. Its picture (`0x539888`) and click handler (`0x53b5fc`) read the *shown* mode,
which is Shuffle while the payload's Shuffle flag is on (also with Repeat all, set from the Queue page): the Shuffle step turns the flag on (stock mode 0),
the next step (Repeat all) turns it off. Two call sites and the mode hook make this ([shuffle](shuffle.md) "Where the mode is shown"); the page itself is unchanged.
The stock `slider_play` retains a 30 px seek target with a 6 px track, 30% white track,
`#FFFFFFEB` fill and radius 4.

## Cover tone and corners

Stock's `parseplaycover_thd` writes `/tmp/coverpic.jpg` or `/tmp/externpic.jpg`.
A playing Navidrome track has no such file: `np_server_art` draws its cached cover (`sba_now_cover`, docs/modules/subsonic.md) over `img_playcover` from `np_on_art_paint`, before the corners; local tracks keep stock's picture.
On a track change the previous server cover stays drawn (never stock's placeholder) until the new one is decoded: while a server track (`REC_ID <= -2`) plays, `np_on_art_paint` draws `sbmp`,
and when it sees a `REC_ID` that `np_server_art` has not looked at it starts a 30 ms one-shot (`np_art_once`, ctx 0; the decode is never in the paint). A track with no cover file yet (or none at all) keeps the previous cover
for `NP_SB_WAIT` (10) ticks, then stock's picture shows. Two tracks with the same cover file only change `sbrec`. A local track draws nothing of ours at once. While a server track plays,
`np_prefetch` asks `sba_now_cover` for the queue record after the playing one (`PLAY_QUEUE` at `mclGetPlayPos()+1`), once per such record.
`COVER_SRC` (`0x97cad8`) is 1 while busy, 2 for embedded art, 3 for folder art,
or 5 for cached art. The payload reads files only in the ready states and never waits on
the extraction mutex. Unreadable or empty files are retried; a rejected decode is retried
only after the file changes.

A cheap signature of source, file length and track path avoids rereading unchanged art.
Changed art first checks the shared album-tone cache, then decodes the 168 px cover cache,
falling back to the playing cover file. The full file key hashes at most 512 KiB plus length.
A same-length replacement under the same track/source without an observed busy state can
remain undetected until the track changes.

`m1_tone` maps maximum channel value to 32..192 and retains 23/25 of saturation;
black uses `#202020`. `m1_tone_get/put` caches 64 album tones in RAM, shared with
the [album page](album-page.md). A failed style update preserves the previous color.

`img_playcover`'s own `EVT_AFTER_PAINT` blends a precomputed 12 × 12 corner mask
against the gradient at that row. Only cover repaints run it. There is no global paint hook;
without the payload the cover is square.

## Status bar

`m1_bar_tint` and `m1_bar_black` in `patch/common.c` share one owner between
Now Playing and the album page. Only the owning window can restore black.
The bar uses the page's top-row tone, darkened until white text keeps at least 4.5:1 contrast.
It is found by the `system_bar` type; no widget pointer is cached.

Background/foreground listeners restore black or apply the tint. A top-window check in
the timer covers missed events. Foreground work refreshes page data before retinting.
Missing bars, failed style calls or refused lifecycle listeners leave the bar untouched.
Real status-bar appearance remains a device-validation concern.

## Time

`get_playtimeandlength` (`0x4e015c`) supplies seconds.
`np_elapsed` shows `m:ss` or `h:mm:ss`; `np_remaining` shows the negative
remaining value, clamped at zero. They replace the visibility of stock time labels rather
than competing with stock text writes. Invalid lengths restore stock labels.
Missing time widgets disable that portion without disabling tint.

## Information page

Page 3 (`view_info`) is text and hairlines only, on the existing `np_scrim`, in the 320 × 450 window:

- **Header.** The record's cover (`mb_art_t`, `patch/minibar.c`, 64 px, 8 px corners, drawn from the `np_i_art` view's `EVT_AFTER_PAINT`, decoded on the tick when the track changes and never in the paint) at (16, 36);
  title 20 px white at y 38, artist and album 16 px `#AAAAAA` at y 62 and 82, x 92, 212 px wide, one line each, ellipsis at the end. Text comes from `REC_TITLE` (else the file name), `REC_ARTIST`, `REC_ALBUM`, cut below 200 bytes.
- **Badge.** `HI-RES` or `DSD` (not translated): a gold `#E3C16F` 1 px outline picture (`np_i_badge_hires` / `np_i_badge_dsd`, text baked in, 49 and 35 px by 18, no fill, fixed against the Accent picker) right-aligned to x 304 at y 40; the title is narrower by its width + 8.
  The rule is the cassette theme's: `tape_badge` (`patch/tape.c`, one `mclGetInfo`): lossless and (over 48 kHz, or 24 bit from 44.1 kHz) is HI-RES, 1 bit is DSD, nothing for CD quality or lossy; DSD files also by extension when the player has no stream yet.
- **Quality line.** Hairline at y 112, the line at y 122: format, rate, bit depth, bitrate, values 17 px white, units (`kHz`, `bit`, `kbps`, always Latin) 12 px `#AAAAAA` 3 px after the value, 1 px dividers (white 18 %). Items are as wide as their content with equal gaps across x 16..304
  (`qlayout` in `tools/mod_nowplaying.py` is the model; `2822.4 kHz` and `22579.2 kHz` fit). An item with no value or a zero one (no bit depth) is dropped with its divider.
- **Rows.** Hairline at y 150, four rows 33 px apart (text tops 158, 191, 224, 257): Genre, Year, File Size, Location; label 16 px `#AAAAAA` at x 16, value 16 px white right-aligned to 304 in the room the label leaves (14 px gap), hairlines (white 15 %) between rows.
  A value too long is cut with an ellipsis at the end, the Location at the start (`...` and as much of the end as fits, looking at its last 200 bytes; `head_fit`), so the file name stays. Everything ends above y 288.
  Genre, Year and File Size are our keys (`Genre`, `Year`, `File Size`: stock's `player_filesize` reads "Location" in Ukrainian), Location is stock's word in the app language.

Stock writes the quality line and the five "Label:value" lines when the track changes (`label_info`, `label_album`, `label_genre`, `label_year`, `label_size`, `label_location`); they stay as the data source, never rewritten, and are hidden and made insensitive once ours show.
The tick (`np_info`) lays a part out when its stock text hash changed, or the track changed (`mb_track_key`: the header, and every row again, since a stream's stock text is the same for each record); the header's title, artist and album labels are shown once the header runs, and for `NP_RELAY` (3) ticks after the page starts or returns, because a label measures in its own style only once the window is open. Our labels are placed with `widget_move` / `widget_resize` from measured text
(`m1_text_w`), ellipsis at the end by the `hscroll_label`'s own, the Location's by `np_head_fit` (binary search over character starts). While the playing record is a server stream (`REC_ID <= -2`, mapped by `sba_rec_track`, and `REC_PATH` an `http` address) `np_stream_text` writes the size and location lines itself, since stock's come from the
stream address (token and salt included) and a file that does not exist: stock's label, then `N.NN MB` from the server size kept in the queue map (`sba_rec_size`; "Unknown" when none) or the saved server's scheme and host[:port] (`sba_url`, user info, path and query dropped; "Unknown" with no server).
A downloaded track plays from its own path and keeps stock's lines.
Fallback is per part: a part whose own widgets the asset lacks, or whose stock text is unreadable (failed read, longer than the 511 byte buffer, no `Label:value` shape, no quality item), shows stock's label again at its row, and the next good text takes it back. The header has no fallback beyond an empty line (stock's album label stays when the asset lacks it).

## Pins, safety and validation

`tools/pod.py` pins the init hook, called functions and `COVER_SRC`.
Important calls include `widget_set_style` (`0x66c448`),
`value_set_uint32` (`0x711858`) and `get_playtimeandlength` (`0x4e015c`).

A-B marker geometry is a separate pinned asset patch: `mod_nowplaying.patch_markers`
changes width/offset at `0x53b8d4` / `0x53b8ec` and y at
`0x53b9c4`, `0x53ba48`, `0x53ba64`, with prologue/call-site checks.
The affected functions are outside the boot path.

Runtime work is page-scoped, with no new thread or lock. Widgets/styles use stock setters;
fallbacks preserve stock behavior. Only the cover widget has paint-time payload work.
Tests check lifecycle, tone/corner models, cover caching, time formatting, the information page (layout model, badge rule, fallback),
contrast and stock hit targets. Real repaint behavior, slider rounding, corner blending,
intro dots and frame timing need the device.
