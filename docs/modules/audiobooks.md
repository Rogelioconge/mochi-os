# Audiobooks

**Sources:** `patch/bkmodel.c` (books, parts, progress, MP4 guard), `patch/books.h` (API and page
geometry), `patch/bkpage.c` / `bkpage.h` (window, Library and Book levels), `patch/bkfind.c`
(LibriVox, search and Preview levels), `patch/bknet.c` (LibriVox catalog), `patch/bkdl.c`
(manifest, folder, download queue), `pc_recent_rank` in `patch/pcmodel.c`; `tools/pod_books.py`
(layout model), `build_books_page` in `tools/pod_ui.py`.
The Extras item **Audiobooks** lists the books in `/mnt/mmc/Audiobooks`, plays them with progress
and resume, and can find and download public-domain books from LibriVox (Internet Archive) into
the same folder. Progress lives in the Podcasts resume ring, so no new state file exists. No hook:
the page opens from a menu row.

## What a book is on the card

The root is `/mnt/mmc/Audiobooks`, or any folder of `/mnt/mmc` named `audiobooks` in any case.

- A **book** is a subfolder with at least one audio file directly in it or in an immediate
  subfolder (`CD1/`). Deeper folders and folders without audio are not books.
- A **loose audio file** in the root is a one-part book titled by its name without extension.
- A subfolder with a readable `.librivox` manifest is a book too, with 0 parts until the first one
  lands. A `.part` file is never a part.
- Audio extensions are Podcasts' list, any case. Dot files and folders are skipped, as are names
  of 128 bytes or more, names with a control byte, and part paths of 192 bytes or more.
- **Cover:** `cover.*` or `folder.*` (jpg, png, jpeg) in the book folder; a loose file has none.
  A book without one shows its own art (below).
- **Title:** the folder name. Books sort by title, ASCII case-insensitive, a leading "The " aside.
- **Key:** `pc_hash("audiobooks/" + folder name)`, the file name for a loose book. The player's
  side (`bk_book_of`) computes the same key, so progress and speed are per book.
- **Parts** are the book's audio files in natural order (`bk_natcmp`: digit runs by value, case
  ignored, `/` sorts first). `Part 2` comes before `Part 10`, `CD1/10` before `CD2/01`. A part's
  ring key is `pc_hash(full path)`, as for a podcast episode.
- **Progress** (`bk_progress`): done parts count whole, a started part counts `pos / len`. The
  current part is the most recently touched; if it is done, the next one not done. States are
  not started, in progress and finished.

Limits: 100 books, 300 parts per book, both silently cut.

A part counts as played within 30 s of its end (no 95 % rule), and a position is saved at any
length. Speed is per book, shared with the Podcasts speed records.

## The MP4 memory guard

FFmpeg's mov demuxer indexes every sample (28 bytes each) in RAM while a file is open. A long
single-file `.m4b` can exhaust the 128 MiB and stall the player, and Memory Playback would try the
same file again at boot, a boot loop. So the page asks before any play.

- `bk_mp4_index_kb(path)`: for `.m4b` / `.m4a` / `.mp4`, walks `moov/trak/mdia/minf/stbl` and sums
  the `stsz` / `stz2` sample counts times 28 bytes. A file that cannot be opened, is empty or 2 GiB
  or more, or has malformed or truncated boxes (or more than 4000 headers) is `BK_MP4_BAD`.
- `bk_mp4_fits(path)`: non-MP4 passes (a long streamed mp3 indexes nothing and is exempt). Else the
  index plus 16 MiB spare must fit in `MemAvailable`. **Everything unknown is refused**, including
  a missing `/proc/meminfo`: the guard is the safety net, so it fails closed.
- Before anything starts, the first part must be on the card and `bk_mp4_fits` is asked of
  **every part of the queue**. Any refusal starts nothing, marks nothing (Play Again keeps its
  marks) and toasts `Too long. Split it into parts.` Refusing an oversized part covers later parts
  too: the player would stall when it went on to part 2, and Memory Playback would retry at boot.
  A refused queue is never loaded, so Memory Playback never holds it. A first part missing from the
  card toasts `Storage unavailable`.
