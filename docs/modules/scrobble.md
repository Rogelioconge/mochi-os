# Scrobbling

**Sources:** `patch/scrobble.c` (log, automatic upload), `patch/scrobup.c` (upload worker,
accounts), `patch/scrobpage.c` (Settings pages), `pj_member` / `pj_span` / `pj_next` in
`patch/pcjson.c`; constants `SC_*`, `SU_*`, `SA_*` in `offsets.inc`; pages in `tools/pod_pages.py`
(`SCROBBLING_PAGE`, `LB_PAGE`, `LF_PAGE`). **Tests:** `test/pod/scrobble.py`,
`test/pod/scrobup.py`, `test/pod/scrobpage.py`. **Preview:** `tools/preview/preview_scrobble.py`.

Listens are appended to `/mnt/mmc/.scrobbler.log` in Rockbox's AudioScrobbler 1.1 format, so any
`.scrobbler.log` uploader on a computer can send them. The device can also upload them itself to
ListenBrainz and Last.fm, by hand or automatically while music plays on Wi-Fi. The log rule, line
format and upload follow q2-pod; the automatic upload is our own.

No hook of its own: logging uses the tag-reader hook ([payload](payload.md) hook 4) and the page
timers that already watch the playing track. Nothing runs at boot or in the main loop.

## Settings

**Settings > Library > Scrobbling** (a value row, On / Off, `ACT_SCROBPAGE` 139) opens a cards page:

1. **Scrobbling** switch, off by default (`/mnt/data/m1plus/scrobbling`, `1` = on). Note: "Saved
   to .scrobbler.log on the card."
