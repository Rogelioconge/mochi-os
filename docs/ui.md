# UI reference

The interface uses a minimal, iPod-inspired style for the 320 × 480 touchscreen. Asset steps
preserve widget names, pin the stock bytes they replace and run in `tools/build.py` order.
Runtime behaviour is documented in [architecture](architecture.md).

`make preview` renders the selected dev artifact without changing it. For a release sheet, use
`tools/preview/preview.py WORKDIR [OUT.png]` (default `out/preview/release-preview.png`). Feature
tools (`preview_icons.py`, `preview_battery.py`, `preview_nowplaying.py`, ...) accept output paths;
use the gitignored `out/preview/`.

Previews are approximate PIL mock-ups with sample data, not AWTK captures. Text uses the built
tree's `default.ttf` via stb_truetype (`tools/preview/preview_font.py`, `tools/stb_raster.py`). See
[workflow](workflow.md) for validation.

## Before changing the UI

Read [UI rules](modules/ui-rules.md), including its text-width model. Reproduce
bugs with an emulation test or device screenshot. Reuse the shared layout/text model in previews
and measure the font from the tree being built.

## References

| Area | Documentation |
|---|---|
| Fonts and theme | [Fonts](modules/fonts.md), [theme](modules/theme.md), [UI rules](modules/ui-rules.md) |
| Navigation | [Menu](modules/menu.md), [settings](modules/settings.md), [navbars](modules/navbar.md) |
| Library | [rows](modules/rows.md), [Albums](modules/albums.md) and its "..." sort card, [album page](modules/album-page.md), [track rows' menu](modules/rowmenu.md), [Get Info](modules/songinfo.md) (preview: `tools/preview/preview_songinfo.py`), [queue](modules/queue.md) (preview: `tools/preview/preview_queue.py`), [Folders](modules/folders.md), [search](modules/search.md) (preview: `tools/preview/preview_search.py`) |
| Playback | [Now Playing](modules/nowplaying.md), [lyrics page](modules/lyrics.md), [More sheet](modules/playmore.md), [Find Cover & Lyrics](modules/onlineart.md), [Software Update](modules/update.md) (preview: `tools/preview/preview_update.py`), [mini player](modules/minibar.md) |
| Home content | [Recently Played](modules/recent.md), [Daily Mix](modules/dailymix.md), [cover build line](modules/homecover.md), [Recently Added albums](modules/recent-albums.md) |
| Extras | [Playlists](modules/playlists.md), [Songs](modules/songs.md), [Podcasts](modules/podcasts.md), [Radio](modules/radio.md), [Cassette Mode](modules/tape.md), [Vinyl Mode](modules/vinyl.md), [VU Meter Mode](modules/vu.md), [virtual iPod](modules/ipod.md), [iPod Cover Flow](modules/ipod-coverflow.md), [Keyboard](modules/keyboard.md), [Tidal Search keyboard](modules/tidalkb.md) |
| System appearance | [Accent and palette](modules/accent.md), [Boot logo/slides](modules/boot.md), [icons](modules/icons.md), [battery](modules/battery.md), [Line Out pill](modules/lineout.md), [pull-down](modules/pulldown.md), [lock screen](modules/lockscreen.md) and wallpaper, [UI rules](modules/ui-rules.md), [dialogs, power-off splash](modules/overlays.md) |
| Languages | [Translation and sizing](modules/i18n.md) |
