# M1+ Music user guide

For installation, updates and restore, see [Install](install.md).

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
| Folders | Extras → Folders lists the card's folders and audio files. With the Playback setting **Folder cover** on, a row with a cover shows it (40 px) in place of its icon: a file's is its album's, a folder's is the album of the first song of the library inside it (also in sub-folders); rows without one keep their icon. Only music in the library gets a cover; the covers are the ones the app has already made (Albums, Cover Flow), none are made here |
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

## Settings

Grey values on the right show the current setting. The pages, top to bottom: Wi-Fi, Bluetooth,
Home Screen, Library, Now Playing, Playback; then one card with General, Display, Appearance,
Buttons & Power and Battery; All System Settings and Developer last.

**All System Settings** is the player's own full list of system settings, as a fallback. It also
holds the rarely used stock pages: Firmware Update (update from a card), Regulatory, Format Storage
and Reset.

### Wi-Fi

- The Wi-Fi switch, the connected network, **My Networks** and nearby networks with their
  security, and **Other…** for a hidden network. WPA3 and Enhanced Open networks join.
- A network's info glyph opens its page: the full name under the title, and for a saved network
  **Forget This Network** and **Auto-Join**. Long names end in an ellipsis in the list.
- Settings → All System Settings → Wi-Fi opens the same page. With `/mnt/mmc/m1plus-off`
  it opens the stock page, the only way to join a WEP network.

### Bluetooth

- The Bluetooth switch and **Audio Codec**: LDAC HQ, Standard or Connection, aptX HD, aptX, AAC,
  SBC HQ or SBC. A connected device is asked before it reconnects.
- A note with this player's name.
- **My Devices**: paired devices. A tap connects or disconnects; a check marks the connected one.
- **Other Devices**: devices found nearby. A tap pairs and connects; **Search Again** after the
  search ends.
- A paired device's info glyph opens its page: **Connect** or **Disconnect**, **Headset Volume**
  while it is connected, **Forget This Device**, and the full name under the title.
- Wi-Fi and Bluetooth can be on together. Turning one on while the other is on warns that
  Bluetooth audio may stutter, and leaves both on (also from the Control Center tiles).
- Settings → All System Settings → Bluetooth opens the same page (the stock page with
  `/mnt/mmc/m1plus-off`).

### Home Screen

- **Recent Albums** and **Daily Mix** on Home. **Regenerate Daily Mix** takes effect at the next
  Home visit.
- **Main Menu**: show, hide or reorder the menu items.
- **Extras**: hide items from Extras. Settings always stays reachable.

### Library

- **Update Library**, **Rebuild Covers**, **Rebuild Artist Photos**.
- **Split Artists**: list a song under each of its artists, with the separators to split on.
- **List Navigation** (Songs, Artists, Albums and Radio lists):
  - **Index Rail**, on by default: the A–Z rail on Songs, Artists, Radio countries and the Albums
    list in Title order; decades in Year order.
  - **Section Headers**, on by default: section letters and the pinned header. Off closes the rows
    up.
- **Folder Album Cover**, on by default: Folders rows show a cover where the folder has one.
- Landscape Cover Flow, and **Volume Buttons** (off by default): the volume buttons move between
  albums in Cover Flow.
- **Podcasts**: **Podcast Discover**; **Directory** (Apple Podcasts, the default, or Podcast
  Index), where podcast searches and show look-ups go; **Podcast Region**. Discover's charts
  always come from Apple. Directory and Region are dimmed while Podcast Discover is off.
