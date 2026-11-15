# Recently Added albums

**Sources:** `patch/songs.c` (`rv_*`, `sg_set_view`), `patch/grid.c`, `patch/covercache.c`,
`tools/pod_ui.py` (`build_songs_page`), `patch/home.h` (`RECENTADD_VIEW_FILE`),
`patch/setfiles.c`. **Tests:** `test/pod/recentalbums.py`. **Preview:**
`tools/preview/preview_recent_albums.py` (`make preview` writes `recent-songs-view.png` and
`recent-album-view.png`).

The Recently Added list (stock class `0xf009`, shown on our Songs page, see [songs](songs.md) "The
other lists") has a View group in its "..." card: **Albums** (grid glyph) and **Songs** (list
glyph). The page stays the Songs page and the rows switch in place between the songs and a
newest-first Albums grid (the ticked row does nothing). Only this list has the group. Card layout: [songs](songs.md),
[albums](albums.md).

## What the user sees

- **Songs view** (default): the page as usual. The card is Select, hairline, Albums, Songs (Songs
  ticked).
- **Album view:** the card is Albums (ticked), Songs. Select is hidden and insensitive. Content is
  the large title "Recently Added" and the 2-column Albums grid ([albums](albums.md): 144 px
  covers, same cells, corners, loader and cover-cache build) from y 52, newest first. There are
  no Play / Shuffle pills and no song count. A tap opens our album page. With no albums the page
  shows "No albums".
- The small navbar title collapses in like the other lists'.
- **Remembered choice:** `/mnt/data/m1plus/recently-added-view` (`RECENTADD_VIEW_FILE`): `1` is
  albums; anything else or missing is songs. It is written on every change with
  `home_write_atomic`, read when the page opens, and listed in Settings Files.

## Data

- **Query:** the full `select * from songtable ORDER BY time_create desc` (stock `sort_time_desc`),
  not class `0xf009`'s query, which stops at 100 songs and would give too few albums. `rv_load`
  sets `sort_flag` to 3 (`RV_SORT_TIME_DESC`), runs `loadLocalClassList(0xf001)` and restores the
  flag at once. Nothing is saved and the library's order is untouched. `REC_TIME_CREATE` (`+0x50`)
  names the field; the page reads rows in query order and never the field.
- **Grouping:** each song resolves to the library album row of its album name (`cc_albums`, one row
  per album name, NOCASE). The first `RV_MAX` (60) distinct rows, in the order of each album's
  newest song, become tiles. A compilation or the same album in another case is one tile; a song
  with no album is skipped. Text, cover key and album-page row come from the library row.
- **Stock list ownership:** the query replaces `*pdeq_showlist`. The album view copies the 60 row
  numbers (`sg.rrow`) and never depends on the stock list. Entering invalidates the songs view's
  list pointer, and leaving runs `sg_load(0)` so class `0xf009` is read again.
- **Tile ring:** a second `grid_t` (`sg.rg`, about 1.1 MB with the placeholder) exists only in the
  album view and is freed on leaving. Loader and cache build follow the Albums page: one cover per
  16 ms tick, none while the scroll view moves.
- **Tap:** `cc_open_album(NULL, 0, row)` with the library album row. A drag, the title block, gaps
  and margins open nothing.

## Stock facts that drive this

- Class `0xf009` runs `select * from songtable ORDER BY time_create desc limit 100`. So the Albums
  side needs its own unlimited query. `sort_time_desc` is that query without the limit.
- `time_create` is filled by the scan from the file's stat times. Update Library drops and
  rebuilds `songtable`, so a rescan rewrites every `time_create`. Stock took `st_atime` on exFAT;
  `patch/filetime.c` supplies the creation time on FAT32 and exFAT, see [songs](songs.md)
  "Recently Added dates".