- The page is the only gate: stock's folder listing and library scan do not accept `.m4b`, so a
  single-file book reaches the player only through this page. A too-long `.m4a` played from stock
  Folders is stock's own behaviour, unchanged.

The 28 bytes and 16 MiB are borrowed from q2-pod's `chapters.c` (MIT, DiamondBond); the syscall
I/O, refusal of malformed input and fail-closed estimate are ours.

## The page

**Item:** Audiobooks is menu item 24 (`ACT_BOOKS` 144), hidden by default, on Extras in the
Library group after Podcasts. `books_open()` opens `m1plus_books` and does nothing when the kill
switch `/mnt/mmc/m1plus-off` exists. The asset is the Podcasts page's structure: one content view
painted in `EVT_AFTER_PAINT`, the plain navbar, hidden label styles.

Levels switch in place; Back goes up a level, and the Library returns at its offset.

- **Library:** large title, **Continue Listening** shelf (the in-progress book touched most
  recently; a tap resumes it), header **Books** and one row per book (cover, title, progress line),
  then the header **Discover** and the **LibriVox** row. Past 20 books a **See All (N)** row opens
  the complete list. With no book the Discover header and LibriVox row stay (the only way to get
  one), unlike Podcasts, which hides its rows. The navbar's small title appears when the large one
  scrolls away. The shelf is absent when nothing is in progress; the Books header when there is no
  book. The See All page has no large title, shelf or LibriVox row (navbar title `Audiobooks`) and
  Back returns to the Library at its offset. A book that leaves the card sends the page back to the
  Library.
- **Book:** header (cover, title, grey line, white capsule **Play** / **Resume** / **Play Again**),
  then a row per part (the capsule is **Play** when not started, **Resume** with a place in the
  book, **Play Again** when every part is played). A played part is grey, the playing part has the album page's wave, and the
  line reads `Played`, `12m left`, or for a LibriVox part not yet landed its manifest time and size.
- **Wording:** `Part 14 of 41 · 33%`, `42%` for one file, `Finished`, `Not started · 12 parts`;
  downloads say `Downloading · Part 13 of 37` (`Waiting · ...` before a retry) and `12 of 37 parts
  downloaded`; the Library row of a downloading book has the ring and `Part 13 of 37`, `Waiting`
  while queued. Durations are
  Podcasts' (`19m`, `22m left`); a whole book reads `18h 28m`.
- **"..." sheet** (Book level): **Playback Speed** (cycles 1x / 1.25x / 1.5x / 2x, saved at once,
  applied to a part that plays; the only row of a book with no manifest), **Pause Download** / **Resume Download**, and **Delete Book** for
  books with a manifest.
- **Delete Book:** refused with `This book is playing` while the player is on a file of the book.
  Else the confirm `Delete this book and its files?`; a running download is paused and the 1 s tick deletes on the first tick after the
  thread lets go, so files are never removed under the writer. It unlinks only what the manifest
  names, plus its `.part` files and `cover.jpg` / `cover.png`, then the manifest, then `rmdir`. A
  folder with anything else in it stays. A failed unlink keeps the manifest and toasts `Storage
  unavailable`.

**Playing** (`bk_play`) queues the parts from the chosen one to the end, so Previous never goes
before the tapped part. Play starts part 1, Resume the part `bk_progress` found, a tapped part
starts there (a played part restarts), Play Again forgets every mark. The book's speed is applied
first. For a LibriVox book with parts to come, only the parts on the card are queued.

**The book's own art.** A book with no usable cover file shows the art of its first part: the
embedded picture, else a picture in that file's folder (a loose file: beside it). The cover cache's
worker builds it ([covercache](covercache.md)) into a cache file keyed `"\x01audiobooks/" + dir`
(the control byte keeps it apart from album keys), once. The cache file stays when the book's
files change; Clear Cover Cache rebuilds it. Delete Book leaves it.

