# Daily Mix

**Sources:** `patch/dailymix.c`, `patch/menu.c` (`menu_daily`), `tools/pod_ui.py` (`daily()`,
`build_dailymix_page`), `tools/pod_pages.py` (`ACT_DAILY`, `ACT_REGEN`), `tools/mod_icons.py`
(`DAILY`), models `tools/pod_dailymix.py` and `tools/pod_mix.py`, constants `DM_*`, `MIX_*`, `DP_*`
in `offsets.inc`, texts in `pod_i18n.py`. **Tests:** `test/pod/dailymix.py`, `test/pod/dmpage.py`.
**Preview:** `tools/preview/preview_dailymix.py`, `preview_dmpage.py`.

The Home menu shows a Made for You card above Recently Played: generated gradient art, the mix
title and artists, and a play disc. A tap opens the detail page; the disc plays. The mix is a file
of song paths, regenerated from listening history once a day. It becomes a stock playlist only when
the user saves a copy with the detail page's Add disc.

No stock hook and no boot work. Window and widget events and a page-owned timer drive the job and
the card.

## Layout

The section `pod_daily` is a `view` 310 wide (`SH_W`) in `pod_scrollview` between the last shown
row and `pod_shelf` ([recent](recent.md)). It is hidden and insensitive in the asset, shown when a
mix exists and the switch is on, height `DM_SEC_H` 272.

