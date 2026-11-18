# Software Update

**Sources:** `patch/update.c` (page), `patch/relnotes.c` (notes page), `patch/upver.c` (version
rules, notes parser), `patch/pcnet.c` (check and download jobs); page assets in `tools/pod_ui.py`
(`build_update_page`, `build_relnotes_page`). **Tests:** `test/pod/update.py`,
`test/pod/updatepage.py`. **Preview:** `tools/preview/preview_update.py`.

Over Wi-Fi the page finds the newest GitHub release, downloads its `update.bin` to
`/mnt/mmc/update.bin`, then calls the firmware's own TF card update. **Stock still does the battery
check, the confirmation, the MD5 checks and the flash**; nothing here touches flashing, the
bootloader or the recovery kernel.

No hook. The entry is a link row on the General page, the network is the Podcasts worker's libcurl
client (one job slot, see [network](network.md)), and the hand-over is a pinned call of stock's TF
card update click handler (below). The design follows q2-pod's Network Update (a header-only
request to `releases/latest`, a `.part` file renamed when complete, a page that shows progress).
The code is our own. Differences: the asset is fetched by its tag, the version is compared as
numbers, and the package's own version lines are checked.

## The page

**Settings > General > Software Update** (`ACT_UPDATE`) is a link row (chevron, glyph `download`)
right below About, in General's first card. Back returns to General. Stock's TF card update page is
not linked; it stays under All System Settings.

The page is black with the stock navbar and neutral colours; only the download popup's progress fill
takes the accent. One block with fixed places (`UP_YS` in `tools/pod_ui.py`, the same in every state):
48 px glyph, title (22 px), detail (18 px grey, two lines at most), a 260 x 48 pill, a second pill.
`%s` in a text is the version, put in by the payload.
The detail is put a second time at the page's first tick (hidden, then shown with its text): on the
device the one set before the window's first paint was not drawn, so the Idle version was missing.

| State | Title | Pills |
|---|---|---|
| Idle | M1+ Music, "Version 1.0.0" (a dev build shows its tag) | Check for Update |
| Checking | Checking... | |
| Up to date | Up to Date | Check for Update |
| Offered | Version 1.0.1 available | Download and Install; Release Notes (only when notes were kept) |
| Downloading | popup over the offer | Cancel (in the popup) |
| Downloaded | Update Downloaded | Install, Check Again |
| Failed | one title per cause (below) | Try Again |
| Cancelled | Download cancelled | Download and Install |

Failure states (title, explanation, pills):

| State | Title | Explanation | Pills |
|---|---|---|---|
| No Wi-Fi | Connect to Wi-Fi first | Turn on Wi-Fi and try again. | Try Again |
| Clock never set | Set the date first | Secure connections need the right date. | Try Again |
| No CA bundle | Certificates missing | This device has no certificate bundle. | none |
| Certificate | Certificate problem | The server's certificate was not accepted. | Try Again |
| No connection | Can't reach GitHub | Check your Wi-Fi connection. | Try Again |
| Not a release answer | Can't check for updates | GitHub did not name a release. Try again later. | Try Again |
| Wrong package | Download doesn't match | The file was not the version offered. Nothing was changed. | Try Again |
| Under 110 MB free | Card is full | Free at least 110 MB on the card. | Try Again |
| Write failed | Can't write to the card | Check the TF card and try again. | Try Again |
| No memory | Not enough memory | | Try Again |

Other explanations: Idle "Version 1.0.0", Up to Date "You have the latest version.", Offered
"Current version: 1.0.0", Downloaded "Version 1.0.1 is ready to install." All strings are
translation keys in 13 languages ([i18n](i18n.md)). **Try Again** repeats the job that failed: the
check, or the download of the release already offered. The "Version 1.x.y available" title is sized
for two digits a part; a longer number is clipped.

Actions:

- **Download and Install** asks first in the stock confirm dialog ([overlays](overlays.md)):
  "Download 1.0.1 (55 MB)? It replaces update.bin on the card." Buttons are relabelled Cancel and
  Download by a timer that finds the dialog by name. Cancel or Back starts nothing and makes no
  request.
- **The download popup** is the Podcasts refresh dialog's scrim and card: title "Downloading 1.0.1", grey line "This may take a few minutes.", a 6 px
  progress bar, "NN%" and Cancel. Cancel (or Back) asks the worker to stop; the line says
  Cancelling... until it has stopped. Then the `.part` is deleted, the old `update.bin` stays and
  the page says Download cancelled. Errors close the popup and show on the page. A download waiting
  for the job slot shows 0 % at once.
- **When the download finishes** the popup closes and, if this page is in front, stock's TF card
  update is called on the next tick. The page's block is cleared first (glyph, texts, pills hidden
  and insensitive) and restored when the call returns. The dialog is translucent, and without the
  clearing the pills show through it. The user lands on stock's own confirmation with no page in
  between. If the user answers No, the page shows Update Downloaded; **Install** calls it again.
- **Check Again** asks GitHub again. A version that is offered, including the one already
  downloaded, can be downloaded again through the same path; the old file stays until the new one is
  verified. Nothing newer: Up to Date.
- **Opening the page** forgets an old answer or failure but keeps a finished download while
  `/mnt/mmc/update.bin` is still on the card (Update Downloaded).
- **Now Playing** leaves the page and cancels what runs; the `.part` is deleted.
- While a job runs, the page's own timer calls stock's `reset_poweroptions_timer(1, 1, 0)` once a
  second (standby and auto power-off countdowns reset, the screen light left alone; standby would
  stop the Wi-Fi), as the Podcasts downloads do. Under a stock dialog the timer leaves everything
  alone.
- **One job at a time.** The check and the download use the worker slot of `pcnet.c`
  (`PN_KIND_UPDATE`). A running Podcasts download has its own thread and goes on beside them.

## Release notes

After a check that ends in an offer, the same job asks
`https://api.github.com/repos/<repo>/releases/tags/<tag>` (the tag found, never `latest`) and keeps
the release `body` in memory (`pn_up_notes`; nothing on the card).

- **Only HTTP 200 counts and every failure is non-fatal**: 404, 403 rate limit, network or
  certificate errors, an answer over `PN_UP_API_CAP` (64 KB), missing, null, empty or malformed
  `body` leave the offer standing without notes (no pill). Up to Date and the error states fetch
  nothing; a new check clears old notes; Cancel during the request cancels the check.
- `up_notes` finds the top-level `"body"` string with a depth-tracking scan (a `body` key of the
  `author` or `assets` objects is never taken), decodes JSON escapes and surrogate pairs, and cleans
  it for the screen: `#` heading markers and `**` dropped, `- ` and `* ` items shown as bullets, three
  line feeds made two, plain text otherwise. The result is cut at `UP_NOTES_MAX` (8192 bytes) between
  two UTF-8 characters.
- The `Accept: application/vnd.github+json` header is not sent: it needs `curl_slist_append`, which
  the payload does not import, and the API answers JSON without it.

The notes page (`m1plus_relnotes`) is black with the stock navbar. It copies the Find Cover & Lyrics
lyrics detail's scroll mechanism: a stock list holding one content view that the payload paints
with the scroll offset taken off the canvas, so the stock scroll view does the drag and fling. Text
is wrapped once by the Podcasts episode wrapper (`pd_lines`, `patch/pcwrap.c`) to 288 px at x 16:
heading "Version 1.0.1" (22 px), then notes at 18 px on a 24 px pitch. Limits: 600 characters per
source line, 700 wrapped lines in all. Back returns to the update page, still offering the release (Now Playing leaves and cancels).
The Lock Screen's Custom Wallpaper instructions ([lockscreen](lockscreen.md)) use the same asset
and painter at 20 px on a 27 px pitch.

## Version rules (`patch/upver.c`)