`bk_art_cover(path)` (`patch/bkmodel.c`) gives the cover of the book an Audiobooks path is in: the
cover file, else the art cache file when it exists. The [Queue](queue.md) page uses it for the rows
and header of a part; it never starts the worker. Now Playing and the surfaces sharing its cover use it only
as a fallback, for a part stock has no picture of ([nowplaying](nowplaying.md)).
While a part plays, Now Playing hides the play mode button ([nowplaying](nowplaying.md)) and the More sheet's
first page is Display Mode and More, without the Look up and Add to playlist rows ([playmore](playmore.md)).

## LibriVox

Find a public-domain LibriVox book and download it. Once its parts are on the card it is an
ordinary book folder. The levels copy Podcasts' Discover and search levels.

- **LibriVox level:** large title, grey line `Public domain audiobooks`, the **Popular** list (rows
  with thumbnail, title and author). The navbar magnifier opens the search level. The popular list
  is held for the session and a re-entry makes no request. Statuses are Podcasts' words (`Loading…`,
  `No Wi-Fi`, `Set the date first`, `Certificates missing`, `Can't connect`, `Server error`,
  `No results`).
- **Search level:** the Podcasts search level (field `Search LibriVox`, keyboard up at once). The
  typed text is not kept (Podcasts keeps it); each visit starts empty. The clear button empties the
  level and stops what runs. Back returns to the LibriVox level at its offset. A new question drops a pending preview, and a
  preview opens only under the row it was asked for.
- **Preview:** the Book header with author and `37 parts · 786m · 380 MB`, a **Download** or
  **Open Book** capsule, and plain part rows. An item with no MP3 part is `Not available` for the
  session (dimmed, no chevron). A third grey line `12 of 37 parts downloaded` shows when the
  folder exists with parts missing. **Download** creates the folder, queues the parts and opens the
  Book level; a failure of the folder toasts its word and the preview stays; a book already
  downloading is queued behind with no toast. Back returns to the level it came from at its offset.
- **Book with parts missing:** a row for every part the manifest names, from the first moment. A
  tap on a part not on the card queues the download (when the book neither runs nor waits; a
  refusal toasts its word). Such a row shows the manifest's time and size, not dimmed. The play
  queue holds only files on the card; a file the manifest does not name is not listed while parts
  are missing.

### The catalog

Source is the Internet Archive's `librivoxaudio` collection (LibriVox's own API matches only a
title's start and has no ranking). No key, HTTPS only.

- **Popular / search:** `/advancedsearch.php`, 25 rows sorted by downloads. A search matches
  `title` or `creator`; the term is cleaned (`bn_clean_term`: Lucene operators become word breaks,
  a bare `AND` / `OR` / `NOT` is lower-cased, empty means Popular). A doc with no title or an unsafe
  identifier is skipped.
- **Thumbnail / cover:** `/services/img/<identifier>`, checked by `pc_cover_ok` before decoding.
- **Parts:** `/metadata/<identifier>/files` (110 KB or more) is streamed to a file and scanned
  object by object, never held whole. Only `"format":"64Kbps MP3"` objects count. The first 300
  parts in natural order survive. Cut JSON is a failed answer; an item with no such object is
  `PN_NOBOOK`.

The catalog and preview jobs use Podcasts' one worker slot ([podcasts](podcasts.md), [network](network.md)),
never beside a refresh. Only the 64 kbit/s MP3 is taken, and nothing checks that a download is MP3
beyond refusing a text answer.

### On the card

Download makes `Audiobooks/<title>/`. The title goes through `bd_fat` (FAT-unsafe characters become
spaces, cut at 72 bytes), then ` (2)` .. ` (99)` while the name is taken by another book. A folder
whose manifest names the identifier is reused whatever it is called.