| part | geometry |
|---|---|
| header `pod_dm_head` | label at (10, 17), 269 x 22 (stops 6 px before the busy mark), 20 px white, key `Made for You`; same air as "Recently Played" |
| busy mark `pod_dm_busy` | 16 x 16 image at (285, 20), `dm_sync` (the status bar's sync glyph, `#AAAAAA`), hidden in the asset, static. Shown while a job runs |
| card `pod_dm_card` | `view` 296 x 220 at (12, 44), the width of the shelf's two covers. It paints art and text itself and takes the taps |
| corners | 12 px (`DM_R`), blended into black once in the bitmap |
| art | 296 x 220 RGBA bitmap, opaque, 260 KB, made by the generator below |
| title | "Daily Mix", two lines, 36 px white, x 18, boxes 38 high at y 84 / 122, 260 wide. Split at the first space; a title without a space (Tagesmix, 每日精选) is one line on the bottom box |
| artists | up to 2 lines, 16 px `#EBEBEB`, x 18, y 164 / 184, 204 wide: "A, B, C and more", at most 3 names (`DM_MAX_NAMES`), fewer when it would not wrap into 2 lines; if not even one name fits, its text is wrapped and cut with an ellipsis |
| disc `pod_dm_play` | stock `button`, 48 x 48 at (246, 202), glass (`dm_disc`, `_down`), white play glyph. A later sibling of the card, so it gets its own hit area |
| below | `DM_BOTTOM` 8 |

The busy mark is not shown for a card's first mix: it is a child of the hidden section. Only jobs
that replace a mix show it.

## Files

Everything lives on the card, so a mix follows its card:

- `CARD_DIR` `/mnt/mmc/.m1plus` (hidden) and `daily-mix/` in it hold `tracks` and `art`.
- **No card, no mix.** `m1_card_mounted` (`patch/common.c`) is checked before every read and write
  and before a job is wanted. With the card out the section stays hidden and nothing is written.
- A card swap shows that card's own mix, or makes one after `DM_START_MS`.
- All writes are `m1_card_write` (temp file, `fsync`, `rename`, directory `fsync`). The mix file is
  written before the art file, both in the last phase, so a failed or dropped job writes nothing.
- **Nothing Daily Mix writes can be read by the stock playlist Import.** Import reads only
  `/mnt/mmc/_explaylist_data` and names ending in `.m3u8` / `.m3u`. Every payload file is under
  `/mnt/mmc/.m1plus/`, has no such ending and is in no `_explaylist_data`. Tests collect every path
  opened for writing, renamed or unlinked during a full job and assert it.

**`tracks`** (`MIX_FILE`; `tools/pod_mix.py` `dump_mix` / `parse_mix` is the model, `dm_load` the
strict reader):

```
M1X2\n
<day dec>\t<seed hex8>\t<art seed hex8>\t<regen dec>\t<songs dec>\n
rrggbb rrggbb [rrggbb [rrggbb]]\n                 (2..4 tones)
<artist>[\t<artist>[\t<artist>]]\n                 (1..3 names, UTF-8, < 96 bytes, no control byte)
<path>\n                                          (<songs> lines, 1..255 bytes each, no control byte, in play order)
```

- Day is days since 1970-01-01 of the local calendar day. Seed is `day * 2654435761 ^ regen *
  0x85EBCA6B` (never 0). `regen` counts how often today's mix was made again. Songs are 10..25.
- At most `DM_FILE_MAX` 8192 bytes. Any deviation is "no mix": the section stays hidden.

**`art`** (`MIX_ART_FILE`): `M1XA`, width, height (u16), art seed (u32), FNV-1a of the pixels
(u32), then 296 x 220 RGB565 words. Size, magic, fields, the mix file's art seed and the checksum
must all agree, else the art is made again from the mix's own tones and seed. It is stored without
corners; the bitmap gets them when expanded.

**`/mnt/data/m1plus/home-daily-mix`** (`DAILY_SET_FILE`): the Settings switch. `0` or `0\n` is off,
anything else or no file is on. It stays on `/mnt/data` as a device preference.

## The art

`dm_*` in C; `tools/pod_dailymix.py` `art(tones, seed)` is the model. It is integer-only and the
test compares the pixels.

1. **Tones** (`dm_prep`): the mix's top albums' tones in integers (lightness `l2 = max + min`,
   chroma `d = max - min`). A colourful tone gets at least 0.55 saturation and a lightness in
   [0.30, 0.56]; a grey one a lightness in [0.25, 0.66]. Hue is kept, so pale covers do not wash
   the card out and dark ones do not vanish.
2. **Base:** the darkest prepared tone at 50%.
3. **Blobs:** n tones are n blobs in n horizontal sectors, centres jittered by an xorshift32 stream
   seeded with the art seed, radius 0.62..0.92 of the width, laid over the running colour with
   alpha = 240/256 x (1 - d^2 / R^2)^2 (no exp, no sqrt).
4. **Scrim:** a black vertical scrim, 0 above the text zone, smoothstepping to a64/64 at the first
   title row. `a64` is the least value (at least 10) at which the brightest text-zone pixel gives
   the dimmer ink `#EBEBEB` 4.7:1, verified on the dithered pixels.
5. **RGB565** with a 4 x 4 Bayer dither.

The art seed is `seed ^ FNV(path of the first song)`, so the card changes daily and on Regenerate,
not on each visit. Tones come from the three top albums by song count: the cover key of the
album's stock row, then the tone cache (`m1_tone_get`) or one cover decode per tick. A cover that
cannot be read adds no tone, and fewer than two tones are completed from a fixed palette (blue,
rose, teal, brown) starting at `seed % 4`.

## The mix

Inputs come through the Songs page's `loadLocalClassList`: the library (`0xf001`), Most Played
(`0xf008`), Recently Played (`0xf007`, last 100) and Favourites (`0xf00a`). Songs match by path
hash. Caps: `DM_LIB_MAX` 12,288 library songs, `DM_OFT_MAX` 8,192, `DM_FAV_MAX` 4,096.

`score = MIX_W_PLAYS (4) x lg(plays, cap 200) + MIX_W_ARTIST (2) x lg(artist's plays, cap 4000) +
novelty (60 never played, 30 played once) + 50 if a favourite - 160 x (100 - position) / 100 for
a song among the last 100 played + a seeded jitter of 0..127`, with `lg(n) = 16 log2(1 + n)` in
fixed point.

- Selection is **25 songs** (`MIX_SONGS`), best score first, at most 2 songs of one artist and 2
  of one album (names compared with ASCII case folded). Then a seeded Fisher-Yates shuffle and one
  pass that pulls apart two songs of one artist side by side.
- **Threshold:** a library under `MIX_MIN_LIB` (50) playable songs gets no mix and no card.
- **Thin libraries loosen:** when the limits leave the mix under 25, they go to 4 per artist and
  3 per album (`MIX_PER_ARTIST2`, `MIX_PER_ALBUM2`), then to no limit, so 300 songs by 3 artists
  still make 25. The side-by-side pass is best effort.
- An untagged artist or album is the song's folder (`dm_tag`), so an untagged library is not one
  capped "artist".
- Under `MIX_MIN_SONGS` (10) left after the files are checked on the card means no mix, and the
  day is not tried again.

## The job

Phases `dm_*` run one slice per tick of the Home page's timer (`DM_TICK_MS` 30 ms), never in paint
and never at boot:

| phase | one tick does |
|---|---|
| `OFT`, `REC`, `FAV` | load the list (the stock query), then `DM_SLICE` 1,536 records a tick hashed into our tables |
| `LIB` | library hashes, plays, recent position, favourite, the artist's play total, `DM_SLICE` songs a tick |
| `SCORE` | `2 x DM_SLICE` songs a tick |
| `PICK` | one pick a tick, then the shuffle |
| `COPY` | the picks copied with their strings from the library list, which is still the show list (read again only when another query came between, [libload](libload.md)); files not on the card dropped; names and top albums |
| `ALBUM` | cover keys from the stock album list once, then one tone a tick |
| `FIELD`, `BRIGHT`, `RENDER` | blob field, brightest pixel of the text zone, render passes of `DM_ROWS` 20 rows a tick |
| `COMMIT` | the mix file, the art file, read back, the card switched. The largest tick |
| `SAVE` | art-only job: art file written, bitmap switched |

- **Start:** the Home menu is in front, the switch is on, `DM_START_MS` (8 s, past the boot
  guard's 5 s window) have passed since it opened, and the local day has no mix yet or Regenerate
  asked for one. The previous mix stays on the card until the new one commits. A failed day is not
  tried again until tomorrow, a restart or Regenerate. A clock before 2020 makes no mix. While the
  screen is off the timer checks at most once per second; a mix due at midnight waits until the
  screen is on and Home is in front.
- **Busy mark:** `dm_busy` shows `pod_dm_busy` while `dm.job` is set, whether it is the daily job,
  Regenerate or the art-only job.
- Every list is checked at every tick (handle, size, first and last record). Another list loaded
  in between ends the job. The menu going to the background drops it, and it restarts from the top.
- **Entry:** `home_menu_opened` calls `dailymix_start`, which reads the 1 KB mix file and registers
  events. The art file is read `DM_FIRST_MS` later and a mix is made no earlier than
  `DM_START_MS` after that.
- Job tables are `calloc`ed and freed when the job ends or fails; a refused allocation ends the
  job and the day is not tried again.

## The mix as songs and as a queue

- **Storage:** the paths in the mix file; nothing in the stock `playlist` table except the page's
  Add disc copy.
- **The mix's rows only** (`dm_rows`; never the whole library): stock's song query with another
  SQL, `select * from songtable where fileurl in ('p1','p2',...)`, run through `toolsQueryDbTable`
  (`QUERY_PINS`) with `'` doubled. Its rows land in `*tools_pdeq_directory`, so `*pdeq_showlist` is
  not touched, and `dm_rows_done` clears the deque after use. The Library filter hook
  ([payload](payload.md) hook 6) leaves a statement over its 1 KB buffer as it is, which is as
  correct.
- **Finding the songs** (`dm_mix_find`): path hashes compared with the mix's, a hit verified with
  `strcmp`.
- **Queue** (`dm_play_at`, used by the disc, a row, Play and Shuffle): rows whose file is missing
  are left out. The start song is the wanted one, the first, or a random one with Shuffle. The
  kept rows are pushed in the mix's order into a small deque that `*pdeq_showlist` points at for
  one call, `loadSongList(queue, name, cue, 0xf001)` runs, and `pod_open_player` opens Now Playing
  at the wanted path (found by path: `loadSongList` matches by name and CUE start, and a name shared
  by several songs is not enough). The queue gets class `0xf001`; the memory-playback record is
  left as before. There is no `classinfo[1]` or `NAV_TITLE` write, no `allmusic_page` and no
  `0xff13`. After a reboot the player resumes in library order (the memory-playback
  record is the library's). A missing wanted song shows "Storage unavailable".

## Card taps

- The card (`dm_on_down` / `up` / `abort`, never consuming, `RC_TAP_PX` 10 as the shelf) opens the
  Daily Mix page. A drag or an aborted press opens nothing. With no song of the mix left in the
  library and on the card, the "Storage unavailable" message shows.
- The disc plays from the first song with `dm_play_at`. The play mode is the user's.

## Settings > Home Screen

Rows: **Recent Albums** and **Daily Mix** (switch, `ACT_DAILY`) in one card, then **Regenerate
Daily Mix** (action row without a chevron, `ACT_REGEN`) in a card of its own, last on the page.

- The switch shows or hides the section and stops or starts the job. With it off nothing is made,
  not even for Regenerate.
- **Regenerate** only asks (`dailymix_regen`, a counter that outlives the Home window). The Home
  menu makes the mix the next time it is in front, in about three seconds. An accepted tap shows
  the toast `New mix when Home opens`. A refused tap shows nothing. Two asks before Home is in front are one regeneration.
- If Home is covered or destroyed before a manual job commits, `dm_job_cancel` restores the
  request, and returning to Home restarts it with the next seed from the committed mix, even if that
  mix is already today's. Completing a job clears the request.
- **Regenerate is hidden while no mix can be made** (`dailymix_can_regen`: switch off, or the last
  job found fewer than `MIX_MIN_LIB` songs, the RAM flag `dm_small`). `regen_show` in
  `patch/m1plus.c` hides the row and its note (not visible, not sensitive), and the switch updates
  them in place. A hidden row's tap is refused too. Songs added to a small library are seen by the
  next day's job or a restart.
- Texts: `Made for You`, `Daily Mix`, `Regenerate Daily Mix`, `New mix when Home opens`, `%s and
  more`, `%s, %s` (`%s、%s` in Chinese and Japanese). All fit in the 13 languages
  (`test/pod/dailymix.py`).

## Safety

No new hook, no boot-path or main-loop code, and nothing at paint but the card's own after-paint
(a blit of the resident bitmap and canvas text). Every failure leaves the plain menu or yesterday's
mix: a missing widget, a refused `widget_on`, no timer, an unreadable or malformed file, an
unreadable art file (made again), no memory, no songs, a list changed under the job, a library
under 10 songs, the card not mounted, an unwritable file. A hidden section is hidden and
insensitive.

The job and the card call no stock playlist function. Only the page's Add disc does
(`createPlayListItem`, `checkPlayListExist`, `getPlayListMaxId`, `addPlayList`, pinned in
`PLAYLIST_PINS` with the words of `batch_add_file` they mirror). `test/pod/dailymix.py` asserts
these names occur in no other function, see [playlists](playlists.md).

## The page

An Apple-style playlist page ("Heavy Rotation"), opened by a tap on the card. Own window
`ui/m1plus_dailymix.bin`, no navbar, no hook, no boot-path code: the stock `list_view` >
`scroll_view` over the whole 450 px, one content view `view_dm` that paints the art, lines and
songs in its after-paint, a floating glass back disc (`btn_return`) and, inside the content view,
the Shuffle disc, the Play pill and the Add disc. Everything is freed on destroy. Window, list,
scroll view and content view get the same solid tint.

| part | geometry (window px, content scrolls) |
|---|---|
| art | 320 x 180 from y 0, RGBA bitmap, the last 60 rows (`DP_FADE`) fade into the tint. No text on it |
| back disc | 44 px touch square at (8, 8), 40 px glass chevron, the only control outside the list |
| title / subtitle / updated | centred in x 16..304, boxes 24 / 17 / 14 px high at y 193 / 218 / 239 |
| buttons | Shuffle disc, Play pill, Add disc, symmetric about x 160, at y 263 |
| Shuffle disc | 44 x 44 touch at (32, 263), 40 px drawn at x 34..74 (the album page's `ah_shuffle`) |
| Play pill | 148 x 44 touch at (86, 263), white 148 x 40, pressed `#D6D6D8`, 16 px glyph + 8 px + text centred, ink `#141414`; the widest "Play" is 88 px |
| Add disc | `btn_dp_add` 44 x 44 touch at (244, 263), 40 px drawn at x 246..286: Shuffle's disc (`#2A2A2A`, pressed `#444444`) with a `plus`, or a `check` once saved |
| description | up to 2 lines of 288 px at y 317 and 337 (15 px), the second ends in an ellipsis if longer. Rows start at 371 |
| rows | 64 px, the Albums list's numbers (`LIST_*`): cover 52 px at x 10 with 4 px corners, text at x 74 (234 wide: 21 px title, 18 px artist), hairline 13% white, pressed row 20% white. Content is 371 + n x 64 + 16 |

Vertical rhythm follows the album page's method (`tools/ah_ink.py`, asserted by the test): art
bottom to the title's capitals 16, title baseline to the subtitle's capitals 9, subtitle baseline
to the Updated digits 9, Updated baseline to the pill's top 16, the pill's bottom to the
description's capitals 16.

- **Tint:** the art's last row is averaged (the card's blob field at 320 x 180, same seed and
  tones, so the page looks like the card), its brightest channel lifted to 48, darkened until its
  luminance is at most 0.07, snapped to the 565 grid. White text is at least 8.8:1 and grey at
  least 5.15:1 over the tested palettes.
- **Status bar:** takes the colour of the art's top row (`dp.barc`, darkened until white glyphs
  keep 4.5:1) while the page is in front, with `m1_bar_tint` / `m1_bar_black`
  ([nowplaying](nowplaying.md) "Status bar"). Black returns on background and destroy, only while
  the bar is still the page's.
- **Art:** made once at open, row by row straight into the bitmap, 230 KB resident. It is
  pixel-identical to `pod_dailymix.page_art`; the card's generator is the same code at the card's
  size.
- **Songs:** the mix file's songs that are in the library and on the card, in the mix's order
  (`dp_songs`: one `dm_rows` query, `dm_mix_find`, `access`, each record copied by `dm_rec_copy`).
  No favourites star. Cover keys: the album's stock row matched by title, else the song's own
  artist + album. Covers load one per 16 ms tick, nothing while the list moves, no background
  cache build, a missing cache file shows the placeholder disc.
- **Playing:** a row tap, Play and Shuffle all go through `dm_play_at`. The library is read again
  and the mix found in it, the file is checked (missing shows the "Storage unavailable" toast and
  the page stays), then `pod_open_player` opens Now Playing. **Play** is in order from the first
  song (`pod_set_in_order`: Shuffle and Repeat one become List play, other modes are kept; a row tap
  keeps the mode). **Shuffle** is the stock Shuffle mode (`pod_set_mode`, see [shuffle](shuffle.md))
  and a random start; the queue is the whole mix.
- **No Regenerate disc:** the job runs on the Home page's timer and needs Home in front.
- **Updated line:** the mix file's local day against today (`dm_today`): `Updated today`,
  `Updated yesterday`, else `Updated 2026-10-26` (ISO date, nothing to translate). A clock that is
  not set or went back says today. New keys: `Updated today`, `Updated yesterday`, `Updated %s`,
  `Play`, and the description line.
- A page that cannot open does nothing: no song left shows "Storage unavailable", a missing
  widget goes back, no memory for bitmaps opens the page on its tint without art or covers.

### The Add disc

`dp_save`, `dp_on_add`, `dp_look`, `dp_mark`. One tap makes a new stock playlist, once per mix,
with no dialog. The name is the translated "Daily Mix" plus a space plus the mix's own day as
`YYYY-MM-DD` (at most 96 bytes), for example `Daily Mix 2026-10-29`.

1. The page's rows are checked again for a song record (`REC_TYPE` 8) and the file. None left
   shows "Storage unavailable" and makes no playlist.
2. The browsing class, `classinfo[0..1]` and `nagvation_title` are saved.
3. `loadLocalClassList(0xf00b)` reads the stock playlist list, then `createPlayListItem(list, name)`:
   -2 (exists) shows `msg_playlistexist` and the disc becomes a check; -1 (full, 100 playlists)
   shows `msg_playlistfull`; else the result is the playlist id.
4. The songs go in one by one in the mix's order, as stock's `batch_add_file` adds a row: a copy of
   the page's record, `checkPlayListExist` (1 skips), `getPlayListMaxId`, `REC_ID` = max(100, that)
   + 1, `REC_DISC` = the playlist id, `addPlayList`.
5. The saved globals are put back, then `msg_addplaylistsuccess`, or `msg_addfailed` when no row
   went in.

Why not `batch_add_file`: it walks the selection in library order, the mix needs its own, and it
needs a stock selection vector over the whole library deque. The mix file is not touched, and the
playlist is a row of `/mnt/data/database.db`.

**Saved is a check.** `dp_look` reads the stock playlist list when the page opens and each time it
returns to the front, and looks for a row whose `REC_TITLE` is exactly the name. Found, or made by
a tap, the disc shows `dp_added`, and another tap only shows `msg_playlistexist`. A full table
leaves the plus.

**Stock has no playlist rename**, so the only way to another name is a new playlist
([playlists](playlists.md)).