- **Scrobbling**: see Scrobbling under [Extras](#extras).

### Now Playing

- **Cassette Theme**: Normal, Chrome, Metal or Auto (the default); applies the next time Cassette
  Mode opens. Auto picks the tape by the track: Normal for MP3 and other lossy files, Chrome for
  CD-quality lossless, Metal for hi-res and DSD. Hi-res and DSD also get a gold sticker in every
  theme.
- **Vinyl Record** and **Base** colours.
- **Lyrics Text Size**: Small, Medium or Large (the default), 22, 26 or 30 px. An open Now Playing
  picks up a change when you return to it.
- **Idle Display**: what Now Playing shows after 10 seconds: Off, Album Cover, Cassette, Vinyl, Lyrics or
  VU Meter. Off is the same switch as Playback Settings → Cover mode.

### Playback

**EQ** opens the [Equalizer](#equalizer). **Playback Settings** is a page with two sub-pages, Volume & Sound
and Output, together the settings stock keeps in its Playback Settings list. Every setting is the same one stock's pages use and takes effect at once (Default Volume at
the next start).

- **Playback Settings**
  - **Play Mode**: List Play, Repeat Track, Shuffle, Repeat All.
  - **Gapless**; **Resume**: Off, Track or Location, where playback resumes after a restart.
  - **Folder Skip**.
  - **Continue Playing**: Off (the default) or Next Albums. When an album started from Albums, an
    artist's albums or Cover Flow ends, the next album in that page's order plays, after a short
    gap. Not with Repeat or Shuffle on, and not from Songs or Search.
  - **Volume & Sound** and **Output** open the two sub-pages below.
- **Volume & Sound**, with a **Volume** header
  - **Gain**: Low or High; dimmed while Line Out is on, as in stock.
  - **Max Volume**: 0 to 100, with a slider and − / + buttons. The volume keys stop there, and a
    higher volume is lowered at once.
  - **Default Volume**: the volume at the next start. **Volume Memory** on keeps the last volume;
    off uses the slider. The row says Memory or the number.
  - **ReplayGain**: Off, Track or Album.
  - The three volume pages use stock's slider code, so a drag saves as often as stock's did.
  - Under a **Stereo** header: **Channel Balance**: a slider from L to R with L and R buttons; the row says e.g. L3, 0 or R2.
    No effect on Line Out or USB audio, as in stock.
  - **Mono Audio**: both channels play the same mix, on every output, also with the Equalizer off.
  - **Crossfeed**: Off, Low, Medium or High. Each ear hears a little of the other channel, so
    stereo recordings sound less extreme. For headphones and Bluetooth only, not Line Out, a USB
    DAC or DSD; the row keeps your choice.
- **Output**
  - **Digital Filter**: the DAC's eight filters.
  - **DSD Output Mode**: D2P, DOP or Native. On a USB DAC the song restarts where it was.
  - Under a **USB & Digital** header: **USB Mode** (opens the player's USB page), **USB Volume**
    (Fixed or Variable) and **Digital Output**.

### General

- **About**: firmware, device, network and storage details.
- **Software Update**, the row under About: see [Software Update](#software-update).
- **Date & Time**: **Set Automatically** syncs the clock over Wi-Fi. **Time Zone** (43 zones) can
  always be changed. **Date** and **Time** have Year / Month / Day and Hour / Minute pickers and a
  Set row, and change only while Set Automatically is off. **24-Hour Time**.
- **Keyboards**: English is always on. **Chinese (Pinyin)** adds a language key and candidates
  above the keys; swipe the candidates sideways, and Space picks the first. Tidal's Search uses
  this keyboard too, at the bottom of Tidal's own page: Search hides it, and a tap on the search
  bar brings it back.
- **Language**: the current language's own name at the right. The list names each of the 13
  languages in its own writing; a choice switches the whole player at once and returns to Home.
  Texts the original firmware left in English in other languages (Look up Artist, Look up Album,
  the sort orders, the digital filters) are translated.

### Display

- Brightness slider; **Screen Timeout**: Never, 15 s, 30 s, 1 min or 5 min.
- **Lock Screen**: **Enable**; **Show Time**; **Player Style**: Large Cover or Mini Player (a bar
  like Home's at the bottom); **Wallpaper**: the default or one of up to five pictures you copy to
  the card's `lockscreenimage` folder (JPG or PNG, 320 × 480, under 1 MB), the chosen one framed in
  the accent. **Custom Wallpaper** explains the pictures. The lock screen shows a short date in
  your language over the clock, such as Wed, Nov 11. All System Settings → Display → Lock Screen
  opens the same page.
- **Screen Rotation**: on turns the screen upside down (180°), at once and kept after a restart.
- **LED Light**: Off, Green, Blue or Dynamic. **Follow Screen** turns the light off with the
  screen.
  - **Dynamic** makes the light follow the music, and adds a **Theme** row. A note at the top of
    the Theme page describes the chosen theme; the six themes are under Ambient and Sample Rate.
    **Reference** shows the playing track's sample rate
    as a colour, from red-pink at 44.1 kHz through blue around 96 kHz to green at the highest
    rates. **Gentle Breathe**, **Heartbeat** and **Lighthouse** pulse that colour; **Candle** and
    **Wave** are mood lights with colours of their own.
  - The light fades when playback pauses, and replaces the red charging light while a track plays.

### Appearance

- **Background**: Black, or Tinted: with an accent chosen, the dark greys of every page, card and
  sheet take a 12 % wash of it. Covers and cover-coloured pages keep their look.
- **Accent**: Neutral (the default), Red, Orange, Green, Teal, Purple or Champagne. Tints the main
  menu's icons, pressed rows, switches that are on, lit pull-down tiles, sliders and progress
  bars, the picker check, selection marks, the index rail's selected letter, the EQ curve and the
  download rings. Applies at once.
- **Control Center**: show, hide and reorder the pull-down's tiles, up to eight ("Up to 8
  controls"). Besides the stock tiles there are six of ours, hidden until you turn them on:
  - **Sleep Timer** (the same page as Now Playing's More page), **Settings**, **Equalizer**;
  - **Power Off**: asks "Confirm Shutdown?", as holding the power key does;
  - **AirPlay** and **DLNA**: a tap turns the service on or off (the same setting as Network
    Service), the tile lights while it is on, and the pull-down stays open. The services run only
    on Wi-Fi: without it the setting is kept and "Connect to Wi-Fi first" shows. The tiles do
    nothing while an AirPlay session plays.
  - The stock Playback Settings tile opens the Playback Settings page above, and is dimmed while
    you are on it or on its Volume & Sound and Output pages.

### Buttons & Power

- **Button Lock**: Off, Lock Volume Only, Lock Buttons Only or Lock Volume & Buttons, only while
  the screen is off. The same setting as the Control Center key-lock tile.
- **Tap to Wake**: touch the screen to wake it; the touch panel decides whether one or two taps.
- **Auto-Standby** (after 5 minutes with nothing playing) and **Auto-Shutdown** (Off, 1, 3, 5 or
  10 minutes with nothing playing). Only one of the two can be on.
- **Car Mode**: the last track resumes at start, Auto-Standby and Auto-Shutdown do not run, and USB
  connections are ignored.

### Battery

- **Battery Percentage**, off by default: the exact charge beside the battery icon, in the status
  bar and on the lock screen.
- **Charge Limit**: stop charging at 80, 85, 90 or 95 % while the player is on, and resume about
  5 % lower. 100 % (the default) is no limit. A switched-off player charges fully.
- **Battery History** (shows On or Off) opens its own page. Its switch is off by default: it keeps
  the last 24 hours of battery level and use on the player, and turning it off deletes them. While
  it is on, the charts appear under the switch (the first 15 minutes show a short note instead):
  - **Since Last Charge** (first, once the charger has been unplugged with the history on): when it
    was unplugged and the level then, the total time on battery since (it can be longer than a
    day), the level now, and a bar split into **Screen On**, **Playing, Screen Off** and
    **Standby**, with the time of each. The three never overlap; idle time counts as Standby.
    The counters stand still while the charger is connected.
  - **Last 24 Hours**: a bar for every half hour: grey, green while charging, red at 20 % or
    less; no bar where nothing was recorded.
  - **Activity**: a stacked bar for every hour (screen on in light grey, playing with the screen
    off in mid grey), with a faint band behind the hours on the charger.
  - **On Battery**: for Screen On, Playing, Screen Off and Standby, how long and about how much
    of the battery it used (for example "~12%"), estimated from the battery gauge's whole
    percents. Time on the charger is left out.

### Developer

- **Startup**: Boot to M1+ Music, or Open Shanling Home.
- **Tools**:
  - **Screenshot**: see [Screenshot](#screenshot).
  - **Cache**: cover counts (cached, missing, stale) and current work, artist photo counts (with
    and without a photo), and Track Durations with **Clear Track Durations**. **Clear Cover
    Cache** asks first, then Home rebuilds the covers; artist photos are kept.
  - **Settings Files**: tap a file to delete it. **Unsupported Files** removes leftovers of older
    builds.
- **Reset**: Reset All Settings.

### Covers

Home builds missing album covers, and measures track lengths, in the background. A pill at the top
of Home shows the progress and a sync icon shows in the status bar; the pill's **×** stops it
until the next restart. Nothing is scanned when the library has not changed, and an album whose
cover hangs the build is skipped. **Rebuild Covers** asks first, then rebuilds every cover the same
way.

### Software Update

Settings → General → Software Update, the row under About; needs Wi-Fi. **Check for Update**, then
**Download and Install**; **Release Notes** shows what changed. A dialog asks first: about 55 MB,
replacing the card's `update.bin`, with 110 MB of free card space needed. A popup shows the
progress and **Cancel** (Back cancels too, and the card's old `update.bin` stays). When the download
is complete, the firmware's own TF card update takes over with its confirmation, battery check and
checksums. If you say No there, the page offers **Install** again and **Check Again**.

### Screenshot

Asks first, with a 5 s or 10 s delay on its buttons. Leave the page during the countdown to capture
another screen, or cancel. Pictures are saved in the card's `screenshots` folder.

## Equalizer

**Settings → Playback → EQ** opens the Equalizer. Its switch turns the EQ on or off; off, playback
is unchanged. The EQ works at every sample rate and on every output; DSD plays without it.
While the switch is on, the status bar shows **EQ** after the volume.

Headphones, Line Out and a USB DAC each keep their own EQ (on or off, and what plays), and it
switches by itself when the output changes. The grey line under the switch names the output you
are setting.

Tap **10-Band EQ** or a preset in the list to play it. Below the list:

- **Edit 10-Band EQ:** drag anywhere in a band's column to set it (±12 dB in 0.5 dB steps); the
  graph and the sound follow. **Curve** picks Flat, a genre curve or Custom (moving a slider on a
  genre curve copies it into Custom). **Preamp** is Auto, which lowers the level by the largest
  boost to prevent distortion, or a fixed cut. **Reset** returns to Flat. **Save as Preset** saves
  the curve as a preset file.
- **Presets:** **Download from AutoEq** searches the AutoEq database by headphone name (with
  Wi-Fi); tap a result to save its correction, then tap it again to use it. Your presets are
  listed under AutoEq and On Card. Open one to see its curve and bands; tap a band to change its
  type, frequency, gain or Q (the values can be typed on a number keypad). Leaving with unsaved
  changes asks whether to **Save**, **Save As New…** or **Don't Save**. **Delete Preset** removes the file.

Presets are Equalizer APO / AutoEq parametric `.txt` files in the `EQ` folder on the card (up to
64; `Preamp`, `Channel` and `Filter` lines with peak and shelf filters), so you can also copy your
own there.

## Extras

**Radio** (Settings > Main Menu shows it) plays internet stations: My Stations (your saved list), Recently Played and,
with Wi-Fi, Radio Browser: the Top Stations, countries, genres and a name search of radio-browser.info. Tap a station to play it; the `...` on
Radio Now Playing adds it to or removes it from My Stations. The Radio Now Playing page shows the song, the stream and previous/next along the list; local
music stops the radio. Stations play over Bluetooth too. Stations are `Radio/favourites.m3u` on the card; the `...` on the My Stations page has Import from Card, which adds the stations of
every other `.m3u`, `.m3u8` or `.pls` in `Radio/` that are not there yet (your files are never changed).

**Subsonic** (main menu Extras > Subsonic) plays from a Subsonic-compatible server such as Navidrome, Gonic or Airsonic. Tap **Add Server** and enter the server address (start it with `http://` or `https://`; a port and a subpath are fine), your username and your password, then tap **Sign In** (the password itself is not kept on the card, only a sign-in token for that server). A line under the card says what went wrong: "Incorrect username or password", "Can't connect to the server", or a certificate error. A certificate that is not trusted (a self-signed server) is not supported; on a home network use `http://`. To change the address or the name later, leave the password field empty and the saved sign-in is kept. The token is stored on the card (`.m1plus/subsonic.conf`) and opens the server like the password does, so make a dedicated server account for the device.
The root page's status line under the title reads **Synced** (with its age), **Syncing…**, **Updating library…**, **Loading covers…**, **Loading artist images…** (the library keeps filling in the background; you can browse meanwhile) or **Not Connected**; while songs download it reads **Downloading 12 songs**, and **12 downloads waiting** when they wait for Wi-Fi. The six rows are Albums, Artists, Songs, Playlists, Favorites and Downloaded. The `...` card has **Sync Now** and **Server Settings** (server, username, password, Sync Now and Sign Out); the magnifier searches the server. Tap a song to stream the original file (nothing is transcoded). DSD files do not stream: tapping one asks **Download to Play?**.
**Folders** (after Playlists on the Subsonic page) browses the server's own folder tree: tap a folder to go in, Back to go up where you were. With one music folder the first level is an A-Z index with the rail; with several, it lists the music folders first. Folders and artists show their cover when the server has one, otherwise a folder glyph. A level that holds songs has Play and Shuffle; tap a song to play the level from there, or use its `...` sheet. Levels show what was loaded last time at once and refresh in the background.

A server album's page has a `...` with **Download Album**, which queues every track not yet on the card (one message tells how many). A song's `...` sheet has Play Next, Play After, Download, Favorite and Get Info. Favorites are the server's own stars and stay in sync with it. Downloads go to `Subsonic/<artist>/<album>/` on the card (files named by track number and title), one at a time, and show up in the local library as well, like music you copied. A small ring shows progress and Cancel Download or Remove Download from the sheet stops it or deletes the file. The waiting downloads are kept on the card: when Wi-Fi drops or the device restarts they wait, and they go on when you open the Subsonic page with Wi-Fi up (a download that stopped half-way resumes where it was). **Downloaded** lists them and works offline; while songs are still to come they are at its top under **Downloading** (the one that runs first, then the ones that wait, in order), and **Clear** beside that title cancels them all (the finished downloads stay; one song is cancelled from its `...` sheet). It works also after **Sign Out**, which keeps the downloads and clears only the server's cache. Without Wi-Fi, songs that are not downloaded are dimmed. A song you play for half its length (or four minutes) is reported to the server as played, so its play count there, and Last.fm or ListenBrainz if the server is linked to them, stay up to date; this needs Wi-Fi while the song plays.
Limits: the Songs list shows the first 10,000 songs, a play queue holds the list in its order, up to 500 songs (from the one you tapped when the list is longer), and a playlist or favourites list up to 3,000 songs.

**Cassette Mode** is a landscape Now Playing screen. Tap the cassette to pause/resume and the
top-left screw to close. The status line shows the format (FLAC 24/96, MP3 320, DSD64). Change its
theme under Settings → Now Playing, where **Idle Display** can also open it (or Vinyl Mode, VU Meter Mode, or the
lyrics page) after 10 idle seconds on Now Playing. Scrolling the lyrics on Now Playing counts as
activity: the 10 seconds start once the lyrics return to the current line.

**Lyrics Mode** (**…** → Display Mode → Lyrics Mode, or Settings → Now Playing → Idle Display → Lyrics after 10 idle seconds) fills the screen (no status bar) with the cover, title and
artist over the synchronized lyrics. Tap anywhere to close it, drag to browse
the lyrics (they come back to the current line after 3 seconds). The text size follows **Lyrics Text
Size**. For a track without lyrics the Lyrics Mode row is dimmed, and the idle display opens the Album Cover page instead.

**Vinyl Mode** is a turntable Now Playing screen: the cover turns as the record's label while
playing. Tap the record or the large key to pause/resume, the side keys to skip, the top-left
chevron to close.

**VU Meter Mode** (**…** → Display Mode → VU Meter Mode, or Settings → Now Playing → Idle Display → VU
Meter after 10 idle seconds) is a portrait screen with two needle VU meters, left above right, that
follow the music: the needles swing with the level of what is being played, and each PEAK lamp lights
for a moment when that channel peaks well above the 0 VU mark or reaches digital full scale. The 0 VU
mark follows the music on its own (like someone setting the record level), so a loud modern master
settles around -3 VU within a few seconds instead of sitting on the stop, and a quiet one rises to the
same place over about half a minute; both needles share it, so left and right keep their relation. The keys play/pause and skip; tap above them
to pause/resume and the top-left chevron to close (when the idle display opened it, that tap
closes it instead). The needles rest while paused, and do not move for DSD.

**Cover & Lyrics** (Now Playing > ... > More > Cover & Lyrics, needs Wi-Fi) looks up the playing album's covers
(iTunes, then Deezer) and its lyrics (LRCLIB). Tap a cover to use it for the album everywhere; Save Lyrics writes
`<song>.lrc` next to the song (Replace Lyrics when one is there) and the playing song shows them at once.

**Pod** opens a virtual iPod. Slide around the wheel to browse and tap its centre to select.
Tap MENU to go back; hold it to return to the Pod's main menu, then tap it to close.
The bottom button pauses/resumes; the side buttons skip tracks. The wheel does not seek
or change volume on its Now Playing screen.

**Podcasts** reads local episodes from `Podcasts/<Show>/` on the card (up to 100 shows). The page shows the 10 most recently updated shows; with more, **See All (N)** under them opens the list of every show. Open a show, then an
episode; its button offers Play or Download. The grey line over an episode's title gives its date and its length (a downloaded episode's length is on its Play button instead); the episode's own page gives the date, the length and the size. The Podcasts page's **…** menu has **Refresh All** (it shows when any show has a feed; its grey value is how long ago the shows were refreshed) and, with a subscriptions or OPML file on the card, **Import from Card**; the grey line under the page title only tells when the last refresh was (or **Refreshing 2/5…** while one runs). A show that was refreshed before keeps its **Updated …** line under its cover when a refresh fails (the reason is shown briefly); one never refreshed shows the reason. Use an episode's **…** menu to mark it played
or unplayed. A show's **…** menu has **Episode Order**: **Newest First** (the default) or **Oldest First**, the order of its list and of the queue that follows the episode you start (Oldest First suits a series); a tap switches it. **Filter** (also in the **…** menu) hides what you do not need on a long list: **All**, **Unplayed** (every episode not marked played, a half-played one included) or **Downloaded** (the ones on the card); each tap goes to the next. The list keeps the show's order and everything on the page (a tap, Select Episodes, Mark All as Played, Delete, the queue after the episode you start) works on the rows that are shown; with nothing to show it says **No unplayed episodes** or **No downloaded episodes** and the **…** menu is there to switch back. An episode you mark as played stays in the list until it is made again (a filter change, a refresh or a finished download). The Filter is not saved: opening another show, or going back to Podcasts, starts at All; the episode page and Now Playing keep it. The Latest Episode button, the search in the show and Continue Listening ignore it. The **Downloaded** row on the Podcasts page opens the list of what is downloading and what is on the card; while something is downloading and something is on the card, the downloads come first under an **In Progress** header and the downloaded episodes follow (with one kind alone the list simply follows the title). A download that runs or waits has a small ring before its line (the arc shows the progress, a square inside it means it is running) with the percentage beside it; a tap on the row pauses it (the part already loaded is kept) and another tap resumes it. Each of these rows has a **…** with **Pause**, **Resume** or **Retry** (by its state) and **Cancel Download**, which stops the download and deletes the part already loaded, without asking. A download keeps going while you search, refresh, browse Discover, look up a cover or check for an update. A show's page lists its 20 most recent episodes; the last row, **See All**, opens a page with every episode (the show's name at the top, **Back** returns to where you were on the show's page; the page has the same episodes, buttons, Select Episodes, Mark All as Played, Episode Order and Filter, which are the show's own). A subscription keeps only its newest episodes at first: the first tap on **See All** fetches the show's feed again (Wi-Fi needed) and opens the page when it has arrived, with every episode the feed has, up to 2000. The row counts the episodes as they arrive (**Loading… 340**) with a small spinner turning beside it (also on **Search All Episodes** while it loads); if the fetch fails it says why and **Tap to Retry** (for example **Can't connect · Tap to Retry**). Going to another page of Podcasts lets it carry on (the page does not open then; **See All (93)** is there next time); closing Podcasts stops it. Once the episodes are fetched the row reads **See All (93)**, the number of episodes, and a tap opens the page at once; a refresh adds the new episodes to that list. A show of copied files with more than 20 episodes has **See All (N)** too. Downloads, played marks and the queue work on those as on any episode; downloaded old episodes also show on the show's page. To find one episode of a show, tap the magnifier at the top right of its page and type: the list follows the typing (letters and spaces match anywhere in the title, a number such as 37 matches Ep 37 and not 137, Chinese titles match by the initials of their pinyin), a tap opens the episode and Back returns to the results, and playing queues the show's own order from that episode. The search covers every episode once they are fetched. For a subscription that has not fetched every episode yet, the results end with **Search All Episodes**: a tap does what the first **See All** does (the row reads **Loading…** and the count; typing and opening results go on meanwhile), and when the list arrives the same search shows the matches among all of them. To find shows online, connect to Wi-Fi, then use the **Discover** row on the Podcasts page (on unless **Settings → Library → Podcasts → Podcast Discover** is off): the top 25 shows and top 25 episodes of your region (**Settings → Library → Podcasts → Podcast Region**, Automatic by default), the magnifier to search (the Podcasts page's globe opens the same search directly), and **Subscribe** on a show's preview.

**Wi-Fi Transfer:** open **Settings → Network Services → Wi-Fi Transfer** (Wi-Fi must be connected). Playback is paused while the page is open; open the address the page shows (an IP address and port 8888)
in a browser on the same network, and leave the page to turn Wi-Fi Transfer off. The same page has the **AirPlay** and **DLNA** switches. M1+ Music replaces the stock page: it lists the whole card: sort, filter, select files to
download, rename, move or delete, create folders, and upload files or folders (drag them onto the
page). The eye button in the header shows hidden files.

**Audiobooks** (Extras > Library) reads `Audiobooks/` on the card: a folder for each book with its parts as audio files, or a single audio file. The page is laid out like Podcasts: **Continue Listening** (the book in progress you played last; a tap resumes it), the **Books** header over a row for each book (`Part 14 of 41 · 33%`, `42%` for one file, `Finished`, `Not started · 12 parts`), then the **Discover** header over the **LibriVox** row (grey line `Public domain audiobooks`). With more than 20 books the list ends in **See All (N)**, which opens the complete list. Tap a book to see its parts and the white button at the top: **Play** (not started), **Resume** (picks up where you stopped, in the part you were in) or **Play Again** (every part played); tap a part to play from it to the end; the **...** at the top right opens **Playback Speed** (a tap cycles 1x, 1.25x, 1.5x, 2x). A book's cover is `cover.jpg` or `folder.jpg` in its folder; without one, the picture embedded in the book's first file is used, else any picture in that file's folder (it appears a moment after the page first shows the book). A very long single `.m4b` or `.m4a` can stall the player, so such a book is refused with a message: split it into parts (chapters) first. **LibriVox** (the Library's last row) finds free public-domain audiobooks: its page has the large title LibriVox over the list of Popular books, and the search is behind the magnifier at the top right (it opens the keyboard on an empty field; Back returns to Popular where you were); a tap on a book shows its parts (a part's length is in minutes, `19m`; a whole book from an hour reads hours, `18h 28m`), **Download** copies the book into `Audiobooks/` (as a folder with its cover, where the Library lists it like any of your own). The book's page lists every part of the book from the start; the ones not downloaded yet show their length and size, the one being fetched shows its progress ring and percent (the book's row in the Library has the ring and `Part 13 of 37`), and a tap on a part that is not there yet starts the download. For a book with no part yet the white button is **Pause** while it downloads, then **Resume** (or **Retry** after a failure); once parts are there it says what the download does under the title (`Downloading · Part 13 of 37`, `12 of 37 parts downloaded`, why it stopped). The **...** also has **Pause Download** and **Resume Download**, and **Delete Book**, which asks first and removes the downloaded files (not while that book is playing; a folder with files of yours in it stays). Parts turn into ordinary rows as they arrive, and the ones that have arrived can be played. Several books can be queued: **Download** on a second book while one downloads puts it in line (up to 16 wait; the book shows `Waiting` with the ring, and **Pause** takes it out of the line); the books are fetched one after another, and a failure that would hit every book (no Wi-Fi, a full card) stops the line with the waiting books paused. The part that is playing shows the playing wave before its grey line. You can search, listen and download podcasts while a book downloads. Stay on the Audiobooks (or Podcasts) page while it downloads: with the page closed the player may go to sleep and the download stops (tap a part or Resume to continue). Your own folders work as before. While a part plays, Now Playing has no play mode button (a book plays its parts in order) and its **…** opens with Display Mode and More only. Books stay out of Library, Shuffle, Recently Played and Daily Mix; details in [audiobooks](modules/audiobooks.md).

**Search** opens the same library search as the Songs page's Search button. It is hidden from
the main menu by default.

**Scrobbling** (off by default; turn it on in **Settings → Library → Scrobbling**, whose page holds all the scrobbling settings; the row on the Library page says On or Off): every song you listen to
(half of it, or 4 minutes) is added to `.scrobbler.log` at the root of the card. Upload it to Last.fm or ListenBrainz from a computer with any
`.scrobbler.log` uploader, or send it to ListenBrainz and Last.fm from the player (below). Songs played only while a stock Shanling screen is open may be missed; see [details](modules/scrobble.md).

**ListenBrainz and Last.fm**: the player can send the log to your ListenBrainz account, your Last.fm account, or both, over Wi-Fi.
You sign in with one plain text file on the card; nothing is typed on the player.

1. On a computer, make a plain text file named `scrobble.ini` at the root of the card. Put in the section of each service you use:

   ```
   [LISTENBRAINZ]
   TOKEN=0f8fad5b-d9cb-469f-a165-70867728950e

   [LASTFM]
   USER=your-user-name
   PASSWORD=your-password
   API_KEY=0123456789abcdef0123456789abcdef
   API_SECRET=fedcba9876543210fedcba9876543210
   ```

   - **ListenBrainz**: sign in at listenbrainz.org, open your settings and copy the **User token** (36 letters, digits and dashes) after `TOKEN=`.
   - **Last.fm**: your user name and password, and an API key and secret of your own: create an API account at last.fm/api
     (any name will do) and copy the two values it shows. All four lines are needed.

   One value a line, nothing else on the line, no quotes. Capitals, spaces around `=`, Windows line ends and comment lines
   starting with `;` or `#` are all fine; keep the file small (under 4 KB) and saved as plain text (UTF-8).
2. Put the card back and open **Settings → Library → Scrobbling**. No restart is needed: the player reads the file whenever that page opens
   and before every upload. With Wi-Fi connected the accounts are checked at once, and the **ListenBrainz** and **Last.fm** rows
   show your user names. "Not Set" means the player found no complete account in the file; "Invalid Token" (ListenBrainz) or
   "Sign-in Failed" (Last.fm) means the service refused it: correct the file. Each row opens a page with the account's state and a
   reminder of what goes in the file.
3. Tap **Upload Scrobbles** whenever you want to send the log. It goes to every service that is set up. It needs Wi-Fi, and the
   card must not be in use by a computer over USB. A message tells how many listens were sent. The Scrobbling switch does not
   have to be on for this: with it off, the account rows, Auto Upload and Upload Scrobbles still work, so a log already on the card can be sent.
4. Or turn on **Auto Upload** (above Upload Scrobbles, off by default) and the player sends the log by itself: while music plays
   and Wi-Fi is connected, about ten minutes after a new listen was logged, so an album goes up in one or two uploads. It works in
   the background and shows no message; it never switches Wi-Fi on, and without a connection the listens simply wait for the next
   time you play music on Wi-Fi. It needs an account and the Scrobbling switch on (only songs logged since the player was switched
   on start it; older ones in the log go along). A service that refuses its account is left out until you correct the file. After
   an upload that failed the player waits half an hour before it tries again. Upload Scrobbles still works at any time; while an
   automatic upload runs it answers "Already uploading".

The file is the only place the player keeps your sign-in, so it travels with the card, and anyone who has the card can read it.
To sign out, delete the service's lines (or the whole file) on a computer. The player never shows the token or the password and
changes only one thing in the file: it adds a `USER` line under `[LISTENBRAINZ]` with your user name once ListenBrainz has
confirmed the token.

Listens that were sent leave `.scrobbler.log` and are kept in `.scrobbler.log.sent` on the card. With two services a listen
leaves the log once both have answered for it; if one of them cannot be reached the listens wait and go to both again next time
(neither counts a listen twice). A listen every service refuses for good is moved to `.scrobbler.log.rejected`, where you can
look at it. If an upload fails, what was not sent stays in the log for the next try.

For a missing feature, enable it through **Settings → Home Screen → Main Menu**, or find it under Extras.
