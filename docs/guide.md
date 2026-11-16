# M1+ Music user guide

For installation, updates and restore, see [Install](install.md).

## In this guide

- [Start listening](#start-listening) and [browse and play](#browse-and-play)
- [Find a setting](settings-guide.md#find-a-setting) and browse the settings reference
- [Equalizer](equalizer-guide.md)
- [Features and extras](features-guide.md), including radio, Subsonic, podcasts, audiobooks and scrobbling

<!-- Screenshot: Home screen showing Extras, the mini player and the pull-down. -->

## Start listening

1. Copy music to the card.
2. Open **Extras → Update Library** to scan it.
3. Open **Albums**, **Artists** or **Songs**, then tap a track to play.

Tap the mini player's cover to open Now Playing. Its buttons pause/resume or skip.

## Find your way around

M1+ Music opens at startup and from its icon on Shanling Home. The default menu shows Cover Flow,
Albums, Artists, Songs, Playlists and Extras. Daily Mix and Recently Played appear below it;
the mini player appears while a track is queued.
Open **Extras → Settings** to customize the player. To return to the stock grid, use
**Settings → Developer → Open Shanling Home**. Change **Boot to M1+ Music** under
**Settings → Developer → Startup** to choose what opens at startup.

## Browse and play

| Page | Controls |
|---|---|
| Cover Flow | Drag to browse, tap a side cover to centre it, tap the centre cover to open its album; with Settings > Library > Volume Buttons on, volume down / up moves to the next / previous album |
| Albums | The navbar's **…** switches grid/list and sorts by Title, Artist, Recently Added or Year; the choices are remembered; the list in Title order has section letters, and in Year order a header per year (albums without a year last, under Unknown) with a rail of decades (2020, 2010, …); the grid in Year order has a header per decade (2020s, 2010s, …, a century before 1900, Unknown last) with each decade starting a new row, and no rail |
| Artists | Switch Artist/Album Artist in the navbar's **…**, then open an artist's albums: Play or Shuffle all the artist's songs, each album with its year; the **…** finds a photo of the artist online, switches grid/list and sets the album order; the rows and the artist's page show [artist photos](#artist-photos). A composer's page (Extras → Composers) looks the same, without a photo; its All Songs lists the composer's songs |
| Songs | Jump with the A–Z rail (Settings → Library → Index Rail, on by default); Search in the navbar; the **…** has Select and Sort (Title, File Name, Format, Recently Added; tap the ticked order to reverse it) |
| Recently Added | The newest songs; the navbar's **…** switches to the newest albums |
| Album | Play, shuffle the album, or tap a track; the footer shows the track count and length once measured |
| Playlists | Open a playlist (Play, Shuffle, or tap a track); the list-plus button creates, imports, exports or deletes; the **…** switches grid/list and the name order. Inside a playlist, **…** → **Clean Up Playlist** repairs songs whose files were moved to another folder (run Update Library first) and offers to remove the ones that are no longer on the card; only that playlist changes and no file is deleted |
| Folders | Extras → Folders lists the card's folders and audio files. With **Settings → Library → Folder Album Cover** on, a row with a cover shows it (40 px) in place of its icon: a file's is its album's, a folder's is the album of the first song of the library inside it (also in sub-folders); rows without one keep their icon. Only music in the library gets a cover; the covers are the ones the app has already made (Albums, Cover Flow), none are made here |
| Shuffle | Shuffle songs, albums or folders from Extras |

In Now Playing, tap **…** for playback options, Look up album, Look up artist and Display Mode, which opens Cassette Mode, Vinyl Mode, VU Meter Mode and Lyrics Mode. For a song playing from Subsonic the two Look up rows open the server's album and the server's artist; while it is streaming (not downloaded), Add to playlist and Delete are dimmed, and it is not added to the card's Recently Played and Most Played lists.
Swipe to Now Playing's third page for the song's details: the title (up to two lines), artist and album, then Format (with a HI-RES or DSD badge), Sample Rate, Bit Depth, Bitrate, Genre, Year, File Size and the Location on the card (up to two lines). Drag up and down to see it all; it is back at the top the next time you open the page.
Open its **More** page for **Sleep Timer** (a page with Off, 15 minutes, 30 minutes, 45 minutes, 1 hour, 1.5 hours and 2 hours; the player turns off when the time is up) and the
online cover and lyrics lookup (Wi-Fi required). The timer counts down in the same setting as Settings > All System Settings > Power; the page checks Off while no timer runs and keeps the time you picked checked while that timer counts down (a time set on the Power page is checked only when it is exactly one of the times). While a timer runs, a **Time Left** row under the list shows the time left as hours and minutes (`1:30`, rounded up to the next minute) and follows the countdown every few seconds; it is hidden while the timer is Off.

A track row's **…** on the album page and the Songs lists, or a long press (about half a second) anywhere on the row, offers **Play Next**, **Play After**,
**Add to Playlist**, **Favorite** (Undo Favorite when it is one) and **Get Info**: the track's
format, sample rate and bit depth, bitrate, length, size and path. Shuffle reorders the queue itself, so the Queue page's Up Next shows what
plays next; **Clear** in its header removes the songs after the playing one.
Each row of Up Next also has a **…**: **Play Next** moves that song to right after the playing one,
**Play After** moves it to the end, **Remove from Queue** takes it out of the queue (the file stays).
The **…** is not shown during folder playback or while DLNA is on.

While Line Out is on, the status bar shows an amber **LO** pill.

Drag a list to scroll; tap a row to open or play it.

### Artist photos

The Artists list and an artist's page show a photo you put on the card:

- Name it `artist.jpg` (`artist.jpeg` and `artist.png` work too).
- Put it in one of the artist's album folders, or in the folder above them if that folder holds only
  this artist's albums, e.g. `Music/Adele/artist.jpg` next to `Music/Adele/21/` and
  `Music/Adele/25/`. A folder that mixes artists (`Music/`, `Various Artists/`) is not used, and
  `CD1` / `Disc 2` folders are skipped.
- The photo belongs to the artist in the album's tags. "A feat. B" with no photo of its own shows A's.
- A square picture fits best. Other shapes are cut to a square: a wide one at the centre, a tall one
  near the top so a face stays in.

Home looks for photos while it builds covers after a library change. To pick up a photo added
later, open that artist's page, or use **Settings → Library → Rebuild Artist Photos**, which checks
every artist again in the background.

No picture on the card? Open the artist's page, tap **…** → **Find Artist Photo** (needs Wi-Fi): it
shows up to six photos from Deezer and NetEase Cloud Music, those under that exact name first. Tap one, then **Use This Photo**.
A photo picked this
way stays until you pick another: Rebuild Artist Photos and an `artist.jpg` added later do not
replace it.

### Split Artists

Some songs name several artists in one tag, like "A feat. B" or "周杰伦/蔡依林". **Settings → Library →
Split Artists** (off by default) lists such a song under each name in **Artists**: the list has one row
per name, an artist's page shows the albums and songs of every track that names them (a song with no
album tag is under All Songs only), and the search, **Look up artist** on Now Playing and Play, Shuffle and
Cover Flow on that page follow the same names. Look up artist opens the first name of the playing song.

- **Separators** choose what splits a tag: `;`, `/`, `&`, `,`, `feat.`, `vs.`, `x`, `+`, `with`,
  `and`. The default is `;`, `/`, `&` and `feat.`. The words need spaces around them, so "Malcolm X"
  stays whole. The switches are dimmed while Split Artists is off.
- Names that must never split, such as "Simon & Garfunkel", "AC/DC" and "Earth, Wind & Fire", are built
  in. Add your own, one per line, to `artist-exceptions.txt` on the card (blank lines and lines
  starting with `#` are skipped).
- The Artists page, the search and Look up artist read the setting when they open: an Artists page that was
  already open keeps its rows until you open it again.
- Photos: a name is looked for by the album's first artist, so a folder of `A` and `A feat. B`
  albums still counts as A's. A name that only ever appears after another gets no photo from the
  card; pick one with **Find Artist Photo**. After changing the switch, use **Rebuild Artist Photos**.
- Not split: Album Artist view, Genres, Composers, Subsonic servers, the Pod's Artists menu and Continue
  Playing's order. After a restart Memory Playback resumes the same track in the whole library (Songs order), not in the artist's list.

A Subsonic server's artists show the server's own artist picture instead, fetched in the background after a sync (the Subsonic page's status line says "Loading artist images…"); an artist the server has no picture for shows the grey placeholder in the list and the page without a circle.
