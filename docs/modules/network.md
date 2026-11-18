# Network

`patch/net.c` and `patch/net.h` run one HTTP request. They are the only code of the payload that
makes, sets up, runs and frees a libcurl easy handle. Podcasts and the jobs of its worker
(`patch/pcnet.c`), the radio (`patch/radio.c`) and Subsonic (`patch/sbnet.c`) fill a `net_req_t`
and call `net_perform` on their own thread.

The firmware imports libcurl's easy interface only (no multi handle), so a request blocks its
thread and two requests at once mean two threads.

## What the layer owns

- **The handle.** `net_perform` makes it, runs the request and frees it. A caller never sees a
  handle; `net_status` and `net_type` read the status and the Content-Type from a callback while
  the request runs.
- **What every request sets.** No signals, http(s) only (a redirect to `file://` or `ftp://` is
  refused), the app's user agent, the CA bundle `M1_CA`. Verification is on: no
  `SSL_VERIFYPEER` / `SSL_VERIFYHOST` option is ever set, libcurl's defaults check the peer and
  the host name.
- **What a request chooses.** The body and header callbacks, the progress callback (its non-zero
  return is the request's Cancel), redirect hops, the connect and total time-outs, the stall
  limit, a range, extra headers, If-Modified-Since, and the `NET_*` flags (`patch/net.h`).
- **What comes back.** libcurl's result (`rc`; `NET_NOHANDLE` when no handle could be made and
  nothing was sent), the HTTP status, the announced length, and on request the Last-Modified
  time, the Content-Type and the address of a redirect that was not followed. An option libcurl
  refuses fails the request with `CURLE_FAILED_INIT` before anything is sent.
- **`net_init`.** libcurl's global state, called on the UI thread before a request's thread is
  made.

## Shared rules for a file download

The downloads (a podcast episode, an audiobook part, a Subsonic track, the update package) write
to a `.part` file and rename it when done. They keep their own way of writing and their own
checks of the finished file; these parts are one copy. What a
request's result means (`net_tls`, `net_http_passing`) is in `patch/net.c`; the rest, which never
touches libcurl, is `patch/netfile.c` / `netfile.h`:

| Part | Function | Used by |
|---|---|---|
| A TLS failure (certificate refused, CA bundle unreadable) | `net_tls` | `pn_rc`, the episode download, `sbd_http_code` |
| An HTTP status that may pass (5xx, 408, 429) | `net_http_passing` | episode download, archive fetch |
| A Content-Type that is no media file (text, JSON, XML) | `net_text_type` | episode download, Subsonic |
| A response's status, strong ETag, type and Content-Range | `net_head_t`, `net_head_line` | Subsonic (`sbn_header`), episode download (`pn_dhead`) |
| A 206 that answers a Range from an offset to the file's end | `net_head_resumes` | Subsonic |
| The If-Range header of a strong ETag | `net_if_range`, `net_strong_etag` | Subsonic, episode download |
| The reserve: the card keeps `NET_RESERVE_KB` (32 MiB) free | `net_room` | Subsonic (before the file and every MiB), episode download (before the file and every chunk) |
| A file with a size limit, the reserve asked every MiB, the reason a write stopped (`NET_W_*`) | `net_file_t`, `net_file_write` | Subsonic, the update package, pictures (`pn_fetch_file`) |
| `fsync` and `close` | `net_file_close` | Subsonic, the update package |
| `rename`, then `fsync` of the folder | `net_publish` | Subsonic, the update package, episode download |

What each still does alone:

- **Podcasts** gathers 512 KB and writes each chunk with open, append, `fsync`, close, so the card
  is rarely held open; retries with 10, 20, 40 s waits; resumes a `.part` of an earlier run on its
  size alone (no record on the card).
- **Subsonic** writes through one open descriptor, saves the resume record `<part>.etag` (strong
  ETag and whose file it is) with the first body byte and resumes only with it; checks the first
  bytes and the length of the finished file ([subsonic](subsonic.md) "Safe resume").
- **Audiobooks** ([audiobooks](audiobooks.md)) download a book's parts on a thread of their own
  (`patch/bkdl.c`, one book at a time, not in the episode queue) through `pnw_download`: the
  episode download's policy (`pn_dl_core`: Range resume of the `.part`, chunks, reserve, retries).
- **Software Update** never resumes; checks that the package is the version offered before the
  rename ([update](update.md)).