2. **ListenBrainz** and **Last.fm** rows → account pages.
3. **Auto Upload** switch, off by default (`/mnt/data/m1plus/scrobble-auto`), and **Upload
   Scrobbles**. Note (three wrapping lines, `pod_note1_t`): "Uploads on Wi-Fi while music plays."
   and, when [the upload record](#upload-record) has a line, " Last upload: Today 14:32 · 12 sent
   to ListenBrainz and Last.fm"

Both switch files are read once and kept in RAM. Turning logging on starts from the next look at
the playing track; turning it off forgets the current one. The tag-reader hook never reads the
file (it runs at boot) and does nothing until a poll has read it on. The Scrobbling switch gates only the logging:
nothing on the page is dimmed while it is off, and an existing log still uploads.

## The log

Header (written to an empty or missing file): `#AUDIOSCROBBLER/1.1`, `#TZ/UTC`, `#CLIENT/M1+ Music`.
Each listen is one line, about 100 bytes:

```
artist \t album \t title \t track number \t length (s) \t L \t start (Unix time) \t (MBID, empty) \n
```

- **Tags:** stock's freshly parsed `playsong_id3info` when it belongs to the track, else the song
  record. No title → file name without extension. Tabs and newlines become spaces; fields are cut
  on a UTF-8 boundary under `SC_STR` (256) / `SC_TITLE` (512) bytes.
- **Time:** the play's start on the wall clock, pinned at the first look with a set clock, so a
  pause never moves it. A clock set later (Auto Time) is back-computed. The system clock is UTC
  (stock's time zone only sets `TZ` for demo), so `#TZ/UTC` is correct.
- **Write:** one `open(O_APPEND)` + `write` + `fsync` + `close` under `scrobble_lock`, the same lock
  the upload holds for its reads and rewrite. A short write is not repeated, to avoid a duplicated
  half line.
- **Not logged:** podcasts, an empty or `Unknown` artist, a track whose length the player never
  reported. With a clock before 2020, the kill switch on, no card or a failed open, the write is
  retried at each look while the track plays.

## A listen

A track longer than `SC_MIN_S` (30 s) counts once `SC_MAX_S` (240 s) or half its length has been
**heard**. It is logged at that moment, so the last track before power-off is not lost, and once
per play. A position falling back under `SC_SLACK_S` (2 s) starts a new play (repeat one, restart).

Heard time comes from the player's position: a forward step counts only up to the wall time since
the last look plus 2 s. Seeks, the Memory Playback resume jump and pauses add nothing, and the
polling rate does not matter. CUE tracks are told apart by `REC_CUE_START`.

Entry points:

- **`scrobble_note(track)`** — the poll, called by the Now Playing, mini bar, Podcasts, iPod,
  Cassette and Vinyl timers (lit and dark). Asks the player at most every `SC_POLL_MS` (500 ms).
  While Scrobbling is off it returns before asking anything. It is also the only clock of the
  automatic upload.
- **`scrobble_started(info, path)`** — called from `pc_id3_path` on every fresh tag parse (including
  Memory Playback at boot). Copies the tags and starts the new play; it only reads `time_now_ms`,
  so the boot path never asks the player. The replaced track gets the time since its last look
  if that look saw it playing, then is judged.

Limits:

- A track no timer saw (played entirely under a stock page) has no length and is not logged.
- A track last seen playing is extrapolated to its end at the next start, so an unseen pause in
  that stretch counts as heard.
- Only the current track's pending line is kept; one still unwritten at a track change is lost.
- Repeat one of a track no timer sees is one play (the tag reader caches the same file).

## The account's file

Both accounts live only in `/mnt/mmc/scrobble.ini`, written by the user on a computer. Nothing is
on flash, Settings Files has no row for it and Reset All Settings does not touch it.

```
[LISTENBRAINZ]
TOKEN=0f8fad5b-d9cb-469f-a165-70867728950e
USER=name

[LASTFM]
USER=name
PASSWORD=the account's password
API_KEY=0123456789abcdef0123456789abcdef
API_SECRET=fedcba9876543210fedcba9876543210
```

Decisions:

- **The file is the only way in and out.** No token or password entry on the device, no sign-out:
  the user edits the file. A file on flash could not be found or edited by the user.
- **Plain text on the card**, token and Last.fm password included. Whoever has the card has both.
- **No built-in Last.fm API key**: `API_KEY` / `API_SECRET` are the user's own (last.fm/api).
- The device writes one thing: `[LISTENBRAINZ] USER=` after a valid token check (a display cache
  for the row after reboot).

Reading (`su_ini_scan`): BOM, CR and leading blanks dropped; `;` / `#` lines are comments; section
and key names are case-insensitive; the value is everything after the first `=`, trimmed; only the
first matching section and the first of each key count. No quotes or inline comments
(`TOKEN="abc"` sends the quotes). UTF-16 files read as Not Set. Only whole lines of the first
`SU_INI_MAX` (4 KB) are read, so a cut token is never sent. Shape checks: `TOKEN` and the API
fields are printable ASCII without spaces; `TOKEN` up to `SU_TOKEN` (128) bytes; `PASSWORD` up to 128 bytes without control bytes; `USER`
filtered through `su_name`.

Writing (`su_ini_set`): read whole, replace or insert only the `USER` value (insertion after
`TOKEN`, matching the file's line end), write `scrobble.ini.tmp`, sync, rename. Every other byte
stays. Refused, file unchanged, when there is no card, the file does not read or is over 4 KB, or
the card refuses the write.

The RAM copy is refreshed with one file read when a Scrobbling or account page opens, at an Upload
Scrobbles tap, at every job start and result, and at the automatic upload's look once all its
other conditions pass. So an edit made on a computer takes effect without a reboot. The worker
thread never opens the file; the UI thread copies credentials in and writes the name.

## Upload

`patch/scrobup.c` runs one job at a time (upload or check) on a worker thread through demo's
libcurl: HTTPS only, no redirects, `M1_CA` verification, `SU_CONNECT_S` 15 s / `SU_TOTAL_S` 60 s.
It has no hook, timer or page. Two owners start jobs: the Settings UI (`SCROBUP_UI`) and the
automatic upload (`SCROBUP_AUTO`). **A caller polls only its own job** (`scrobup_owner()`,
`scrobup_kind()`), otherwise a result would be lost or toasted for a job the user never started.
USB mode and Wi-Fi are the caller's to check.

| Call | Purpose |
|---|---|
| `scrobup_start(owner)` | Upload to every service that is set up and not refused. `1` started, `0` busy, `-1` cannot (kill switch, no card, nothing set up) |
| `scrobup_check_start` / `scrobup_lastfm_check_start` | Validate the ListenBrainz token / get a Last.fm session |
| `scrobup_busy()` / `scrobup_kind()` / `scrobup_owner()` | Busy from a start until its result is polled; the job kind (`SCROBUP_UPLOAD` 0, `SCROBUP_CHECK` 1, `SCROBUP_LFCHECK` 2); who started it |
| `scrobup_poll(&sent)` | `0` while running; then one result, once. `sent` is the listens taken, also on a failure |
| `scrobup_auth()` | Which services (`SCROBUP_LB`, `SCROBUP_LF`) refused or were left out |
| `scrobup_rejected()` | Listens refused for good in the last upload |
| `scrobup_account` / `scrobup_lastfm` | Account state from the RAM copy (no network). Last.fm: `SCROBUP_LF_NONE` 0 not set, `_NEW` 1 set and not yet asked, `_IN` 2 signed in, `_BAD` 3 refused |
| `scrobup_configured` / `scrobup_usable` | A service is set up / set up and not refused |
| `scrobup_invalid()` | The current token is the one the service refused (Invalid Token). RAM only, per boot, and it follows the file: another token is not invalid, the refused one put back is. No automatic upload starts while it stands |
| `scrobup_forget()` | Mark the RAM copy stale; the next read reloads the file |

| Result | Upload | Check |
|---|---|---|
| `SCROBUP_OK` | Every listen answered (taken or refused for good) | Valid; name stored |
| `SCROBUP_FAIL` | Network, timeout, TLS, 429, 5xx, other status, kill switch, too many refused runs | Request failure or unusable answer; nothing changes |
| `SCROBUP_AUTH` | Account refused (ListenBrainz 401; Last.fm error 4, 10, 13, 26) | Refused; token kept |
| `SCROBUP_DISK` | Log could not be read, archived or rewritten; the log is unchanged | Name could not be written |

### Upload run

1. Read the log in `SU_WIN` (64 KB) windows under the lock; take whole lines. No log (`ENOENT`) is
   nothing to upload; any other open, seek or read failure is `SCROBUP_DISK`. Skip comments,
   lines over `SU_LINE`, non-`L` lines, missing artist/title, and times before `SU_TIME_MIN`
   (October 2002; ListenBrainz refuses a whole request for one such line). A last line without a
   newline waits.
2. Send batches of `SU_BATCH` (50) listens or `SU_RAW` (16 KB) of log, with no lock held. Per
   service:
   - **200**: taken.
   - **400 on a batch**: re-send each listen alone; a listen answered 400 alone is refused for
     good. A bad listen never blocks the rest of the log.
   - **Anything else**: stop. Unanswered listens stay in the log.
   - The kill switch is checked before every request after the first.
3. Retire once, under the lock (`su_retire`): bytes up to the last answered listen leave the log,
   to `.scrobbler.log.sent` (at least one service took it) or `.scrobbler.log.rejected` (all
   refused; the user can fix and re-add those lines). Write order: new log as `.tmp`, archives,
   rename, so a full card fails before anything is archived. The retired bytes are re-read and
   hashed first; if the log changed meanwhile, nothing is retired (`SCROBUP_DISK`). Listens
   appended during the upload sit after the retired bytes and stay. The appender and this rewrite
   share `scrobble_lock`, so a line is never torn; the UI thread can wait on it for one 64 KB read
   or the rewrite.

Up to `SU_REJ` (128) separate runs of refused listens are tracked per upload; beyond that the
upload ends as `SCROBUP_FAIL` and the next one continues.

### Upload record

Every upload job that sent at least one request (manual or automatic; result ok, fail, auth or
disk) appends one line to `/mnt/mmc/.m1plus/scrobble-uploads` from the worker, just before the result is
published. Uploads that found nothing to send, checks, the kill switch and a missing card are not
recorded. A failed write changes nothing of the result.

```
2026-11-16T14:32:05Z auto ok listenbrainz=12 lastfm=12 rejected=0
```

UTC time (`0000-00-00T00:00:00Z` while the clock is unset), `manual` or `auto`, `ok` / `fail` /
`auth` / `disk`, then each service that took part with the listens it took (`su_flush` counts a
listen once every service of the job has answered it), then the listens refused for good. Past
`SU_UP_MAX` (8 KB) the newest half is kept at a line start (tmp + rename).

The Scrobbling page reads the last line (`lb_last_load`) when it opens and at the end of its timer
(a job finished while it is up), and writes `lb_note` into the note under Upload Scrobbles: day (Today,
Yesterday, else month and day, local time) and `hh:mm`, then Failed / Refused / Card error for a
non-ok result, then "N sent to ListenBrainz and Last.fm" (equal counts), or each service with its
count, or "Nothing sent". A record with an unset time, or a device clock that is unset, shows no
day or time. No record or an unreadable line: only the note's own text.

### Two services, one log

Each batch goes to ListenBrainz, then Last.fm. A listen leaves the log once every participating
service has taken or refused it.

- A temporary failure on either service stops the upload; the next upload re-sends those listens
  to both, relying on the services to drop duplicates.
- **A refused account is left out** of later uploads so it never holds the log back; its listens
  leave on the other service alone. The refusal is RAM only and follows the file: new credentials
  clear it, as do a valid check, an upload with listens taken, or a reboot. When every service is
  refused, a manual upload asks them all again.

### Requests

**ListenBrainz:** `POST https://api.listenbrainz.org/1/submit-listens` (`listen_type: import`;
`release_name`, `duration`, `tracknumber` only when present; `additional_info` carries
`media_player` and `submission_client` = "M1+ Music"), header `Authorization: Token …`.
Invalid UTF-8 is sent as U+FFFD so one bad tag cannot fail a batch. Check:
`GET /1/validate-token`; `valid: true` with a `user_name` is OK. The name is untrusted and
filtered (`su_name`, 64 bytes). The poll writes it back as `USER=` only when the file's token is
still the one checked and the name differs.

**Last.fm:** `POST https://ws.audioscrobbler.com/2.0/`, form-encoded. `api_sig` is MD5 of the
parameters sorted by byte order of their names, plus the secret (libcrypto's `MD5_*`, imported by
demo).

- `auth.getMobileSession` gets the session key, kept in RAM only with the credentials it came
  from and asked again each boot. Error 9 drops the key and retries once.
- A tag byte that is not valid UTF-8 goes as U+FFFD into both the body and the signature, since
  any other byte would make the signature wrong.
- `track.scrobble` sends up to 50 listens (`artist[i]`, `track[i]`, `timestamp[i]`, plus `album[i]`,
  `duration[i]`, `trackNumber[i]` when present). Per listen, an `ignoredMessage` code other than 0 is
  refused for good, except 5 (daily limit), which is a failure. An answer that does not cover
  every listen confirms nothing.
- Errors 4, 10, 13 and 26 refuse the account. Every other error is a plain failure.

## Automatic upload

With Auto Upload on, `scrobble_note` drives it (`sa_tick`). With nothing counted and no job, its
cost is two compares. Listens are counted in RAM; older ones in the log go along with the first
upload.

At most every `SA_EVAL` (60 s), in order:

1. the first counted listen is `SA_WAIT` (600 s) old, so a run of tracks gives one upload;
2. `SA_RETRY` (1800 s) since a failure;
3. no job is running;
4. USB mode is off;
5. Wi-Fi is connected (Wi-Fi is never switched on);
6. only then is `scrobble.ini` read, and a usable service must exist;
7. `scrobup_start(SCROBUP_AUTO)`; its `-1` counts as a failure (retry after `SA_RETRY`).

Results are silent: no toast, dialog or widget change. OK lowers the count. FAIL or DISK waits
`SA_RETRY`. AUTH marks the service refused, and the next look uploads to the other service if
there is one. An upload that sends nothing and gets a refusal stops automatic uploads until
reboot, so a service that takes nothing cannot drain the log into `.rejected`; manual uploads are
unaffected. No token is not a failure. The automatic upload only reads `scrobble.ini`: it starts no
check, so it adds no `USER` line.

The result is collected from the poll or from the Settings pages before they use the worker, so a
finished automatic job never blocks the user's start. Nothing keeps the device awake for it;
playback does. An upload starts only while a page whose timer calls `scrobble_note` is up.

## Settings pages

`patch/scrobpage.c` (`lb_*`, `lf_*`). The pages show accounts and change nothing.

- **ListenBrainz row / Account:** user name; "Not Set"; "Invalid Token"; "Checking…"; empty
  for an unchecked token.
- **Last.fm row / Account:** `USER`; "Not Set" unless all four keys are present; "Sign-in
  Failed".
- Account page notes: "Put your token from listenbrainz.org in scrobble.ini on the card." / "Put
  USER, PASSWORD, API_KEY and API_SECRET under [LASTFM] in scrobble.ini on the card. Get an API
  key at last.fm/api." The token and password are never shown.
- On page open, an unchecked token or new Last.fm credentials are checked when Wi-Fi is up and no
  job runs (the page's own service first). A check never toasts.

**Upload Scrobbles** refusals, in order:

| Condition | Toast |
|---|---|
| A job is running | "Already uploading" |
| USB mode | "Not available in USB mode" |
| No card | "Storage unavailable" |
| No service set up | "Set up an account first" |
| No Wi-Fi | "Connect to Wi-Fi first" |

Otherwise "Uploading scrobbles", then one result toast:

| Result | Toast |
|---|---|
| AUTH, ListenBrainz | "ListenBrainz: Invalid Token" |
| AUTH, Last.fm | "Last.fm: Sign-in Failed" |
| DISK | "Card error, %d sent" |
| FAIL | "Upload failed, %d sent" |
| OK with rejected | "%d sent, %d rejected" |
| OK | "Scrobbles sent: %d" / "Nothing to upload" |

A page timer (`lb_tick`, 500 ms) runs only while a page is up and a job is in flight. It keeps
the device awake during the user's own upload, and shows the toast at the first lit tick. A job
that ends after the pages close is reported when one opens again.

## Limits

- 429 and 5xx are plain failures: no back-off, `Retry-After` is not read.
- A batch answered 400 costs one request per listen, with no connection reuse.
- Listens sent while a service stood refused are never sent to it later; nothing re-sends
  `.sent`.
- Last.fm error 6 is a plain failure without narrowing: a line that always triggers it holds the
  log back until removed.
- A wrong Last.fm key or secret marks the whole account refused, like a wrong password.
- A Last.fm password that starts or ends with a blank cannot be written in the file.
- `scrobble.ini` over 4 KB: uploads work if the account is in the first 4 KB, but the name is not
  saved, so each page open re-checks.
- The log rewrite replaces another writer's header (Rockbox's `#CLIENT/`) with ours.
- `time_now_ms` wraps after 49 days of uptime.
- A manual upload leaves the automatic count alone, so the next automatic upload may find nothing
  to send (one log read, no request).
- A page that opens with an unconfirmed token starts a check; until it answers (at most
  `SU_TOTAL_S`) Upload Scrobbles says "Already uploading".
- Last.fm `USER` is not corrected from the service's answer.
- A 400 that every request gets (a service API change) asks once per batch and per listen, then
  empties the log into `.rejected`; nothing re-sends that file, and the automatic upload stops
  after one such run.
- A failed archive write can leave part of the lines in `.sent` / `.rejected`; the upload that
  succeeds archives them again.
- An upload already running when the card goes to a computer over USB still reads and, if the card
  is mounted then, rewrites the log.
