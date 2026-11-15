# Timed cover page (bigcover_page)

**Sources:** `patch/bigcover.c`, `patch/covercache.c` (`cc_fit`, `cc_decode_fit`, the worker),
`tools/pod.py` `BIGCOVER_*`. **Tests:** `test/pod/bigcover.py`, `test/coverflow.py` (`cc_fit`),
`test/pod/coverart.py` (the aspect job).

Stock opens `bigcover_page` from Now Playing's 500 ms page timer after a counter runs out (20 ticks,
about ten seconds, with Cover Mode on). The page's `img_playcover` is 320 x 320 but stock fills it
from the shared 264 px `/tmp/coverpic.jpg` (cover source 2) or `/tmp/externpic.jpg` (3, 5), so the art
is enlarged 21 % and reads blocky. `COVER_SIZE` (264) is not touched: Now Playing, the lock card and
the remote-control replies depend on it.

## Design

The page gets a 320 px picture of its own, made from the original track's art and shown 1:1.
Stock's 264 px picture stays underneath.

- **Hook:** `bigcover_page_init` (payload hook 23, a PIC prologue hook). `m1plus_bigcover_init` runs
  the stock init, then (unless it failed, the window is null, `/mnt/mmc/m1plus-off` exists, or there
  is no `img_playcover`) starts the page state. Chosen over the call site because the page-init
  dispatcher calls it for every way the page is built, and no stock timer or counter is touched.
  Not boot-reachable.
- **State** (`bc`, one page): the window, `img_playcover`, a 250 ms timer (`bc_tick`),
  `EVT_DESTROY`, `EVT_AFTER_PAINT` on the cover, and one 320 x 320 RGBA bitmap made on first use.
- **Track identity:** the hashed playing path (`cc_playing`); 0 for nothing or a stream. A change
  drops the job and picture (`bc_drop`) and restarts in the same tick.
- **Source must belong to the playing track.** Stock's cover parser is asynchronous: after a track
  change `COVER_SRC` keeps the last track's value until the new one is parsed, and it stores
  `savecover_path` only afterwards. So the page requests only when `COVER_SRC` is 2 or 3 and
  `savecover_path` equals the playing path (`bc_src`), keeps the source with the job, and `bc_finish`
  drops the result unless both still match (`bc_same`; also checked in the paint). A dropped result
  is asked for again within the track's `BC_TRY_MS` (6 s) budget. If the paths were ever formatted
  differently the check never matches and stock's picture stays (the safe side).