The podcast and Subsonic ways of writing stay separate: merging them would change how long the
card is held and when bytes are durable.

## Whose job it is

The job slot of `pcnet.c` (`pn.busy`, `pn.kind`) runs one job at a time for six pages: Find Cover & Lyrics, Software
Update, AutoEq, the Podcasts searches, refresh and archive, and the Audiobooks catalog. A page
stops only the kinds it starts: `pn_cancel(kinds)` sets the flag when the running job is one of
`kinds` and does nothing otherwise.

| Mask | Kinds | Who cancels |
|---|---|---|
| `PN_K_REFRESH` | refresh, import | the Podcasts refresh dialog (Cancel, the page closing under it) |
| `PN_K_PODCASTS` | search, preview, chart, archive | the Podcasts page (leaving a level, a new query, the page closing) |
| `PN_K_ART` | lookup, save | Find Cover & Lyrics / Find Artist Photo |
| `PN_K_UPDATE` | check, download | Software Update |
| `PN_K_EQ` | AutoEq list and preset | the AutoEq page |
| `PN_K_BOOKS` | LibriVox catalog (Popular, a search, the pictures) and a book's parts (the preview) | the Audiobooks page (leaving the LibriVox level, a new search, the page closing) |

Downloads are not jobs (a book's download has a thread of its own and `bd_pause` stops it): `pn_dl_cancel` (pause) and `pn_dl_drop` (cancel and delete) take an episode's key (events of the queue's state table), Subsonic and the radio have
their own.

## What stays with the callers

| Caller | Its defaults | Its own |
|---|---|---|
| `pcnet.c` `pn_req` | HTTP error fails, 16 hops, 20 s connect, 120 s total, stall under 1000 B/s for 30 s | feeds, JSON, pictures, the episode queue, the PN_* codes (`pn_rc`) |
| `pcnet.c` downloads | as above; no total limit, stall under 1 B/s for 60 s, `NET_IDENTITY`, Range | `.part` chunks, retries, the card margin |
| `pcnet.c` Software Update | as `pn_req`; `NET_HTTPS` on GitHub; the check is `NET_NOFOLLOW` + `NET_HEAD` | the tag, the package check, the rename |
| `radio.c` directory | 5 hops, 10 s connect, 30 s total; an HTTP error's status is the answer | mirrors, retries, the JSON |
| `radio.c` logo | HTTP error fails, 3 hops, 5 s connect, 10 s total | the picture file |
| `sbnet.c` `sbn_http` | HTTP error fails, 5 hops, 12 s connect, stall under 512 B/s for 45 s, `NET_NODOWNGRADE`, `NET_NOENCODING` | ETag, If-Range, Content-Range and identity checks of a resumed file, the JSON walker |

The threads, the job slot, the download queues and each page's Cancel are the callers' too
([podcasts](podcasts.md) "Network and feeds", [subsonic](subsonic.md), [radio](radio.md)).

## Where it stops

- `patch/net.c` is one HTTP request and nothing else; `patch/netfile.c` is the rules of a file on
  the card. Neither holds a queue, a thread or a page's state.
- The episode queue's life cycle is one state table in `patch/pcnet.c` ([podcasts](podcasts.md)
  "Network and feeds"); Subsonic's queue and the radio keep their own.
- The two download queues stay two models. Episodes: slots in a state table under one mutex,
  changed by the pages and the thread. Subsonic: slots only the worker changes, the pages post
  ordered messages (`patch/m1job.h`; [subsonic](subsonic.md) "The queue is the worker's"), which
  avoids the races of a shared state table.
- Fetching one resumable file is two copies (`pn_dl_attempt` in
  `patch/pcnet.c`, `sbn_download` in `patch/sbnet.c`) over the shared rules of
  `patch/netfile.c`. The differences: the stall limit, and `sbn_download` drops the `.part` when the
  connection is reset (curl 56), while a timeout or a short body keeps it.
- AutoEq's list and the radio's logo write their small files themselves.
- The radio has no download queue (two one-request threads over `net_perform`), so there is
  nothing to move.
- There is no event bus, no broadcast to subscribers and no scheduler over the sources, on
  purpose: the pages read status records on their own timers.
- Bulk downloads (an episode, an audiobook, a Subsonic track, the update package) run at the same
  time, each on its own thread, beside one job. There is no limit on them.
