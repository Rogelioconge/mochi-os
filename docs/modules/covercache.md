# Cover cache

**Sources:** `patch/covercache.c`, `patch/covercache.h`, `patch/pccover.c` (shrink), `patch/pcpng.c`
(PNG); `COVER_PINS` in `tools/pod_pins.py`. **Tests:** `test/coverflow.py`, `test/pod/coverart.py`.
**Preview:** `tools/preview/preview_cover_resample.py`.

The shared album-cover thumbnail cache and the one worker that builds it. Cover Flow, the Albums
grid, [Home](homecover.md), the mini player and the album page all read the same files. No hook.

## Files

- `/mnt/mmc/.m1plus/covers/r<key>-168.jpg`: one 168 px thumbnail per album, made from the album's
  first track (the album row is its first track by the query filter, [payload](payload.md) hook 6).
  Key = FNV-1a of artist then album, never 0 (`cc_path`, `cc_album_key`).
- An empty `r<key>-168.jpg` is a "no art" marker: both extractors failed, not retried. None is
  written over an existing file, for a vanished track, or when the rename failed (the next open
  retries).
- Every file is written to `.tmp` and renamed. Nothing is written outside the card. To clear the
  cache, delete the folder from a computer or use Clear Cover Cache ([homecover](homecover.md)).
- Stock's `/mnt/mmc/.downpic` is keyed by an MD5 we cannot reproduce and holds 90 px images, so it is
  never read.
- One size only. The Pod's 264 px cover pane needs no second tier: it uses the demo's full-size file
  for the playing track and, for its random rotation, a transient extraction to
  `/tmp/m1plus-pane.jpg` (`cc_build_add_file`: no cache file, no marker; see [ipod](ipod.md)).
- `cc_build_add_aspect` is the same one-off job for the timed cover page ([bigcover](bigcover.md)).
  `pv_cover_aspect` keeps the shape of a picture whose longer side is exactly the request, where
  stock's fit (`cc_stock_fit`) stretches it to a square. It searches only the cover source stock
  chose (2 embedded, 3 folder), never the other as a substitute.

## The builder

One job set and one pthread for the whole app (`cc_build_*`).

| Call | Does |
|---|---|
| `cc_build_open(capacity, mode)` | takes the app's one set; refused while another page holds it |
| `cc_build_add(track, key)` | queues an album; `CC_MISSING` skips one whose file, picture or marker exists |
| `cc_build_start()` | makes the folder, needs 16 MB free (`statfs`), starts the worker |
| `cc_build_done()` / `_total()` | the counters pages poll |
| `cc_build_stop()` | cancels; joins and frees if the worker has exited |
| `cc_build_near_step` | resumable nearest-first scan the Albums page and Home use, 64 albums a step |

Modes: `CC_MISSING` (only missing covers), `CC_REBUILD` (extract every album again to `.tmp` and
rename over the file, so an old picture or a "no art" marker is replaced atomically; an album that
now yields nothing keeps what it has), `CC_DURATIONS` (track lengths, [album-page](album-page.md)).

- **One worker at a time, app-wide.** A page that finds the set taken starts nothing. A stopped
  worker still inside its last album is orphaned: it keeps the set (`cc_build_busy` is true) and the
  next call joins it. Pages that use the set: Cover Flow, the Albums page (background build) and
  Home (a progress line, stopped when Home leaves the front; its Cover Flow button stops its own
  build before opening the page). It runs at nice 10 (`setpriority`, o32 syscall, no import).
- The worker touches only its jobs (strings copied on the UI thread), three `volatile` counters, the
  covers folder and the stock art calls under `parse_cover_mutex` (the lock every stock caller
  holds). Never a widget, a deque or the image manager. `art_lock` checks the cancel flag, so a Back
  that waited behind a stock parse skips the extraction and writes no marker.
- The shared `/tmp/.tmp_picture` is renamed to `/tmp/.m1plus_art` under the lock and shrunk after
  the unlock.
- A progressive JPEG over 4 MP (`PV_COVER_PROGRESSIVE_PX`) or 8192 px on a side is refused
  (`PV_REFUSED`; libjpeg buffers all its coefficients): no art, and stock is not asked.
- No build below 16 MB free, without a card, or if `pthread_create` fails.

