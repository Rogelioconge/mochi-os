# Audiobooks: the book model and the page

Two layers. The **model** (`patch/bkmodel.c`) answers four questions about `/mnt/mmc/Audiobooks`: which books are there, what are their parts and in which order, how far
along is each book, and may the player open this file at all (the MP4 memory guard). The **page** (`patch/bkpage.c`, "The page" below) is the Extras item Audiobooks that
shows them. Podcasts' resume ring is the only state of reading: a part is keyed like a podcast episode, so no new file is written. A third layer, "LibriVox" below, finds and downloads
public-domain books from the Internet Archive into the same folder.

Sources: `patch/bkmodel.c`, `patch/books.h` (API, the model's numbers and the page's geometry, which the tests parse); `patch/bkpage.c`, `patch/bkpage.h` (the page: window, Library and Book levels),
`patch/bkfind.c` (the LibriVox and Preview levels), `patch/bknet.c` (the LibriVox catalog), `patch/bkdl.c` (the LibriVox manifest, folder and download job); one function at the end of
`patch/pcmodel.c`, `pc_recent_rank` (declared at the end of `patch/podcasts.h`); `tools/pod_books.py` (the page's layout model in Python, parsing `books.h`), `tools/pod_ui.py`
`build_books_page` (the asset), `tools/preview/preview_books.py`. Tests: `test/pod/bkmodel.py`, `test/pod/bkpage.py`, `test/pod/bknet.py`, `test/pod/bkdl.py`, `test/pod/bkfind.py`. `tools/pod.py` compiles them and keeps three model helpers
(`bk_natcmp`, `bk_mp4_index_kb`, `bk_parse_meminfo`) with `--undefined=` for the model test: the page reaches them through `bk_load_parts` and `bk_mp4_fits`. No libc import was
added: it uses `opendir / readdir / closedir`, `__xstat`, `open / read / lseek / close`, which demo already imports and Podcasts already uses. No hook: the page is opened from a row.

## What a book is on the card

The folder is found as `pc_root` finds Podcasts: `/mnt/mmc/Audiobooks`, else any folder of `/mnt/mmc` named `audiobooks` in any case (`bk_root`).

- A **book** is a subfolder with at least one audio file directly in it or in one of its immediate subfolders (`CD1/`, `Disc 2/`). The parts are all those
  files merged. Deeper folders are not looked into. A subfolder without audio is not a book (so `Docs/` or an empty folder never shows).
- A subfolder holding a readable `.librivox` manifest is a book too, with 0 parts until the first one is on the card (`bm_manifest`: `access(R_OK)`); the title stays the folder name. A `.part` file is not
  audio (its extension is `part`), so it is never a part, and the manifest is a dot file.
- A **loose audio file** directly in `Audiobooks/` is a one-part book titled by its name without the extension. A folder named `x.mp3` is not looked into
  (an entry with an audio extension is taken for a file).
- Audio extensions are Podcasts' list: `mp3 m4a m4b aac ogg opus flac wav wma`, any case.
- Dot files and dot folders are skipped at every level (macOS `._x.mp3`, `.DS_Store`, `.Trashes`). So are names of 128 bytes or more, names with a control
  byte, and parts whose path inside the book is 192 bytes or more.
- The **cover** is `cover.jpg / cover.png / cover.jpeg / folder.jpg / folder.png / folder.jpeg` directly in the book folder, in that order of preference,
  any case; `""` for none. A loose file has none.
- The **title** of a folder book is the folder name; the books are sorted by title, ASCII case-insensitive with a leading "The " aside (`cc_name_cmp`, the
  Shows page's order), then by folder name.
- Limits: `BK_MAX_BOOKS` 100 books (the card's own order decides which survive on a bigger card), `BK_MAX_PARTS` 300 parts loaded (`bk_book_t.parts` still
  counts them all, so a page can say a book is cut). Both sorts are insertion sorts in place: no scratch memory, no `.scratch` data.

## The key

`bk_book_t.hash = pc_hash("audiobooks/" + dir)`: `dir` is the folder name, or for a loose file its file name with the extension, as the card spells it;
`pc_hash` lower-cases ASCII, so the spelling of the root folder and of the case does not matter. The Podcasts side's `bk_book_of(path)` returns exactly this
for a path inside a book (the first component under the root, whether a folder or a loose file). The test checks the construction.

## The parts

`bk_load_parts` lists a book's audio files (path below the book folder in `rel`, title = file name without extension, size in KB rounded up, ring key
`pc_hash(full path)` exactly as Podcasts keys an episode) and sorts them by **`bk_natcmp(rel)`**: ASCII case-insensitive, digit runs compared by value
(leading zeros dropped, then the longer run is larger, then the digits, so there is no overflow however long the run), `/` sorts before every other
character (a folder's files stay together). So `Part 2 < Part 10`, `CD1/10.mp3 < CD2/01.mp3`, `CD1 < CD1/a`. Two different paths are never equal: a plain
compare breaks the ties (`file01` vs `file1`, `a` vs `A`). A loose book has one part, `rel` = the file name. `bk_part_path` gives the full path
(`root/dir/rel`, or `root/dir` for a loose file).

## Progress

`bk_progress(parts, n, &permille, &current)` reads the ring through `pc_state` and `pc_recent_rank` (the slot's place in the ring: 0 most recently touched).

- **Bytes**: a part `PC_DONE` counts whole, a part `PC_PROGRESS` counts `pos / len` of its size, `PC_NEW` nothing. A part with no size weighs one unit. The
  sums are scaled to stay in 32 bits (a book up to terabytes), `pos` and `len` are clamped to 4 000 000 s, `pos <= len`.
- **Current part**: the touched part (not `PC_NEW`) with the smallest ring rank. If it is `PC_DONE`, the part after it, skipping parts that are done too; when that runs
  past the end (the last part was the one finished), the first part not done. Nothing touched: part 0 and `BK_NOT_STARTED`. Every part done: `BK_FINISHED`,
  1000 permille, `current = n`. Otherwise `BK_IN_PROGRESS`.
- No parts: `BK_NOT_STARTED`. A slot with no place and no mark is `PC_NEW` and is not a touch.

## The MP4 memory guard

FFmpeg's mov demuxer indexes every sample: an `AVIndexEntry` (24 bytes) and the `stsz` entry (4 bytes), 28 bytes per sample, held in RAM while the file is open.
A long single-file `.m4b` (tens of millions of samples at low bitrates, or an AAC-LC book of many hours) can exhaust the 128 MiB RAM and stall the player, and
Memory Playback would try the same file again at boot, a boot-loop risk, so the page must ask before any play.

- `bk_mp4_index_kb(path)`: 0 for a name not ending `.m4b / .m4a / .mp4` (any case; the extension is the last component's); otherwise the walk of
  `moov / trak / mdia / minf / stbl` (every track) summing the `stsz` / `stz2` sample counts, times `BK_MP4_SAMPLE_BYTES` (28), in KB rounded up. Boxes are
  read with `lseek` + `read` of 8 or 16 bytes at a time (64-bit sizes and size 0 = to the end are understood). **`BK_MP4_BAD`** (0xffffffff) when the file
  cannot be opened (a file of 2 GB or more fails `open` without `O_LARGEFILE`: EOVERFLOW), is empty or 2 GB or more, has a box smaller than its header, larger
  than its parent or the file (truncated), a 64-bit size with high bits, an `stsz` shorter than its 12 bytes, no sample table at all, or more than
  `BK_MP4_MAX_READS` (4000) headers (a file full of tiny boxes). No offset is read past the file: every read is a checked `lseek` + full-length `read`.
  Fewer than 8 trailing bytes after a box are ignored, as the demuxer does.
- `bk_parse_meminfo(text)`: the number of the `MemAvailable:` line in KB, 0 when the line or the number is missing or absurd.
- `bk_mp4_fits(path)`: 1 for a name that is not an MP4; otherwise the index in KB plus `BK_MP4_SPARE_KB` (16 MiB: the decoder's buffers, the UI, the page cache) must be
  at most MemAvailable. **Everything unknown is refused**: `BK_MP4_BAD`, no `/proc/meminfo`, no `MemAvailable` line. (q2-pod lets a missing estimate play as
  stock does; here the guard is the safety net, so it fails closed. Linux 5.10 always has the line.)

Borrowed from q2-pod's `patch/chapters.c` (`mp4_samples`, `mp4_index_bytes`, `mp4_fits`; MIT, DiamondBond), whose attribution is kept in the file header; the
differences are the syscall-level I/O, the refusal of malformed input (q2-pod stops walking and counts what it saw), the read budget and the fail-closed estimate.
The 28 bytes a sample and 16 MiB are q2-pod's numbers and are not yet measured on the device (`BK_MP4_*` in `books.h`, tune there).

Not guarded here: other tables the demuxer keeps (`stco`, `stsc`, `stts`) are small next to the 28 bytes a sample; a non-MP4 container (a long `.mp3` is streamed
and indexes nothing) is not looked at.

## Tests

`make test TEST=bkmodel`: discovery (folders, subfolders, loose files, dot files, case-insensitive root, long names, the 100-book cap), natural-order edge cases
and a shuffled sort, parts (order, titles, sizes, keys, paths, the 300-part cap), progress against rings written by hand and the live ring (`pc_mark`), and the MP4
guard on synthetic byte strings (small, huge, stz2, two tracks, 64-bit and zero sizes, every refusal above, every truncation of a valid file, random
corruption, the exact MemAvailable boundary, the meminfo parser).

## The page

**The item.** Audiobooks is menu item 24 (`ACT_BOOKS` 144, saved as `p`, `pod_ic_audiobooks`, the Lucide book-headphones glyph): hidden from the menu by default, on Extras in the Library
group right after Podcasts; `MENU_FILE_MAX` is 28 (25 item characters, the `-`, a newline and the NUL). A tap calls `books_open()`: `window_open("m1plus_books")`. It returns -1 and opens
nothing when the kill switch `/mnt/mmc/m1plus-off` exists (the menu is not reachable then either), when the page is up already, when the window will not open, or when the asset has
lost a widget (it goes back). The page is the last of `PAGES` (`BOOKS`, kind `books`); `tools/pod_i18n.py` has its ten keys in all 13 languages.

**The asset** (`build_books_page`) is the Podcasts page's structure: the plain navbar (Back, title, Now Playing as the disc), `list_view > scroll_view` + `scroll_bar_m` holding ONE
content view, `view_grid`, which the payload paints in its `EVT_AFTER_PAINT` (no widget per row); `bk_big` is the large heading of the Library and of the LibriVox level (its text is set per level) (the Podcasts pages' size, a child of the
content, so it scrolls with it); `label_status` is the empty hint; the hidden labels are the text styles (`label_row_title` / `label_row_sub` of the rows, and `BK_STYLES`: the header's
title, its grey line, the capsule's word on its own white, the title of a played part). The navbar has the Discover level's magnifier `btn_search` (hidden; `pod_ui.discover_find`, shared with the Podcasts page; `bk_nav` shows it on the LibriVox level, where Now Playing is the capsule's right cap and the small title ends before it) and the Podcasts Show page's `btn_more` (hidden; the payload shows it on the Book level and makes Now Playing the capsule's right cap) and the asset holds the Podcasts sheets' widget set `bk_sh_*` (`sheet_widgets`, hidden). New UI is neutral white and grey; there is no accent colour.

**Five levels**, switched in place (Back goes up a level before it leaves the page; the Library comes back at the offset it was at, its covers kept while the books are the same; the LibriVox, search and Preview levels are "LibriVox" below, `patch/bkfind.c`). The first two:

- **Library** (the Podcasts Shows level's order, `bk_lib_layout`, `tools/pod_books.py library()`): the large heading; **Continue Listening** (`bk.cont`: the in-progress book whose latest part has the smallest place in the ring, `bst.rank`; the shelf with one item as Podcasts draws it: header at `PP_HEAD_X`, a `PP_SHELF_ART` cover with the play disc from `pc_atlas`, the title cut to `PP_SHELF_W`, the percent where Podcasts has "35m left"; a tap resumes the book (`bk_cont_play`) and the page stays on the Library; absent when nothing is in progress); the header **Books** (the Shows header's: `BS_SECH` at `PP_SHOWS_X`, `PP_HEAD_PITCH` over the first row; none while there is no book, as Podcasts has no Shows header with no show) and the books as a list, one row each, from `BK_TOP` (60) or under the shelf; then `PP_SEC_GAP`, the header **Discover** and the **LibriVox row** (the Discover row's look: `PP_DL_*` tile, the title `LibriVox`, the grey line `Public domain audiobooks`, chevron, hairline). The rows are `grid_list_paint`'s (cover `LIST_ART`, text at x 74 ending at 278, hairline 74..310, chevron x 288); a book that downloads has the ring before its grey line (`grid_tile_t.subx`). With more than `PS_SHOW_MAX` (20) books the first 20 (the model's title order) are shown and a **See All (N)** row (`PS_MORE_H`, the Show page's, its text at `PP_SHOWS_X` under the header and the covers) follows them, PP_SEC_GAP, the Discover header and the LibriVox row right after it; it opens the complete list from the top (`bk.all`: the title `Audiobooks` in the navbar, no large heading, no shelf, no LibriVox row). Back from it returns to the Library at the offset it was left at; a book opened from it returns to it at its offset (`bk.all_off`). No book: the Discover header and the LibriVox row stay (the only way to find a book; Podcasts hides every row with no show, a deliberate difference) and the hint (`grid_hint_paint`, centred in the room under the row) follows.
  **The small title.** The navbar shows `Audiobooks` once the large title has scrolled away (`bk_gone`: `m1_title_gone(off, 0)`, `SG_COLLAPSE`, as Podcasts' `pg_collapse`); the See All page always has it. Every level change that keeps an offset (Back from a book, the See All page, LibriVox, the search level, a preview) calls `bk_level_title` after the offset is set, so the title is right at once, not after the next scroll event.
  **One wording** (`bk_prog`, `bk_dl_text`, `pc_left_text` / `pc_len_text`; model `lib_sub`, `dl_head`, `len_text`): reading progress `Part 14 of 41 · 33%` (the part first), `42%` for one file, `Finished`, `Not started · 12 parts` (`Not started` for one); the Library row, the Book header and the shelf use it. Downloads: the header says `Downloading · Part 13 of 37` (`Waiting · ...` while the job sleeps before a retry), `12 of 37 parts downloaded`; the Library row of the book that downloads has the ring and `Part 13 of 37` (the row's text ends at 278, 184 px after the ring: "Downloading · Part 13 of 37" is 205 px and would be cut). Durations are Podcasts': `19m`, `22m left` (minutes rounded up). A whole book's length (the Preview and the no-part Book header) reads hours from 60 minutes in the same short style, `18h 28m`, `2h` on the hour (`bf_total_len`, `%dh` / `%dh %dm`); a part stays in minutes.
  The covers decode one per 16 ms tick (the shelf's first, then the rows in view and two either side; `pc_cover_ok` first), painting decodes nothing.
- **Book** (a tap on a row): the header, then a row per part in reading order, up to `BK_MAX_PARTS`. The header: the cover (`PS_ART` px, the Show page's), the title (22 px, centred, at
  most two lines wrapped as the Show page wraps its name), the grey line (`Part 3 of 12 · 42%`, `12 parts`, or the size for a file; `Finished`), then a **white capsule** with black text,
  alone and centred as the Show page's Latest Episode pill is (the page draws it). The capsule says **Play** (not started), **Resume** (a place in the book) or **Play Again** (every part played) (a stadium: each row inset by the circle's chord, the end pixel blended by its coverage; no atlas). The speed is a row of the "..." sheet (below), not a pill. A part row: the title (21 px, white; grey when played; the part the player is on right now has the album page's playing wave in the ring's slot before its grey line (same bitmap and colour rule, `grid_wave_make` / `grid_wave_draw` in `grid.c`, `bk.pl_row`, followed by the 1 s tick without reloading the list); the part to resume has no mark, its `22m left` and the Resume capsule say it) and a grey line:
  `Played`, `12m left` (the ring's pos and len) or, for a LibriVox part not played, what it said before it landed, the manifest's `19m · 9 MB` (a book of your own: its size, `45 MB`, `1.4 GB`). The Library rows mark no playing book (no list of the Albums, Artists or Podcasts pages does). The navbar shows the book's title once the header's has scrolled away. Geometry: `BK_*` in `books.h`.

**The "..." and its sheet** (`bk_nav`, `bk_sheet_open`, `bk_on_sheet_row`; the Podcasts sheets' widget set, `tools/pod_ui.py` `BK_SHEET_ROWS`): on the Book level of every book the navbar shows the Show page's "..." (the capsule's left cap on the 214 slot, Now Playing its
right cap, the small title ends before it; the Library, LibriVox and Preview levels have the disc). It opens a bottom sheet (`m1_sheet_rows`, the glass of its rows, a tap on the scrim or Back closes it):

| Row | When | A tap |
|---|---|---|
| `Playback Speed` + grey value (`m1_sheet_value`, the Show sheet's value placing, now shared) | every book | cycles `1× 1.25× 1.5× 2×`, the value follows, `pc_speed_set` under the book's key (saved at once) and `pc_speed_apply` (a part that plays takes it at once); the sheet stays |
| `Pause Download` | the book downloads or waits in the queue | `bd_pause(key)`; the sheet closes |
| `Resume Download` | parts are missing and the book neither runs nor waits (a failure too) | `bd_start(dir)` (it queues behind a running book); a refusal toasts its word |
| `Delete Book` (red as Unsubscribe is) | the book has a `.librivox` manifest | see below |

A book of your own (no manifest) has Playback Speed alone. **Delete Book** (`bk_delete_ask`, `bk_delete_run`): refused with the toast `This book is playing` while the player is on a file of the book (`cc_playing`, `bk_book_of`), before anything is asked; else the confirm `Delete this book and its files?`
(`pod_confirm`); then, when the book runs, `bd_pause(key)` and the page waits (a waiting book leaves the queue by the same call and nothing holds its files: they go at once; the queue goes on with the next book): the 1 s tick (`bk_tick`) runs the deletion on the first tick that finds `bd_active() != the book` (the thread clears `run` after its last touch of a file and its manifest copy), so nothing waits on the UI thread and the
files are never removed under the writer. Taps on the Book level do nothing meanwhile (Back works; the deletion then finishes behind the Library). The deletion unlinks each file the manifest names and its `.part`, `cover.jpg` and `cover.png` (the one the download copied from the preview), then the manifest
(`unlink`; each file's place in the ring is forgotten, `pc_mark`), then `rmdir` of the folder, which stays when anything else is in it (a file of yours, a part the manifest does not name): nothing is deleted recursively and nothing the manifest does not name. A part that is still there afterwards (an `unlink` that failed)
keeps the manifest and toasts `Storage unavailable`. The Library is read again. Only `unlink`, `rmdir` and `access`, which Podcasts' deletes already import.

**Playing.** `bk_play(from, again)` builds `stSongInfo` records of its own as Podcasts does (class 1, the book's title as album and artist, type 8; the queue handed to
`playing_page`, `pod_set_in_order`): **the parts from `from` to the end**, index 0 (so Previous does not go back before the part tapped). Play starts part 1; Resume starts the part
`bk_progress` found, and `pc_note` jumps to its place a moment after it starts; a tap on a part starts that part (a played part restarts: `pc_restart`; a part with a place keeps it);
Play Again forgets every part's mark and place (`pc_mark(hash, 0)`) and starts part 1. The book's speed is applied first (`pc_speed_apply(book hash)`).
Playing from a LibriVox book with parts to come queues the parts that are on the card, in order (`bk.parts`); a part that is not there is not in the queue.

**The memory guard comes first.** Before anything starts, the first part must be on the card (else `Storage unavailable`), and `bk_mp4_fits` is asked of **every part of the queue**: if any
refuses (an index too big for MemAvailable, a malformed MP4, no `/proc/meminfo`) nothing starts, nothing is marked or restarted (Play Again keeps the marks), and the toast says `Too long.
Split it into parts.` (the stock message box). So the refusal covers the next parts too: a book whose part 2 is too big
cannot be started from part 1 either, because the player would stall when it went on to part 2, and Memory Playback would try it again at boot. Non-MP4 parts need no estimate.
**Why the page is the only gate:** stock's folder listing (`toolsLoadDirectory`) and library scan do not accept `.m4b`, so a single-file book reaches the player only through this page;
a queue the page refused is never loaded, so Memory Playback never holds it. A too-long `.m4a` played from stock Folders is stock's own behaviour, unchanged.

**State.** The Library's progress is read when the page opens, comes back in front, or the Back key returns to it, and again for the book the player is on whenever the ring moved (the
1 s tick calls `pc_note(cc_playing())`, like the other pages that look at the playing track). The Book level reads the ring again on each tick that moved it and when it is back in
front; a book that has gone from the card sends the page to the Library. Behind another page both timers go; destroy frees the lists and the tiles.

**Tests** (`make test TEST=bkpage`): the asset and the item (id, character, group, the saved list, the row on the menu and Extras, the icon), the Library (rows, the three states, the empty
hints, the covers, touches and the lit row), the Book level (every text against `tools/pod_books.py`, the capsule's three words, the part to resume, Back, a long title, the small navbar
title), Play / Resume / Play Again / a tapped part (queue contents, start index, marks and places, the speed), the guard (a huge MP4 in a book: no start, the toast, the marks stay;
a small MP4 and an MP3 play; no `MemAvailable` refuses an MP4), the speed row of the "..." sheet (its value, each tap's cycle, saved and applied, the book that plays), the key the scan and the player's side agree on (a folder book and a loose
file), behind another page and back, and every text of the page in the 13 languages against its place. Preview: `uv run python -I tools/preview/preview_books.py WORKDIR out/preview`.

## LibriVox

Find a public-domain LibriVox book on the device and download it into `Audiobooks/`. Once its parts are on the card a LibriVox book is an ordinary book folder: the model, progress, resume, speed
and the memory guard above do not change. Sources: `patch/bknet.c` (catalog), `patch/bkdl.c` (names, manifest, folder, download job), `patch/bkfind.c` (the LibriVox and Preview levels),
`patch/bkpage.c` (the Library row's line, the Book level's rows, header, "..." sheet and Delete Book, the tick, keep-awake), `patch/bkpage.h` (the page's state, shared with `bkfind.c`), `patch/pcnetw.h` and `patch/pcnet.c`
(the worker slot and the download policy shared with Podcasts), `patch/pcjson.c` (`pj_object`, `pj_records`). Python: `tools/pod_books.py` (words and layout), `tools/preview/preview_books.py`.
No hook, no menu item: the page opens from the Library's LibriVox row.

### The catalog

The catalog is the Internet Archive's `librivoxaudio` collection, where every LibriVox recording is hosted. (LibriVox's own API matches only the start of a title and has no ranking.) No key. HTTPS only,
host `BN_HOST` = `https://archive.org`:

- **Popular / search**: `/advancedsearch.php?q=<q>&fl[]=identifier&fl[]=title&fl[]=creator&fl[]=runtime&sort[]=downloads+desc&rows=25&output=json`. Popular is `q=collection:librivoxaudio`; a search is
  `collection:librivoxaudio AND (title:(<term>) OR creator:(<term>))` with the whole query percent-encoded. `bn_clean_term`: UTF-8 kept, control bytes and Lucene's `+ - & | ! ( ) { } [ ] ^ " ~ * ? : \ /`
  become a word break, breaks collapsed, a word that is exactly `AND`, `OR` or `NOT` lower-cased, bytes that are not UTF-8 dropped, cut at `BN_TERM` - 1 on a character boundary; nothing left means Popular.
  The answer `response.docs[]` of `{identifier, title, creator, runtime "10:17:59"}` (`creator` a string, an array or missing) is parsed by `bn_parse_docs`: a doc with no title, or an identifier
  that is not `[A-Za-z0-9._-]` (shorter than `BN_ID` 80, not `.` / `..`) or was altered by decoding, is skipped, never cut.
- **Thumbnail and cover**: `/services/img/<identifier>` (a 180 x 180 JPEG, about 20 KB), cap `PN_THUMB_CAP`, checked by `pc_pic_info` / `pc_cover_ok` before it is decoded.
- **Parts**: `/metadata/<identifier>/files`: `{"result":[{...}, ...]}`, one flat object per file in every format (110 KB for 37 parts, 160 KB and more for a long book). It is fetched to
  `BN_DIR/files.json` and scanned by `bn_scan_files` in 4 KB chunks, object by object, never held whole: only objects with `"format":"64Kbps MP3"` count (`name`, `title`, `length` as `18:52` or seconds,
  `size`), kept sorted by `bk_natcmp(name)` so the first `BK_MAX_PARTS` (300) in natural order survive whatever the order of the file (`*more` says some were left out). An object over `BN_OBJ` (4096) bytes,
  a name with `/`, a control byte, over 127 bytes or altered by decoding is skipped; reading stops at `BN_FILES_CAP` (2 MiB). Malformed or cut JSON: the parts whole before the break, `*complete` 0,
  and the job takes that for a failed answer (`PN_NOTFEED`). An item with no such object is `PN_NOBOOK` (the collection also holds a few bundles). A part's address is
  `/download/<identifier>/<name>` (percent-encoded by `m1_urlenc`; it redirects to a data node, 16 hops).

The jobs run in `pcnet.c`'s one worker slot (`patch/pcnetw.h`: `pnw_spawn`, `pnw_end`, `pnw_json`, `pnw_file`), never beside a refresh or each other (the book download and the Podcasts episode downloads have threads of their own). Catalog job: `bn_catalog(term)`,
state `BN_S_*`, `bn_gen()` moving with every answer, picture and end, `bn_row(i)`, `bn_thumb(i, ...)` (pictures `BN_DIR/p<i>` popular, `s<i>` search; rows are heap records made on first use). The popular list
is held for the session: asked again it starts no worker, asks no guard and is answered even while a job runs; a held list whose pictures were not all tried fetches only those. A search drops the old
search rows and pictures and replaces the search result only. Preview job: `bn_preview(id)` fetches the files answer, scans it into a heap list (70 KB) and fetches the picture to
`BN_DIR/preview.jpg|png` (a missing picture is no failure); the parts stay until the next preview or `bn_preview_drop()`. `bn_catalog_clean()` removes the pictures and forgets the search (the page's close).
Codes (`pcnet.h`): `PN_OK`, `PN_NOBOOK`, `PN_NOTFEED` (cut or over 2 MiB), `PN_NET`, `PN_HTTP`, `PN_GONE` (404, 410), `PN_CERT`, `PN_NOWIFI`, `PN_NOCLOCK`, `PN_NOCERT`, `PN_STORAGE`, `PN_MEM`, `PN_BUSY`, `PN_CANCELLED`.

### On the card

Download makes `Audiobooks/<title>/`: the title through `bd_fat` (`\ / : * ? " < > |` and control bytes become spaces, bytes that are not UTF-8 dropped, spaces collapsed, no leading or trailing space or
dot, cut at `BD_BASE_MAX` 72 bytes on a character boundary; `Audiobook` when nothing is left), then ` (2)` ... ` (99)` while the name exists on the card and is not this identifier's. A folder that already
names the identifier (`bd_find`: the first 1024 bytes of the manifests of at most `BK_MAX_BOOKS` folders) is reused as it is, whatever it is called. `cover.jpg|png` is a copy of the preview's picture.
**`.librivox`** is the manifest (a dot file, so the model never lists it), written last and atomically (`m1_save`), so a folder with a manifest is whole: the first line `M1PLUS-LIBRIVOX 1`, `i=<identifier>`,
`t=<title>`, `a=<author>`, then one line a part of five tab-separated fields: local file name, seconds, bytes, the archive's file name, the title (tabs and line feeds in a field become spaces).
`bd_open(dir)` (a heap record of about 108 KB, `bd_free`) reads it and refuses a missing file, one of `BD_MAN_CAP` (128 KiB) or more, a first line that is not the magic, an `i=` that fails
`bn_id_ok`, a part line without exactly five fields, a number that is not digits or over 2^32 - 1, an empty, over-long or unsafe file name (`/`, `\`, control byte, `.` or `..`, a local name
starting with a dot), the same local file twice, more than `BK_MAX_PARTS` parts, a text line that is no `key=value`; unknown keys and CR before LF are ignored. `bd_present`, `bd_counts` (present,
missing, bytes of the missing) read the card. The model lists a folder with a readable manifest and no audio yet as a book of 0 parts (`bm_manifest`, `access(R_OK)`); the title stays the folder name
(the manifest's `t=` is not used).

**Local names and reading order.** A part file is `NNN <title>.mp3`, `NNN` zero-padded to 1, 2 or 3 digits by the part count (under 10, under 100, else), the title through `bd_fat`, the archive name's stem
when the title is empty, `Part N` when that too; a title that starts with the part's own number (`001 - Marseilles`) loses it; cut so the name is under `BK_FILE` bytes and `<root>/<folder>/<name>.part` is
within `PN_DL_PATH_MAX` (240). The parts are numbered in the natural order of the archive's file names (checked against the track numbers of eight real books, 2026-11-13), and the local names keep that
order under `bk_natcmp` whatever the titles are (9 to 300 parts, seven kinds of titles). A part is written as `<name>.part` and renamed when whole, so a part on the card is complete.

### The download job: a queue

`bd_start(dir)` queues the missing parts of one book; the thread fetches the books **one at a time, in the order they were asked**, each book's missing parts in manifest order through `pnw_download(pnw_dl_t, url, path, expect)`, the one download policy that `pcnet.c` shares with the Podcasts queue
(`pn_dl_core`: guards, Range resume of a `.part`, 512 KB chunks, the 32 MB free-space margin before the file and before every chunk, the stall limit, retries after 10, 20 and 40 s, text answers refused as
`PN_NOTAUDIO`, the 2 GiB cap, rename on completion). A book stops at the first part that does not come (nothing is skipped; parts fetched before stay) and the thread takes the next waiting book by itself (`bd_next`); it does not need the page, and no page tick starts anything. The thread ends when nothing waits.

- **States** (`bd_state(key)`): `BD_S_RUN` (the book being fetched, `bd_active()`), `BD_S_WAIT` (in the queue), `BD_S_NONE`. Results (`bd_result`): `DONE`, `PAUSED`, `FAILED` with the `PN_*` code; a book that leaves the queue unfetched is `PAUSED`.
- **Capacity**: the running book and `BD_QMAX` = 16 waiting behind it; a seventeenth is `PN_QFULL` (`Queue is full`). A book that runs or waits already is not added twice (OK, no thread, nothing moves); one whose pause is pending is queued again behind the others.
- **`bd_start`** returns 0 (the thread runs, the book runs or waits, or nothing was missing: result DONE, no thread), `PN_QFULL`, `PN_NOBOOK` (no readable manifest), `PN_MEM`, else the guard's `PN_NOWIFI`, `PN_NOCLOCK`, `PN_NOCERT`, `PN_STORAGE` (a book already in the queue is answered OK whatever the guard says). `bd_create(id, title, author, dir, size)` (from the held preview) needs no network and no thread.
- **`bd_pause(key)`** is per book: the running book's stop flag is set (the transfer ends at once with `PN_CANCELLED`, the `.part` stays, result `PAUSED`) and the thread goes on with the next; a waiting book leaves the queue (`PAUSED`).
- **Failures**: a book's own failure (a part the archive no longer has, `PN_GONE`, `PN_HTTP`, `PN_NOTAUDIO`, a path too long) is recorded and the queue goes on. A failure every book would meet (`PN_NOWIFI`, `PN_NOCLOCK`, `PN_NOCERT`, `PN_CERT`, `PN_NET` after the retries, `PN_STORAGE`, `PN_CARDFULL`, `PN_MEM`) stops the queue: the waiting books leave it as `PAUSED`, not as a row of identical failures.
- **Locking**: every move of the queue and of the running book's identity (enter, leave, claim, end, the thread ending) is one hold of `bq.mutex` (the UI thread's `bd_start` / `bd_pause` / `bd_state`, the thread's claim and end), the pattern of the episode queue's `pn_dmutex`. The thread decides that nothing waits and clears `run` in the same hold in which `bd_start` looks, so a book queued as the thread ends starts a new one. The next manifest is read off the mutex and taken only if it is still the head; the book record is the thread's own (freed by it before the next claim), the page never sees it. No file is touched under the mutex.
- State read by pages (UI thread): `bd_active()` (the running book's key, 0 for none, also in the moment between two books), `bd_progress(&part, &parts, &got, &total, &wait)`, `bd_gen()` (moves with every progress step, part, wait, queue change, start and end; only grows), `bd_result`, `bd_state`. After a reboot nothing runs and no result exists: the manifest and the files are the state.

**A book download is a thread of its own.** `bd_start` makes the thread itself (`pn_guard`, `net_init`, `pthread_create`, detached, `bd_main`); it does not take the job slot of `pcnet.c` and is not in the Podcasts episode queue, so `pn_job_busy()`, `pn_busy()`, `pn_dl_running()` and `pn_dl_waiting()` do not see it. It runs beside a
catalog search, a preview, a Podcasts job and the episode queue's thread, and nothing gives way to anything. `pn_cancel()` never reaches it; the page cancels only its own jobs, `pn_cancel(PN_K_BOOKS)`.

### The levels

All inside `m1plus_books`, switched in place; Back goes up a level.

- **Library**: see "The page". A book whose manifest names more parts than are on the card has the line `Part 13 of 37` after the ring while the job runs on it, else `12 of 37 parts downloaded`.
  The manifest's part count is `bk_man_total`: the tabs of the file counted in a stream (four a part), read when the Library is loaded and not per paint, 0 when they do not add up. The Library is
  loaded again when a part came or a job began or ended, the lines only follow the other generation steps.
- **LibriVox** (`BL_LV`, `bkfind.c`), the Podcasts Discover level's look: the large title `LibriVox` (`bk_big`, which collapses into the navbar's small title at `SG_COLLAPSE`), under it the grey line `Public domain audiobooks` (`BS_META` at `PP_LINE_X`, `PP_LINE_Y`: the Shows level's refresh line), the section header `Popular` at `BK_LV_POP_Y` (the Library's `Books` header: `BS_SECH` at `PP_SHOWS_X`, `PP_HEAD_PITCH` over the rows) and the rows from `BK_LV_POP_TOP`, each a thumbnail (decoded one per 16 ms tick, `pc_cover_ok` first), title, author in grey, chevron. No field here. The navbar's **magnifier** (`btn_search`, the Podcasts Discover level's widget made by `pod_ui.discover_find`: the capsule's left cap beside Now Playing, `bk_nav`) is on this level only and opens the search level. Entering starts at the top with Popular (the held list needs no request). Status line (20 px, centred as a block in the room under the grey line by `grid_hint_paint`, the spinner before it while a job runs): `Loading…`, `No Wi-Fi`, `Set the date first`, `Certificates missing`, `Certificate problem`, `Can't connect`, `Server error` (`PN_HTTP`, `PN_GONE`,
  `PN_NOTFEED`, `PN_NOTAUDIO`), `Storage unavailable`, `No results`. A search or a preview runs at once beside a book download or an episode download. `bf_pump` cancels the page's own running job
  (`pn_cancel(PN_K_BOOKS)`) and waits for another page's job to end. Leaving cancels the page's own job and drops the preview; the page closing calls `bn_catalog_clean` when no worker runs. Back returns to the Library at its offset.
- **Search** (`BL_SRCH`, `bkfind.c`), the Podcasts search level's: no large title (the navbar's `LibriVox` is always shown), no magnifier, the field at `PQ_FIELD_Y` (`ps_field`, hint `Search LibriVox`, the keyboard page on a tap), the rows of the typed term from `PQ_TOP`, right under the field (no label line), the same status line under the field. The magnifier opens it with an empty field and **the keyboard on it at once** (`bf_search`, as Podcasts opens the keyboard on entering with nothing typed); it does nothing while a row's parts are being fetched. An empty field shows no rows and no status; the typed term is searched (`bf_done`, `bf_fg`); the clear button empties the level again (no request, what runs is stopped) and opens the keyboard. A new question (a search, the clear button, entering the level) lets go of a preview that was asked for: the row is no longer chosen, a held answer is dropped (one still being fetched once its worker ended, in `bf_sync`), and `bf_open_pre` opens an answer only for the row whose identifier it carries, so a preview never opens under another row's title (`bkfind.py/preview_tests`). Back (`bf_search_close`) returns to the LibriVox level at the offset it was left at (`bf.disc_off`) with Popular from the held list; the typed text is not kept (Podcasts keeps it and searches it again when the level is entered: left out, the field is empty on every visit).
- **Preview** (`BL_PRE`; a tap on a row of the LibriVox or the search level; Back returns to the level it was opened from, at its offset: `bf.from`, `bf.lv_off`; pictures of its rows that opening the preview cut are fetched then with no new query, `bn_thumbs`, so the rows and the offset stay): the Book level's header with the author (`bk_header`), `37 parts · 786m · 380 MB` (`bf_line`: the pieces that are known; `%d parts` only above
  one), and, when `bd_find` finds the folder and parts are missing, a third grey line `12 of 37 parts downloaded` (`bd_open`, `bd_counts`; the header is one line taller), a white capsule alone, **Download** or **Open Book** when `bd_find` finds a folder, the parts as plain rows (title, `19m · 9 MB`, no chevron, no tap). A row of an item with no MP3 part is marked
  `Not available`, dimmed and without chevron for the session (`bf.dna`). Download: `bd_create`, `bd_start`, then the Book level of the folder (the preview is dropped); a failure of `bd_create` toasts its
  word and the preview stays; a refusal of `bd_start` toasts after the Book level opened (the book is on the card and resumable). A book that is already downloading is queued behind it with no toast.
- **Book** with a manifest and parts missing (`bk.mrows`, `bk_man_read`): **a row for every part the manifest names**, in its order, from the first moment (also with no file on the card), so the list the preview showed does not disappear. A part on the card is the row it is
  otherwise (playable, played and resume marks, its grey line); a part that is not is the same row with its title (the local file name without the extension, so the row does not change when the file lands) and the manifest's time and size (`19m · 9 MB`, `bf_line`),
  not dimmed (the Show page does not dim a remote episode either), and a tap on it queues the book's download when it neither runs nor waits (a refusal toasts its word), else does nothing. There is no row after the parts. The queue of Play and of a tapped part holds
  only the files on the card, in order. The files are matched to the manifest by name (`bk.mp`, a `bk_mrow_t` a part: title, seconds, bytes, place among the files); a file of the folder the manifest does not name is not listed while parts are missing. A book of your own (no manifest) is the plain list.

**The download in the rows and the header** (words of Podcasts' In Progress rows and pill):

| State | The part's row | The header |
|---|---|---|
| the job runs on this book | the part being fetched (`bd_progress`): the **shared ring** (`ls_marks_draw`, as Podcasts' In Progress rows: the 14 px ring before the grey line, the stop square, the arc is the percent of the part in 12 steps, step 0 while its size is unknown) and its grey line `45%` (`12 MB` once a whole MB came and the length is unknown, `Downloading` before that); the others keep their time and size | no part on the card: the manifest's totals (`37 parts · 786m · 380 MB`) and the capsule `Pause`; parts on the card: Play and the grey line `Downloading · Part 13 of 37` |
| it sleeps before a retry | the ring with the arrow (Podcasts' WAIT), the grey line `Waiting` | the capsule `Pause`; `Waiting · Part 13 of 37` |
| the last try failed (`BD_R_FAILED`) | the first part not on the card says `Failed: <why>` (no ring) | no part on the card: the capsule `Retry`; parts on the card: `Failed: <why>` |
| it waits in the queue | the manifest's time and size (no ring on a part) | no part on the card: the totals and the capsule `Pause`; parts on the card: Play and `Waiting · 12 of 37 parts downloaded` |
| otherwise (paused, a book started before a reboot) | every missing part its time and size | no part on the card: the capsule `Resume`; parts on the card: `12 of 37 parts downloaded` |

The capsule of a book with no part on the card is the download's button (`bk_hdr_btn`): a tap pauses while it runs, else starts (`bk_dl_tap`); it becomes Play with the first part. A waiting book's **Library row** has the same ring at step 0 and the text `Waiting`. The ring is also on the **Library's row** of the book that downloads, before its grey line (`Part 13 of 37`), the line starting a ring and a gap right.
The failure words are `bf_word` (`bkfind.c`, shared): `PN_NOWIFI` `No Wi-Fi`, `PN_NOCLOCK` `Set the date first`, `PN_NOCERT` `Certificates missing`, `PN_CERT` `Certificate problem`, `PN_NET`
`Can't connect`, `PN_GONE` / `PN_HTTP` / `PN_NOTFEED` / `PN_NOTAUDIO` `Server error`, `PN_STORAGE` / `PN_CARDFULL` `Storage unavailable`, `PN_NOBOOK` `Not available`, `PN_QFULL`
`Queue is full`, else `Not enough memory`. `bd_open` is called when the Book level loads (`bk_man_read`: the rows and the totals; a 108 KB record, freed at once, never per paint) and when the download's signature moved.

**Following the download** (`bk_tick`, 1 s, screen lit). When `bd_gen()` or the signature (`bk_dl_sig`: the running book and its part) moved, the Book level looks at the
signature. Unchanged (a progress step): only the texts of the part being fetched and of the first missing part are made again (`bk_retext_parts(1)`), nothing is scanned. Changed (a part came, the job began or ended): `bk_reload_book`, the
books read again and the rows made again at the same scroll offset and the same height: the part that landed becomes an ordinary row in place, and a book of 0 parts gets Play with its first part. A tap that starts the job reads the book again
at once. The Library level reads the whole list again on a changed signature and only retexts the lines of books with parts to come otherwise.

**Keep-awake.** A 1 s page timer (`bk_awake_tick`, `BK_AWAKE_MS`) calls stock's `reset_poweroptions_timer(1, 1, 0)` while `bd_active()` (a book downloads or others wait: the thread lives; only the instant between two books, a manifest read, is not covered; a Podcasts episode download alone does not hold it; the call and cadence of the Podcasts downloads timer; it
sets the standby and auto power-off countdowns again and leaves the screen's alone). It lives as long as the page does: behind another page, with the screen off. **Limit:** with the Audiobooks page
(and the Podcasts page) closed nothing resets the countdowns, so the device may go to standby, the Wi-Fi goes with it and the download ends with a network error; a tap on a part that is not on
the card, or Resume Download, continues it from the `.part`.

### Strings

`tools/pod_i18n.py`, 13 languages: `LibriVox` (the product name, the same everywhere), `Public domain audiobooks`, `Books`, `Popular`, `Search LibriVox`, `Open Book`, `%d of %d parts downloaded`, `%dh`, `%dh %dm`, `Pause Download`, `Resume Download`, `Delete Book`, `Delete this book and its files?`, `This book is playing`. Reused: `Playback Speed`, `Pause`, `Resume`, `Retry`, `Waiting`, `Queue is full`, `Failed`, `Downloading`, `Part %d of %d`, `%dm`, `%dm left`, `Continue Listening`, `See All (%d)`, `%d parts`, `%d MB`, `%d.%d GB`, `Download`,
`Loading…`, `No results`, `Not available`, `Storage unavailable` and the status words. `test/pod/bkfind.py/width_tests` fits each in its place in every language (the Library line at 99 of 99 parts).

### Limits and validation

- Nothing is device-tested. The "..." sheet, Delete Book and the ring on the rows are tested under Unicorn only. The Internet Archive's answers (advancedsearch, files, images, the download redirect) were checked on 2026-11-13; the tests run the compiled payload under Unicorn against a
  scripted libcurl and a card that is a dict of paths.
- 300 parts are listed (`BK_MAX_PARTS`); 100 books (`BK_MAX_BOOKS`); the files answer is read to 2 MiB; the manifest to 128 KiB; a download path to 240 bytes.
- Only the 64 kbit/s MP3 of each item is taken. Nothing validates that a downloaded file is MP3 beyond the refusal of a text answer (the policy of Podcasts episodes).
- One transfer at a time, the books queued behind it (16 waiting); searches, previews and Podcasts jobs and downloads run beside it, so with several at once the card and the link are shared.
- The page does not run the download: a started job outlives the page, but see keep-awake for the standby limit.
- A manifest that exists but cannot be read is not covered by a test (the test card ignores `access`).

### Not there

A language filter, the book's description, deleting a book of your own on the device (Delete Book is for a LibriVox download; delete a copied folder from a computer), a Settings switch to hide the LibriVox row, streaming without a download, more than
one book downloading at the same moment, automatic resume after a reboot (a tap on a part that is not on the card, or the capsule, continues it).

### Tests

`make test TEST=bknet` (`query_tests`, `secs_tests`, `docs_tests`, `files_tests`, `catalog_tests`, `preview_tests`: the builder, the docs parser, the scanner against `test/data/librivox/files.json`
and truncated or fuzzed files, the jobs through the scripted libcurl); `TEST=bkdl` (`name_tests`, `create_tests`, `part_name_tests`, `manifest_tests`, `model_tests`, `job_tests`, `reboot_tests`,
`interplay_tests`, `queue_tests`: names, folder, manifest, the job and its retries, the Podcasts queue and other jobs in both directions, the queue: order, no double entry, pause of the running and of a waiting book, per-book and global failures, capacity); `TEST=bkfind` (`library_tests`, `collapse_tests` (the small title at `SG_COLLAPSE` on the Library and LibriVox levels, right after a level change at a kept offset, the magnifier on its level only), `popular_tests`, `search_tests` (the magnifier, the keyboard on the empty field, Back to Popular at its offset) ... `download_tests`: the LibriVox, search and Preview
levels, with the Preview's third line; `row_tests`, `fail_tests`, `follow_tests`, `library_row_tests`, `sheet_tests`, `delete_tests`, `queue_tests` (the Waiting texts and ring, Pause for a waiting book, Delete Book of a waiting and of the running one), `awake_tests`: a row for every manifest part by state against `tools/pod_books.py`, the ring cells and step, the capsule of a book with no part, a tap on a part that is not on the card, failure words and retry, the busy toast, parts landing in place at the same offset, the queue of the files on the card, the Podcasts queue beside the book job, the Library line and ring, the sheet's rows by state, pause and resume from it, Delete Book (the confirm, the files, foreign files and a non-empty folder kept, a failing unlink, refused while playing, a running download stopped and waited for), the keep-awake call; `width_tests`: every new text in 13 languages). The worker's
counters are set in the tests through `bkdl.c`'s static record (`bd`, found by its size in the symbol table). Preview: `uv run python -I tools/preview/preview_books.py WORKDIR out/preview`
also writes `books-librivox.png` and `books-download.png`.

### Open

Not device-tested (the Library shelf and headers, See All, the Discover-like LibriVox level, the magnifier and the search level, and the new wording run under Unicorn only). Differences from Podcasts that stay: with no book the Discover header and the LibriVox row remain (Podcasts hides every row with no show; the row is the way to get books); the search level starts empty on every visit (Podcasts keeps the typed text); the LibriVox level's popular list is the only chart (no Shows | Episodes control). A file of the folder that the manifest does not name is not listed while parts are missing. In four languages (fr, es, th, uk) `%d of %d parts downloaded` was shortened to fit the Library row's 204 px; the translations are unreviewed, as are the new `Books` and `Public domain audiobooks` (restored from before 0c00dd04). Preview: `uv run python -I tools/preview/preview_books.py WORKDIR out/preview` writes `books.png`, `books-download.png`, `books-sheet.png`, `books-states.png`, `books-librivox.png` (the Discover-like level, the search level in each state, the Preview).
