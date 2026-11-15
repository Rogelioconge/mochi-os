# Now Playing

**Sources:** `patch/nowplaying.c`, `tools/mod_nowplaying.py`, `patch/common.c`. **Tests:**
`test/pod/nowplaying.py`, `test/pod/shared.py`. **Preview:**
`tools/preview/preview_nowplaying.py`.

The stock `playing_page` gets cover-coloured backgrounds, rounded artwork, elapsed/remaining time
and reformatted track information. Playback, the slider and stock lyric loading stay stock.
[Lyrics](lyrics.md), [Queue](queue.md), [More](playmore.md) and [podcasts](podcasts.md) have their
own docs.

## Hook and lifecycle

The init hook calls `playing_page_init` through its trampoline and returns the stock result. After
a successful init with a window, `np_start` attaches page listeners and a repeating timer: 500 ms
lit, 1000 ms dark. A refused timer or listener leaves stock behaviour. Every tick also notes the
seconds heard for [scrobbling](scrobble.md).

- A replacement page stops the previous timer.
- Destroy acts only on the current window: it restores the status bar, removes timers and clears
  state. Stale callbacks end without touching widgets.
- A covered normal page skips cover, time and info work. A dialog can leave the page partly
  visible, so its data keeps updating beneath it.

## Layout and assets

The window is 320 x 450 px. `tools/mod_nowplaying.py` defines widget geometry and page styles;
`tools/mod_icons.py` supplies the transport, mode, queue and favourite glyphs. The 264 px cover
has 12 px corners. Existing widget names are kept.

- Art page: `np_tint.png`, a black gradient with alpha 38..235 over the window tone.
- Info page: `np_scrim.png`, 320 x 324 at y 8, alpha 128 in the centre, 36-row linear edges.
- Lyrics page: `np_scrim_lyrics.png`, 320 x 332 at y 0, alpha 68, 44-row smoothstep edges.
- Decorative images and time labels are insensitive.
- Mode and queue glyphs are `#C8C8C8` (repeat-off `#6E6E6E`).
- The stock `slider_play` keeps its 30 px seek target and 6 px track (30% white track,
  `#FFFFFFEB` fill, radius 4).
- The mode button keeps its four steps and looks; the shown mode follows the Shuffle flag, see
  [shuffle](shuffle.md).
- Favourite is a filled or outline star. While a podcast plays it is a saved/unsaved bookmark.
  While a server track plays it is the server's favourite ([subsonic](subsonic.md)); stock's
  `manage_myfav` never writes the stream record.

## Cover tone and corners

