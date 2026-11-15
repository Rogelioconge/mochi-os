# The Folders page

**Sources:** `patch/folders.c` (the page), `patch/viewsort.c` (the card), `patch/songops.c`
(`so_play_with`, `so_selection`, `so_add`), `tools/pod_ui.py` `build_folders_page`,
`tools/pod_pages.py` (`FOLDERS`, `ACT_FOLDERS`), `tools/pod_pins.py` (`FOLDER_PINS`).
**Tests:** `test/pod/folders.py`. **Preview:** `tools/preview/preview_folders.py`
(`--covers` draws the rows with stock's Folder cover switch on).

The Extras Folders row (`ACT_FOLDERS`, arg `HOME_FOLDER`) opens `ui/m1plus_folders.bin` in place of
stock's `folder_page`. The stock page ([navbar](navbar.md), [rows](rows.md) restyle it) is only the
fallback when the window or asset will not open (`folders_open` returns through
`pod_home_open(HOME_FOLDER)`). No hook; everything runs from the page's widgets and timers.

## What stock does (read from the binary)

- **A filesystem walk, not the database.** `toolsLoadDirectory(path)` lists one directory into the
  queue deque `*0xa03964`: folders first, then files with an audio extension (and `.m3u8`). `.`,
  `..` and junk names (`lost+found`, `System Volume Information`) are skipped; every other dot name
  is listed (ours hides them). It never touches `*pdeq_showlist`; `folder_enter` copies the queue
  into it only after a load that returned > 0.
- **The root** (`load_rootfolder`) is three fixed records: `SD` (`/mnt/mmc`), `OTG` (`/mnt/usb`),
  `CD Library` (`/mnt/mmc/Ripper`). Record type (`+0x34`): 1 playlist file, 2 SD, 3 OTG, 4 folder,
  8 audio file; cue start at `+0x48`. No tags are read: a file shows its file name.
- **State** is global: the layer (0 before the first enter, 1 the root, 2.. folders), the path, the
  title buffer (`"folder"` at the root), the stack of scroll offsets, the m3u path.
- **`folder_enter(index, yoffset)`**: index < 0 resets to the root; a tap on a storage checks the
  mount (-2 "No TF Card Found", -3 "No OTG Found"); a type 4 record appends `/name` and loads it; a
  type 1 record parses the playlist file; a type 8 record returns 8 and changes nothing.
- **Return -1 ("File Not Found") is mostly an empty load**: the directory held nothing stock lists.
  The path is cut back and the layer, offset stack, title and shown list stay as they were. It also
  comes from a folder that is gone or an unparsable playlist file. So a failed enter leaves the
  shown list valid and only the queue deque empty; ours calls `folder_reload` (and `fo_load`,
  keeping the offset) after every -1.
- **`folder_back(&yoffset)`**: layer - 1, pops the offset; at the root it clears state and returns 0
  (the stock page then calls `navigator_back`). `folder_reload()` loads the current level again.
- **A file's tap**: `loadSongList(queue, name, cue, 1)` on the folder's files, then
  `navigator_to_with_context("playing_page", {queue, index, 1, 2})`. `g_class_type` is 1.
- **Select mode and its calls** (class 1 for both; pinned in `FOLDER_PINS`):
  - Delete: `batch_delete_file(1, ...)`. A folder is read with `toolsLoadDirectory` and each audio
    file in it leaves the library (direct children only; sub-folder files stay in the table until
    the next scan), then `remove_file` runs `rm -rf` on a directory, so **a folder goes
    recursively**.
  - Add: `batch_add_file(1, ...)` on a folder adds its **direct** audio files only. Playlist files
    and storages add nothing.

Both work on folder records, so our page passes them through `so_selection` unchanged.

## Our page

One window for every level, the Songs page's structure ([songs](songs.md)): the glass navbar
(Back, the small title, the capsule **"..." | Now Playing**), over a stock list whose one content
view holds the large title and, when the folder holds an audio file, the Play / Shuffle pills. The
page paints the rows itself.

- The small title shows once the large one scrolls away and runs to the "..." (x 214), to the Now
  Playing disc at the root, to Select All in select mode.
- At the root the "..." is hidden (its card would hold nothing) and Now Playing is the plain disc
  `ah_nav_np`. On a playlist file's tracks the button at 214 is Select (below).
- The root title says "Folders" (stock's is singular); a folder shows its name.

### Rows

The menu rows' style (`POD_ICON_X` 16, `POD_ICON` 24, `POD_TEXT_X` 56, `ROW_H` 52):

- A white 24 px Lucide glyph at x 16: `pod_ic_folders`, `pod_ic_playlists` (playlist file),
  `pod_ic_cdripper`, and ours `fo_ic_file`, `fo_ic_sd`, `pod_ic_usbmode` (`mod_icons.FOLDER_ROWS`).
- The name at x 56 (21 px white, one line, cut at x 256), hairline from x 56, press fill 20 %. A
  file shows its file name with the extension.
- Folder, storage and playlist file end in the shared grey chevron (`FO_CHEV_X` = `LIST_CHEV_X`
  288). The now-playing wave (`pod_ic_nowplaying`) marks what plays (the playing file, a folder or
  storage holding the playing file of a folder queue, the playing playlist file; stock's
  `is_folderplaying` / `is_playing` / `is_m3ulistplaying`). It is at x 262 on a file row, x 254
  (`FO_MARK_X_CHEV`) on a chevron row, where the name then ends at 248 (`FO_TEXT_END_CHEV`).
- The large title and pills are the Songs page's; the first row is at `SG_TOP` under the pills or
  `FO_TOP_PLAIN` 60 under the title alone. Select moves glyph, text and hairline right by
  `SG_SEL_COL` 30.
- Names starting with `.` are not shown. A folder with only such names shows "Empty folder".
- Neutral white and grey; no accent.

### Covers

Stock's Folder cover switch (`foldercover_flag`, `FOLDER_COVER`) is read as each level is read and
when the window comes back. Off: the rows above, and the library is never asked.

- On: a row with a cover shows a 40 px picture (`FO_COVER`) at x `FO_COVER_X` 8 with 4 px corners in
  place of the glyph. A row without one (storage, playlist file, a path the library lacks, an album
  with no cache file) keeps its glyph.
- A file's cover is its library track's album cache file; a folder's is the album of the first
  library track under it in path order. Our cache only: nothing is queued for stock's workers or
  built from this page.
- **Lookup cost.** No library list is copied. One row per 16 ms tick, rows in view only, nearest
  the middle first, never while the list moves or from a paint (`fo_on_load`). One lookup is one
  `toolsQueryDbTable` (file: `fileurl='<path>' limit 1`; folder: `fileurl>='<path>/' and
  fileurl<'<path>0' order by fileurl limit 1`; a path over 300 bytes is not asked). So cost does not
  grow with the level's size.
- The album cover map (`cc_cmap_build`, one `getAllAlbum` query) is made on the first lookup and
  freed with the page. No map leaves every glyph.

### Levels and play

- A tap on a folder is `folder_enter`; a folder or storage with nothing to list toasts "No music in
  this folder" and stays; a failed playlist file keeps `msg_notfile`. Back is `folder_back`; at the
  root the window closes. So Back and Now Playing behave as stock and no window stack is kept.
- On return to the front the list is read again only if another query replaced it (pointer, size,
  first record, as on Songs). A paint over a replaced list reads nothing; a 100 ms timer reads it
  when the page is on top.
- **Play** is the first audio file in order (`SO_IN_ORDER`); **Shuffle** a random file with Shuffle
  on (`SO_SHUFFLE`, [shuffle](shuffle.md)). Both use `so_play(class 1)`. A file's tap is `SO_KEEP`
  and the stock open (`navigator_to_with_context`).

### Order

The "..." card (`vs_glass4`): **Select** above one group **Name, Date Modified, Type**, one hairline
between. The ticked row is the order, its second line A-Z / Z-A (Date Modified: Newest First /
Oldest First, `vs_dated`). A row not ticked starts in its default direction; a tap on the ticked row
reverses it.

- Saved first in `folders-sort` (`FOLDERS_SORT_FILE`): `0` Name, `1` Date Modified, `2` Type, `a`
  `b` `c` the same reversed; missing or anything else is Name A-Z; a failed save changes nothing.
  One order for every level, read at open; the level is read again from the top.
- **Folders come before files in every order and direction.** The stock list is never reordered:
  `vis` is sorted in place (`cc_heapsort`, ties by record), so rows, taps, Play / Shuffle's first
  file and Select All follow the rows shown. Marks stay by stock record.
- Name is `cc_key_cmp` (digit runs by value, case folded, no pinyin); Type is the text after the
  last dot (case folded), then the name (Z-A reverses the extension only; folders have no type and
  stay by name); Date Modified is the mtime from one
  `statx` per entry (`ft_statx`) taken when the level is read, newest first, ties by name.
- Stock records carry no mtime, so Date Modified costs one syscall per entry. It is offered only on
  levels of at most `FO_STAT_MAX` (2000) entries; a bigger level shows by Name and the card has
  three rows (`vs_glass3`).
- The storages list has no card and is not sorted. A playlist file's tracks keep the file's order
  and have no card (Select is a navbar button instead).
- **Play order.** The queue `loadSongList` builds is put in the order shown by `fo_reorder`
  (`so_play_with`: each queue record takes the rank of the row with its path, then the permutation
  is applied in place). Files the page does not show go last. **Add to Playlist** appends in the
  folder's listing order, not the order shown.
- **CUE images.** Stock lists one record per TRACK of a `.cue`, all with the image file's path
  (`+0x48` / `+0x4c` hold the start and end). So anything matching a record uses the path **and the
  CUE start** (`fo_reorder`, `so_play_with`, and the twins in `ipod.c`, `search.c`, `shuffle.c`).
  In every order the tracks of one image stay together in the CUE's order and are placed as the
  image file would be. Stock's comparator does the same.

### Select

- Elsewhere the card's `Select` row; on a playlist file's tracks (`fo_direct`) `btn_select` takes
  the "..." place and enters select mode at once. Not at the root. A list that becomes the root
  ends the mode.
- Marks are a bitset by record on folders and audio files (not storages, not `.m3u8` files). A tap
  on a folder row toggles its mark instead of entering. Marks drop when the level is reloaded.
  "N Selected", Select All, the Songs page's bar.
- **Delete** follows the stock handler: a kind 1 confirm with `msg_delfile`, or, when any marked
  record is a folder (stock removes it with `rm -rf`), "Delete folder and everything in it?"; the
  m3u check; `batch_delete_file(1, list, vector, 0, 1)` on the stock vector filled by
  `so_selection`; `msg_delfilesuccess`.
- **Add** is `so_add(1, ...)`: the stock playlist picker with `0x10001`. The stock Favourites
  question is not asked, as on the Songs page.

### Texts

Translated: "Date Modified", "Type", "Empty folder", "No music in this folder", "Delete folder and
everything in it?" (that one wraps to at most three lines in all 13 languages). Stock keys:
`msg_delfile`, `msg_delfilefailed`, `msg_delfilesuccess`, `msg_notsupportdel`, `msg_nottf`,
`msg_nototg`, `msg_notfile`.

## Limits

- Covers come from our cache only, never stock's `.downpic` pipeline: a `cover.jpg` or embedded art
  that the library's album covers lack does not show, and nothing is made for a path the library
  does not hold (SD / USB files outside the scan, playlist files, storages).
- No tags: a file shows its file name.
- A marked folder: Add takes only its direct audio files and Delete leaves library rows of
  sub-folder files until the next scan (stock's loops read one level).
- If the hardware Back key calls `navigator_back` directly it closes the window at any level; the
  stock state stays at that layer until the next open resets it.
- The stock offset stack grows by one per open when the window is left by anything but Back at the
  root (stock does the same).