- **`.librivox`** is the manifest: a dot file written last and atomically, so a folder with one is
  whole. Line 1 `M1PLUS-LIBRIVOX 1`, then `i=`, `t=`, `a=`, then one line a part with five tab
  separated fields (local name, seconds, bytes, archive name, title). `bd_open` refuses anything
  malformed or unsafe (bad magic or id, a name with `/`, `\`, a control byte or a leading dot, a
  duplicate local file, over 300 parts, over 128 KiB). The folder name stays the title; `t=` is not
  used.
- **Part files** are `NNN <title>.mp3`, padded to the part count, numbered in the natural order of
  the archive's file names so `bk_natcmp` keeps the reading order. A part is written as `.part` and
  renamed when whole, so a part on the card is complete.

### The download queue

The episode download policy (`pnw_download`: Range resume, 512 KB chunks, 32 MB free margin, retries
after 10, 20 and 40 s, 2 GiB cap, text answers refused) is Podcasts' ([podcasts](podcasts.md),
[network](network.md)). What is book-specific:

- `bd_start(dir)` queues a book's missing parts; one thread fetches **one book at a time, in the
  order asked**, parts in manifest order, and takes the next waiting book itself. A book stops at
  the first part that does not come; parts already fetched stay.
- **Capacity:** the running book and 16 waiting (`BD_QMAX`); the next is `Queue is full`. A book
  already running or waiting is not added twice.
- **`bd_pause(key)`** stops the running book (the `.part` stays) and the thread goes on with the
  next; a waiting book leaves the queue. A failure every book would meet (no Wi-Fi, certificate,
  storage, card full, memory) stops the queue and the waiting books are paused. A book's own
  failure (a part gone, HTTP error, path too long) is recorded and the queue goes on.
- The thread has its own slot: it is outside the job slot and the episode queue, runs beside both
  and gives way to neither. The page cancels only its own jobs (`pn_cancel(PN_K_BOOKS)`).
- Every queue move is one hold of `bq.mutex`, as the episode queue's. Nothing runs after a reboot:
  the manifest and files are the state.
- **Rows and header** show a download as Podcasts' In Progress rows do (the shared ring, `45%`,
  `Waiting`, `Failed: <why>`), and the header capsule is `Pause`, `Retry` or `Resume` for a book
  with no part yet.
- **Download marks** (the words of Podcasts' In Progress rows):

  | State | Part row | Header |
  |---|---|---|
  | running | the part being fetched has the ring and `45%` (`12 MB` when the length is unknown) | no part on the card: totals and capsule `Pause`; else Play and `Downloading · Part 13 of 37` |
  | sleeping before a retry | ring with the arrow, `Waiting` | capsule `Pause`; `Waiting · Part 13 of 37` |
  | last try failed | first missing part says `Failed: <why>` | capsule `Retry`; else `Failed: <why>` |
  | waiting in the queue | manifest time and size | capsule `Pause`; else `Waiting · 12 of 37 parts downloaded` |
  | paused, or started before a reboot | manifest time and size | capsule `Resume`; else `12 of 37 parts downloaded` |

  The capsule of a book with no part on the card is the download's button; it becomes Play with the
  first part. Failure words: `No Wi-Fi`, `Set the date first`, `Certificates missing`,
  `Certificate problem`, `Can't connect`, `Server error` (gone, HTTP, not a feed, not audio),
  `Storage unavailable` (also card full), `Not available`, `Queue is full`, else `Not enough memory`.
- **Keep-awake:** a 1 s page timer resets stock's standby countdowns while a book downloads. With
  the Audiobooks and Podcasts pages closed nothing does, so the device may standby and the download
  ends with a network error; a tap on a missing part continues from the `.part`.

## Limits

- 100 books, 300 parts, 2 MiB files answer, 128 KiB manifest, 240-byte download path.
- One transfer at a time (16 waiting); searches, previews and Podcasts jobs run beside it and
  share the card and link.
- Delete Book is for LibriVox downloads; delete a copied folder from a computer.
- No language filter, book description, streaming without a download, simultaneous downloads,
  Settings switch for the LibriVox row, or automatic resume after a reboot.
- The popular list is the only chart (no Shows | Episodes control).
