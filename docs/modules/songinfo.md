# Get Info

**Sources:** `patch/songinfo.c` / `songinfo.h`, `tools/pod_ui.py` (`build_songinfo_page`),
`pod_pages.SONGINFO`.
A track's details page, opened by the Get Info row of the track rows' "..." sheet
([rowmenu](rowmenu.md)).

`songinfo_open(rec)` copies the title (the file name when empty), artist, album, path and CUE
start/end of the row's `stSongInfo`, so the caller may destroy the record at once. The page
`m1plus_songinfo` has Station Info's structure ([radio](radio.md), `patch/radioinfo.c`): the stock
navbar (Back, Now Playing, title "Get Info") over a stock list holding one content view painted in
its `EVT_AFTER_PAINT`, texts wrapped once by `pd_lines`, the navbar fade shown while scrolled. Four
hidden labels carry the text styles: `label_head` 22 px white, `label_sub` 16 px `#AAAAAA`,
`label_key` 14 px `#AAAAAA`, `label_val` 18 px white. No timer, nothing written; the memory goes
with the window. It returns -1 with no record, no window, an asset without the widgets or no
memory, and a second open while the page is on top opens nothing.

## Content

- **Header:** the cover, 96 px at (16, 16) with 8 px corners (one `grid_t` tile), then the title (at
  most two lines), artist and album (one line each, left out when empty) at x 124, 180 px wide,
  centred on the cover's height.
- **Cover:** the Cover Flow cache file of the track's own album key, else the file of the library's
  album record of that name (`cc_album_rep_key`), else the placeholder disc. A collab "A; B" has no
  file under its own artist, because the cache is named after the row `getAllAlbum` lists. That is
  one targeted query at open, none when the own file exists or the track has no album tag: stock's
  album statement filtered by name (`COLLATE NOCASE`, quotes doubled, a name over 250 bytes asks
  nothing). The Library filter rewrites it like every album list, so the record is the one the full
  list has, whatever order SQLite scans in. No album list is loaded, `*pdeq_showlist` is untouched
  and no cache job is started.
- **Pairs** (x 16, 288 px, a label over its value, a pair with no value left out), in order:
  **Format** (the extension upper-cased), **Sample Rate / Bit Depth** (`44.1 kHz / 16-bit`, or just
  **Sample Rate** when the depth is unknown), **Bitrate** (`N kbps`), **Duration** (`m:ss`,
  `h:mm:ss`), **Size** (decimal units: `845 KB`, `36.4 MB`, `1.23 GB`), **Path** (wrapped in full).
  Format to Size fit above the fold with Path's label peeking. The content ends at `gi.h`; nothing on the
  page takes touches.

## Sources

One read of the file's first 2 KB (a second after an ID3v2 tag, skipped by its synchsafe size):

- FLAC STREAMINFO (rate, bits, total samples), a WAV `fmt ` chunk, an Ogg Vorbis identification
  header (rate);
- for an MPEG extension only (MP3, MP2, MP1, MPA, MPGA), the first MPEG audio frame header whose
  next frame, when inside the bytes read, has a matching header (rate).

The size comes from `cc_file_size`. The duration comes from, in order: a CUE track's own end minus
start, the durations table ([album page](album-page.md)), FLAC's total, else TagLib's length of
this file (`dur_probe`, one open on the UI thread, not stored).

## Limits

- Bitrate is the file's average (bytes over seconds, including tags and art), not a stream value.
  It is hidden for a CUE track.
- Sample rate and depth of M4A/AAC/ALAC, Opus, APE, DSD, WMA and other formats are not readable, so
  their rows are hidden. The bit depth of every lossy format is hidden too.
- A missing file shows Format and Path only.

## A Navidrome track

`songinfo_open` asks `sbs_track(rec)` first. A Navidrome record (`nd://`) is not a file, so the
page takes its facts from the source's row: Format (the suffix), Sample Rate / Bit Depth (what the
server sent, else the downloaded file's first bytes), Bitrate (the server's figure), Duration, Size
(the server's, else the file's), and **Path only for a downloaded track** (the local file; the
server's own path is not kept). The cover is the cached Navidrome picture, else the placeholder;
nothing is requested. No file is read for an undownloaded track and TagLib is never used
([subsonic](subsonic.md)).
