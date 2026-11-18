# Library list hand-over

**Sources:** `patch/libload.c`, `patch/covercache.c` (`cc_class_copy`), `patch/artists.c`
(`ar_load`), `patch/dailymix.c` (`dm_ph_copy`).
Every local list (Songs, Albums, Artists, Most Played, Recently Played, Favourites, a playlist's
or an album's songs) is read by stock's `loadLocalClassList(cls)`. Payload hook 29
([payload](payload.md)) removes the copies that function made, and the pages no longer keep a
second copy of a list they have just read.

## Stock

`loadLocalClassList` runs the class's query into `*tools_pdeq_directory` and ends, for every
class, in one tail: clear the destination, `deque_assign` the query's rows into it, clear the
query's deque, return the size. The destination is `pdeq_showlist`, `pdeq_playlist` (class
`0xf00b`) or the online classes' list. `deque_assign` copies every record (88 bytes) and its
strings, and libcstl allocates with plain `malloc`, so the old list, the query's rows and the copy
all sit in the heap together.

## The hook

- **`ll_load`** replaces the prologue. For a local class whose destination is the show list
  (`LCL_LOCAL`: `0xf001`..`0xf00a`, `0xff01`, `0xff02`, `0xff09`, `0xff10`..`0xff14`; proven by the two jump tables, pinned as `LCL_TABLES`) it clears `*pdeq_showlist`
  first, then runs stock's function through `stock_loadclass_trampoline`. Stock clears that list in
  the tail anyway, so only the moment of the free moves. Playlists and online classes are not
  cleared early.
- **`ll_assign`** replaces the tail's `deque_assign` call. It exchanges the two `deque_t` structs
  (`lib_deque_swap`): the destination owns the query's rows and the row deque is the empty one
  stock clears next. No record is copied.
- `lib_deque_swap` repeats libcstl's `deque_swap` (pinned by offset and SHA-256, `CSTL_SWAP`):
  it swaps the 0x14c bytes and fixes the iterators' container pointers. It refuses, changing
  nothing, unless both deques point at themselves. The library function is not called, because it
  compares the lists first and demo does not import it.
- Stock runs unchanged with `/mnt/mmc/m1plus-off` and whenever the exchange refuses.
- Boot-reachable (`tools/reach.py`), bounded: no allocation, thread, timer or file.

For a local list of N records read over M old ones, peak records fall from `max(M + N, 2N)` to N.

## Pages

- `lib_take_list(list)` makes a deque of our own that takes the stock list's records and leaves
  the list empty. It copies (`deque_assign`) only when the exchange is refused. `cc_albums` /
  `cc_songs` and the Artists page use it, so the list is held once.
- `*pdeq_showlist` is empty afterwards. A page that shows the stock list checks it
  (`grid_list_same`: pointer, size, first record) and reads again.
- Lists read for one scan are freed after it: the Albums page's Recently Added / Year scan
  (`so_stats`) and the Artists page's foreground comparison (`ar_local_changed`).
- Daily Mix copies its picks from the library list read while it is still the show list, and
  reads the library a second time only when another query came between.

## Limits

- The queries are unchanged: Most Played and the library are read whole, and Recently Played keeps
  its stock limit of 100.
- `loadSongList` / `mclLoadPlayList` still copy the shown list into the play queue.
- Pages that show the stock list itself (Songs, an album's tracks, the Pod levels, Search's
  songs) hold it once, as before.