Stock's `parseplaycover_thd` writes `/tmp/coverpic.jpg` or `/tmp/externpic.jpg`. A playing
Navidrome track has no such file, so its cached server cover is drawn over `img_playcover`, see
[subsonic](subsonic.md). The previous server cover stays (never stock's placeholder) until the new
one is decoded, and the decode is never in paint: a 30 ms one-shot starts it on a new record. A
track with no cover file yet keeps the previous cover for `NP_SB_WAIT` (10) ticks, then stock's
picture shows. While a server track plays, `np_prefetch` asks for the next queue record's cover
once. A local track draws nothing of ours. `COVER_SRC` is 1 while busy, 2 for embedded art, 3 for folder art, 5
for cached art. The payload reads files only in the ready states and never waits on the extraction
mutex. Unreadable or empty files are retried; a rejected decode is retried only after the file
changes.

A cheap signature of source, file length and track path avoids rereading unchanged art. Changed
art first checks the shared album-tone cache, then decodes the 168 px cover cache, falling back to
the playing cover file. The full file key hashes at most 512 KiB plus length. A same-length
replacement under the same track and source can go unnoticed until the track changes.

`m1_tone` maps the maximum channel value to 32..192 and keeps 23/25 of saturation; black uses
`#202020`. `m1_tone_get/put` caches 64 album tones in RAM, shared with the
[album page](album-page.md). A failed style update keeps the previous colour.

`img_playcover`'s own `EVT_AFTER_PAINT` blends a precomputed 12 x 12 corner mask against the
gradient at that row. Only cover repaints run it. There is no global paint hook; without the
payload the cover is square.

## Status bar

`m1_bar_tint` and `m1_bar_black` in `patch/common.c` share one owner between Now Playing and the
album page. Only the owning window can restore black. The bar uses the page's top-row tone,
darkened until white text keeps at least 4.5:1 contrast. It is found by the `system_bar` type; no
widget pointer is cached.

Background and foreground listeners restore black or apply the tint. A top-window check in the
timer covers missed events. Foreground work refreshes page data before retinting. Missing bars,
failed style calls or refused listeners leave the bar untouched.

## Time

`get_playtimeandlength` supplies seconds. `np_elapsed` shows `m:ss` or `h:mm:ss`; `np_remaining`
shows the negative remaining value, clamped at zero. They replace the visibility of stock time
labels rather than competing with stock text writes. Invalid lengths restore the stock labels, and
missing time widgets disable only that part.

## Information page

Page 3 (`view_info`) is text and hairlines on the existing `np_scrim`.

| part | layout |
|---|---|
| Header | cover (`mb_art_t`, 64 px, 8 px corners, at (16, 36), decoded on the tick, never in paint); title 20 px white at y 38; artist and album 16 px `#AAAAAA` at y 62 and 82; text x 92, 212 px wide, one line, ellipsis at the end. Text is `REC_TITLE` (else file name), `REC_ARTIST`, `REC_ALBUM`, cut below 200 bytes |
| Badge | `HI-RES` or `DSD` (not translated): gold `#E3C16F` 1 px outline picture (`np_i_badge_hires` / `np_i_badge_dsd`, 49 and 35 by 18 px), right-aligned to x 304 at y 40, never tinted by the accent. The title is narrower by its width + 8 |
| Quality line | hairline at y 112, line at y 122: format, rate, bit depth, bitrate. Values 17 px white, units (`kHz`, `bit`, `kbps`, always Latin) 12 px `#AAAAAA` 3 px after, 1 px dividers (white 18%). Items as wide as their content with equal gaps across x 16..304 (`qlayout` in `tools/mod_nowplaying.py`). An item with no value or zero is dropped with its divider |
| Rows | hairline at y 150, four rows 33 px apart (text tops 158, 191, 224, 257): Genre, Year, File Size, Location. Label 16 px `#AAAAAA` at x 16, value 16 px white right-aligned to 304, hairlines (white 15%) between. A long value ends in an ellipsis; Location is cut at the start (`head_fit`, last 200 bytes) so the file name stays. Everything ends above y 288 |

- **Badge rule** is the cassette theme's `tape_badge` (`patch/tape.c`, one `mclGetInfo`): lossless
  and (over 48 kHz, or 24 bit from 44.1 kHz) is HI-RES, 1 bit is DSD, nothing for CD quality or
  lossy. DSD files are also recognised by extension when the player has no stream yet.
- Genre, Year and File Size are our keys; stock's `player_filesize` reads "Location" in
  Ukrainian. Location is stock's word in the app language.
- Stock writes the quality line and the five "Label:value" lines on a track change (`label_info`,
  `label_album`, `label_genre`, `label_year`, `label_size`, `label_location`). They stay as the data
  source, never rewritten, and are hidden and insensitive once ours show.
- The tick (`np_info`) lays a part out when its stock text hash or the track changed
  (`mb_track_key`). The header labels are shown after the page opens, and for `NP_RELAY` (3)
  ticks after it starts or returns, because a label measures in its own style only once the window
  is open. Labels are placed with `widget_move` / `widget_resize` from measured text (`m1_text_w`).
- While the playing record is a server stream (`REC_ID <= -2`), `np_stream_text` writes the size
  and location lines itself, since stock's come from the stream address (with token and salt).
  Size is `N.NN MB` from the server size in the queue map, else "Unknown". Location is the saved
  server's scheme and host[:port] ([subsonic](subsonic.md)). A downloaded track keeps stock's lines.
- Fallback is per part: a part whose widgets the asset lacks, or whose stock text is unreadable
  (failed read, over the 511 byte buffer, no `Label:value` shape, no quality item), shows stock's
  label again. The next good text takes it back. The header has no fallback beyond an empty line.

## Pins and safety

`tools/pod.py` pins the init hook, called functions and `COVER_SRC`. The A-B marker geometry is a
separate pinned asset patch (`mod_nowplaying.patch_markers`) with prologue and call-site checks;
the affected functions are outside the boot path.

Runtime work is page-scoped, with no new thread or lock. Widgets and styles use stock setters, and
fallbacks keep stock behaviour. Only the cover widget has paint-time payload work.