- **Job:** only for source 2 (embedded art) or 3 (folder art) of a local track. Source 5 (the cached
  `.downpic` file) stays stock's picture: no job, nothing drawn. The job is
  `cc_build_add_aspect(track, "/tmp/m1plus-bigcover.jpg", 320, source)` on the shared worker (see
  [covercache](covercache.md)). It keeps the aspect ratio of an original whose longer side is exactly
  320, searches only the source stock chose, and keeps a picture only when its longer side is 320 (art
  under 320 px makes no file, so stock's picture stays). Retries last `BC_TRY_MS`; a running job is
  given up after `BC_RUN_MS` (10 s).
- **Picture:** a finished job is decoded by `cc_decode_fit` and fitted by `cc_fit`: the whole picture,
  never cropped, inside 320 x 320 over `#141414` (an exact area average, never nearest). Worker files
  are a pixel copy; a 320 x 240 picture sits at y 40 with bars. A missing, corrupt or oversized file or
  a failed decode gives up for the track. The file is removed after the decode.
- **Server track** (`sba_rec_track`, [subsonic](subsonic.md)): the key is the record's synthetic
  `REC_ID`, never the path (a stream address carries the login). No job runs for a stream; the picture
  is the cover file Now Playing draws (`sba_rec_cover`), fitted into the same bitmap. A stream whose
  cover is on its way keeps stock's page and asks again every tick for `BC_SRV_MS` (60 s); one the
  server has no picture for is given up. A downloaded track without a server picture uses the local
  job.
- **Audiobook part** with no stock picture (`np_cover_file` answers the book's cover, not a `/tmp` file):
  the book's cover file fitted into the same bitmap, no job, like a server track's. Tried until the
  per-track give-up time; a part with embedded or folder art takes the job as any local track. The
  book's cover stays only while `np_cover_file` still answers it: once stock starts on a picture
  (busy), it goes and the part's own picture gets the job.
- **Paint:** `EVT_AFTER_PAINT` draws the bitmap 1:1 over the widget only while the picture is ready
  and the playing track's key is the one it was made for. A stale picture is never drawn between a
  track change and the next tick.
- **End:** `EVT_DESTROY` stops the job if held (no wait), removes the timer and files, destroys the
  bitmap and clears the state.
- **Kill switch / fallback:** `/mnt/mmc/m1plus-off` skips it at the hook, and every failure leaves
  stock's page as it is.

## Idle view

**Sources:** `patch/bigcover.c` (`bc_timed_open`, `idle_view`, `idle_choice`, `idle_set`),
`patch/m1plus.c` (`ACT_IDLE`, `ACT_IDLESET`), `tools/pod.py` (`IDLE_SITE`, `IDLE_PINS`, `COVER_MODE`),
`tools/pod_pages.py` (`IDLE_PAGE`). **Tests:** `test/pod/bigcover.py`.

Settings > Now Playing > **Idle Display** chooses where the timed view goes: **Off**, **Album
Cover** (stock's page, sharpened above), **Cassette**, **Vinyl**, **Lyrics** or **VU Meter** (pages of
[tape](tape.md), [vinyl](vinyl.md), [idlelyrics](idlelyrics.md), [vu](vu.md)). A page the timer opened closes on
a tap: Cassette anywhere, Vinyl on the record (the chevron closes as always), Lyrics and VU Meter anywhere. The
same pages opened from the More sheet are unchanged (tap pauses).

- **Setting.** The last card of Settings > Now Playing is the value row Idle Display (`ACT_IDLE` 82)
  with the note "Shown after 10 seconds on Now Playing." (also on the picker). It opens the picker `m1plus_idleview`
  (`ACT_IDLESET` 83, arg 0 Off, 1 Album Cover, 2 Cassette, 3 Vinyl, 4 Lyrics, 5 VU Meter). Two stores make the
  choice: stock's Cover mode byte `COVER_MODE` (the timed view runs only while it is on) for Off or
  not, and `/mnt/data/m1plus/nowplaying-idle` (`0\n` Album Cover, `1\n` Cassette, `2\n` Vinyl, `3\n` Lyrics, `4\n`
  VU Meter; missing or invalid = Album Cover). `idle_choice` reads both live, so stock's Cover mode row
  and ours stay in step.
- **Saving.** Stock flips the byte, then saves `COVERMODE` to `config.ini`. `idle_cover_mode` saves
  first and stores the byte only on success. A destination pick writes the file atomically first,
  then turns the byte on if it was off; if that save fails the file is put back. Off only turns the
  byte off and keeps the destination. A failed save changes neither file, byte nor check.
- **Hook** (payload hook 24, not boot-reachable): the Now Playing timer callback reaches its
  `navigator_to("bigcover_page")` call only with the Cover mode byte on, `playing_page` on top and the
  countdown at zero; that call becomes `jal bc_timed_open`. `IDLE_PINS` pins the surrounding words.
- **Dispatcher** (`bc_timed_open(name)`): the kill switch, another name, a missing or invalid file or
  Album Cover all go to stock's `navigator_to(name)`. Cassette and Vinyl call `tape_open_idle()` /
  `vinyl_open_idle()` (the plain open plus an `idle` flag that makes a tap close the page); on -1,
  stock's call runs exactly once. VU Meter calls `vupage_open_idle()`. Lyrics calls `idlelyrics_open_idle()` only when the track has lyric
  rows now or the page is already up; otherwise Album Cover opens, and the next timed open, ten
  seconds later, looks again. Once the lyrics page is up, a track without lyrics keeps it. The page
  opens over Now Playing, which stays alive under it.
- **Already open.** The `*_open_idle` calls return 0 when their window exists, open nothing and leave
  the page's flag alone. Stock's countdown restarts as after any open.
- **Fallback.** Everything off the happy path ends in stock's call. No state, thread or timer of its
  own.

## Limits

- No delay choice: stock resets the countdown to 20 from several sites.
- Art under 320 px keeps stock's `scale_auto` picture (no extra upscale filter).
- After a track change the 264 px picture shows until the 320 px one arrives (usually under a second
  for a local file, longer for a large embedded picture).