### Hung jobs

A cover that hangs the worker must not hang the boot or the pages.

- `.m1plus/covers/.inflight` records the job, written once `art_lock` holds the lock for it and
  removed after the extraction. `cc_build_open` turns a leftover one into a strike (an empty
  `r<key>-168.jpg.try`; a power-off is no proof) and a second strike into
  `r<key>-168.jpg.bad`. No set queues a key that has a `.bad`.
- Rebuild Covers removes every `.bad` once (`cc_clear_bad`), so each album gets one retry.
  Clear Cover Cache removes both files.
- `.bad` and `.inflight` are plain text, one field per line, ending with `end`: `m1plus cover 1`,
  `key`, `build`, `track`, and in a `.bad` also `result` (timed out / interrupted twice), `phase`
  (where progress stopped: not a proof the file is corrupt) and the image's path, size and
  format when known. A leftover `.inflight` is read defensively; a bad one is removed and no one is
  blamed.
- **Stall watchdog.** `cc_build_done` stops a set whose counter has not moved for `CC_STALL_MS`
  (10 s): the worker is orphaned, the set reads as finished, `cc_build_stalled` stays true until the
  next open, and a pending Rebuild Covers request is kept so the next foreground resumes without
  the hung album. The watchdog writes the `.bad` itself (a worker that never returns could not) and
  removes the `.inflight` so the next boot takes no strike.
- A claimed job that still returns and publishes its cover clears its own `.bad`, so either order
  ends with the cover and no `.bad`. A failed or cancelled job leaves it.
- `CC_DURATIONS` sets are not watched. The `.bad` write runs on the UI thread, so a stalling card
  can still block it.

### Page rules

- A page owns its set only while it started it (Cover Flow: `cf.owns`); its progress timer failing
  stops the worker and shows the cached covers.
- Cover Flow's own build (`start_build`) is one synchronous pass before its Preparing screen: that
  screen has no scan state, and the wait is the expected one. When the open is refused only because
  an orphan is finishing, `on_retry` asks again every `POLL_MS` until it is free or 10 s have passed.
- Leaving a page stops its worker; the Preparing screen's Cancel resumes later.

## Cover resampling

Both steps are exact area averages. Stock's four-tap bilinear skips pixels on a 6:1 reduction and
aliases.

- **Extraction** (`art_make`, worker thread). Stock: `taglib_album_picture` writes the raw picture
  to `/tmp/.tmp_picture` (2 JPEG, 1 PNG, 0 none), then stock decodes whole, fits (long side to the
  request, a square-request side gives a stretch, a smaller picture is copied) and bilinear-resizes
  at quality 90. `toolsGetExternCover` picks a folder image (`.jpg/.jpeg/.png`; `folder.*`,
  `cover.*`, `<track>.*` first; JPEG at most 6 MiB, PNG 1 MiB).
- Ours: `art_embedded` calls `taglib_album_picture` the same way and `pv_cover` shrinks it: libjpeg
  DCT scaling to the smallest picture that still has both target sides, one row at a time, `ar_push`
  area average, quality 90 (PNG through `pcpng.c`). `art_folder` reproduces stock's file choice. No
  full bitmap of a 3000 px picture is ever held. The output size is stock's (`cc_stock_fit`).
- **Everything else is stock's own call:** a picture smaller than the request, an interlaced PNG, a
  progressive JPEG over 4.2 MP, CMYK, any decode or write error, an unreadable candidate.
- **Cache name** `r<key>-168.jpg`: the letter changes whenever the way a cover is made changes, so
  old files are never read again and every cover is rebuilt once (Cover Flow's Preparing screen or
  the Albums page in the background).
- **`cc_box`** (grid tiles, mini player, album page) is `ar_push` over the centred square: edge
  pixels weigh their covered fraction (integer weights, one rounding). `cc_sample`, Cover Flow's
  nearest sampler, is unchanged.
- `uv run python -I tools/preview/preview_cover_resample.py [--card | --image F | --m4a F]` writes
  `out/peek/cover-resample.png`: stock's output against ours at 3x zoom.

See [coverflow](coverflow.md), [albums](albums.md) (grid and background build), [homecover](homecover.md)
(Home's build, Rebuild Covers, Clear Cover Cache).
