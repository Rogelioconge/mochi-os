# Continue Playing: Next Albums

**Sources:** `patch/nextalbum.c` / `nextalbum.h` (prefix `na_`), `patch/albumpage.c`, `albums.c`,
`coverflow.c`, `shuffle.c`, `m1plus.c`, `setfiles.c`, `tools/pod.py` (`NEXTALBUM_SITE`,
`NEXTALBUM_PINS`), `tools/pod_pages.py`, `pod_i18n.py`, `mod_icons.py` (`skip-forward`).
Settings > Playback > **Continue Playing** is a value row (Off by default, or Albums) that opens a
picker with **Off** and **Next Albums** and the hint "Plays the next album in the order of Albums,
the artist or Cover Flow". When a List play queue started from an album ends, the next album plays,
in the order of the page that album was opened from. The row shows "Albums" rather than "Next
Albums", so label plus value fit the 216 px between the label and the value's right edge in all 13
languages.

Two parts: the order an album was opened from, kept in memory, and the end of the queue (hook 26,
`na_end`).

## Setting

`/mnt/data/m1plus/playback-next-album`: `1` is Next Albums; missing or anything else is Off.
`na_setting` reads it and `na_set(mode)` saves it with `home_write_atomic`. A mode that is not
offered or a failed save changes nothing. Turning Off drops the active source.

- `ACT_NEXTALBUM` 90 is the value row on the Settings root after EQ (`VK_NA`, `NEXTALBUM_PAGE`),
  glyph `skip-forward`. `ACT_NASET` 91 are the picker rows.
- The file is in `SETTING_FILES`, so Settings Files and Reset All Settings list and delete it.
- Off, or while `/mnt/mmc/m1plus-off` exists, nothing is recorded or allocated.

## The order

A source is one reference-counted block: `n` album keys (`cc_album_key`, in shown order, at most
`CC_CMAP_MAX` 4096), the `scope` (`CLASS_ARTISTS` / `CLASS_COMPOSERS`, 0 for the library), a deep
copy of the artist row (NULL for the library), `own` (the album the page was opened on) and `cur`
(the album now playing). Three slots hold it, so nothing frees what plays: `pending` (the note),
`page` (the open album page's order) and `active` (the playing queue's source). A failed allocation
leaves no source.

| step | caller | effect |
|---|---|---|
| note | `al_on_up` (Albums page, library and scoped, grid and list) and `open_album` (Cover Flow) call `na_note_albums(...)` before `cc_open_album` | keys of the shown order; the All Songs card and Unknown Album (`REC_ID` -1) left out; replaces the previous note |
| drop | same callers, after `cc_open_album` | `na_note_drop` frees a note that `album_open` did not take |
| take | `album_open` after its window is up: `na_page_open(key)` | the note becomes the page's order when the opened key is in it. `ab_on_destroy` calls `na_page_close` |
| arm | `ab_play_at` (Play, Shuffle pill, a track row) brackets `so_play` with `na_arm()` / `na_disarm()` | arm makes the page's order the active source; disarm restores the previous one if no load happened |
| load | `sh_load_playlist` (hook 14) calls `na_on_load()` first | armed: the source is kept. Not armed (Songs, playlist, folder, Daily Mix, podcast, radio, DLNA, boot resume, Pod, playmore): the active source is dropped |

`na_next_key(cur, &out)` returns the key after `cur` in the active order; 0 at the end (no wrap),
for a key not in the order, or with no source.

Sources are the Albums page (library), an artist's or composer's albums, and Cover Flow. Recently
Added, Search, Look up album, the Songs page, playlists, folders, Daily Mix, podcasts, DLNA, radio
and Pod mode are not sources: they stop at the end of the queue as stock does.

## Constraints

- The armed flag works because `ab_play_at` to `mclLoadPlayList` runs on the UI thread inside one
  call (`so_play_with` destroys its queue after `open()` returns).
- No lock: the flags are single bytes touched on the UI thread. A DLNA or refresh load on another
  thread can drop the source, which is right because it is a different queue.
- Only repeat off (stock mode 0) and the Shuffle flag off may continue.

## The hook

Hook 26, `na_end` ([payload](payload.md)). `mclNextSong` is stock's Next: `mclAutoChange` calls it
with `a0` = 1 when a song ends, `next_music` / `change_music` with 0 for the Next key. In List play
it plays pos + 1 if `pos < size - 1`. At the end it falls through to the folder-callback check,
`mclStop` and `{mcl-orderstop}` (or restarts the same song for a manual Next).

The two words at the end branch become `j pod_na_site; nop` (`NEXTALBUM_SITE`). The stub calls
`na_end()`. On 1 it jumps back to the end test, which now finds a longer queue and plays pos + 1
for both `a0` values. Otherwise it re-executes the two words and resumes: stock's end exactly.
`$a1` is live at the site (the Folder Skip branch passes it to `deque_at`), so the stub keeps it in
`$s0` across the C call. `NEXTALBUM_PINS` fail the build on a different binary. The site is not
reachable at boot (`tools/reach.py`) but is on the idle path, so work is bounded and any refusal
leaves stock's end ([safety](safety.md)).

`na_end` continues only when all hold, in this order. Each failure returns 0, changes nothing and
shows no toast:

1. setting on and no kill switch;
2. a source exists;
3. DLNA's `dmr_serverflag` is not 1 (DLNA's threads also reach `mclNextSong`);
4. Shuffle flag off and `mclGetPlayMode()` is 0;
5. the playing position is the last of a non-empty queue;
6. `na_next_key(na_cur())` has a next key.

Then:

1. **The album's name:** the albums of the source's list go into `*PDEQ_TOOLS_TMP` (no show list):
   the library through `toolsQueryDbTable` with the Albums list's statement (the Library filter
   applies), an artist's or composer's page through the stock getters `loadAlbumList` runs
   (`getAlbumByAlbumArtist`, `getAlbumByArtist`, `getAlbumByComposer`; the Unknown Artist row passes
   no name). The row whose
   `cc_album_key` is the next key gives the name, copied to a 256 byte buffer.
2. **The tracks:** the album page's own getter (`getMusicByAlbum`, `getMusicByAlbumAndAlbumSonger` /
   `AndSonger`, `getMusicByAlbumAndComposer`), so the order and the SQL are the page's by
   construction. Neither query touches `*pdeq_showlist` or the browsing record. The getters'
   prologues and the choosing words are pinned.
3. **Append:** `upnext_add(rows, 1)` at the end of the queue. Only `UPNEXT_ADDED` counts; any other
   answer (full, missing file, no memory, a stream play type, Radio, DLNA) is "not appended".
   `pod_queue_insert` stamps `REC_CLASS` from the playing row. On success `na_set_cur(next key)`,
   so the chain goes A, B, C.

`na_end` holds no lock. The payload mutex is taken once, inside the insert, after both queries.

## Limits

- There is a gap between albums; it is not gapless.
- The source is memory only: lost on reboot (the resume plays the saved queue as stock does) and
  dropped by any other queue load.
- Up Next and the Queue page show the appended album once its first song plays; Previous goes
  back into the old album.