- **The tag** is exactly `D+.D+.D+`: three runs of 1 to 5 decimal digits, nothing before, between or
  after (no `v`, `-rc1`, sign, space, line break, query or fragment). Anything else is "Can't check
  for updates", never "newer". Leading zeros parse.
- **The comparison** is numeric, major then minor then patch (1.10.0 > 1.9.9).
- **The build's version** is `tools/build.py VERSION`, injected as `-DM1PLUS_VERSION`, with
  `-DM1PLUS_DEV` (1 when the build tag is not the release's) and `-DM1PLUS_REPO` (`tools/build.py
  REPO`, the one place the repository is named).
- **A release build** is offered a tag strictly newer than its version; equal or older is Up to
  Date, so a newer build is never offered an older release. **A development build is always offered
  the latest release.** Stock's updater refuses only an identical version and has no newer check, so
  this page is the only downgrade guard.

## The check

`pn_up_check` (after the guards: card, Wi-Fi, clock, CA bundle) asks
`https://github.com/<repo>/releases/latest` header only, without following redirects, https only,
verification on. The answer is accepted only when curl succeeded, the status is a redirect (301,
302, 303, 307, 308) and the redirect URL is exactly `https://github.com/<repo>/releases/tag/<tag>`
for the configured repository with a tag that parses. Anything else (200, 404, another host or
repository, `http://`, another path or case, a bad tag) is "Can't check for updates", never "up to
date". The offered tag is held for the download.

## The download

`pn_up_download` needs an offered release and **at least 110 MB free** on `/mnt/mmc` (the package is
about 55 MB and the old one stays until the rename), else "Card is full". Then:

1. `update.bin.part` is deleted and created fresh (no resume: a half file is not trusted).
2. `https://github.com/<repo>/releases/download/<tag>/update.bin`, **by the tag the page showed**,
   so a release published meanwhile cannot swap in another version. Redirects to the asset host are
   followed, https only, at most 128 MB (`PN_UP_CAP`), no overall timeout (a stalled transfer still
   ends at 1 kB/s for 30 s).
3. Writes go to the `.part`; progress is libcurl's transfer-info callback; Cancel stops through the
   same callback.
4. On success (HTTP 200, whole answer, length matches `Content-Length` when given): `fsync`, close.
5. **The package must say it is the version offered** (`up_info_ok`): a tar whose first member is
   exactly `firmware_v20.info`, line 1 `Shanling M1 Plus`, line 2 `V2.1-<tag>`
   (`tools/build.py TAG`). Another model or version, the stock version, a dev tag, CRLF, a member
   not first or a damaged tar is "Download doesn't match". Stock checks the other members' MD5s at
   install time.
6. `rename(.part, update.bin)`, then `fsync` of `/mnt/mmc`. **Any failure before the rename deletes
   the `.part` and leaves the old `update.bin`.**

A write that fails is "Card is full" when `statfs` then shows under 1 MB free, else "Can't write to
the card".

## Limits

- `SHA256SUMS` (uploaded by `make publish`) is not verified. The file is trusted by TLS to GitHub,
  curl's length check, the info lines and stock's MD5 check.

## Development channel

A local server can stand in for GitHub (`make ota-serve`, `make ota`); its address goes in a card
file (`UP_CHAN_FILE`, `tools/ota_server.py`). The package checks above still apply.

## Pinned stock call

`tf_update_click` is the click handler of the "TF card update" row of `systemset/fwupdate_page`
(`TF_UPDATE`, `TFUPDATE_PINS` in `tools/pod.py`; the build refuses on a mismatch). It ignores its
arguments and uses no page state: it shows stock's `msg_confirmupdate` in the modal confirm dialog
(only Yes goes on), runs `check_updatefw_exist`, and opens the flash dialog, or one of stock's own
messages (low battery, no firmware, latest, no card, no memory). The payload calls it directly on
the UI thread, so no hook, patched word or import is needed.
