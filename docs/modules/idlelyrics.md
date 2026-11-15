# Idle lyrics page

**Sources:** `patch/idlelyrics.c`, `patch/lyrics.c` (`ly_retarget`, `ly_release`),
`patch/minibar.c` (`mb_art_*`), `patch/nowplaying.c` (`np_window`, `np_idle_color`),
`tools/pod_ui.py` `build_idlelyrics_page`, `tools/pod_pages.py` `IDLELYRICS_PAGE`,
`tools/mod_nowplaying.py` (`np_scrim_idle`), `IL_*` in `patch/offsets.inc`. **Tests:**
`test/pod/idlelyrics.py`, `test/pod/lyrics.py`, `LYRICS_PINS` in `tools/pod_pins.py`.
**Preview:** `tools/preview/preview_idlelyrics.py`.

A full-screen page of our own that opens over Now Playing as an Idle Display destination
(Settings > Now Playing > Idle Display > Lyrics, see [bigcover](bigcover.md)). It has an 88 px
header (cover, title, artist, no controls) over the synchronized lyrics, on the Now Playing cover
tone with the light lyrics scrim. It reuses the [lyrics](lyrics.md) engine, retargeted to this
page. No hook of its own: it is opened by hook 24's dispatcher.

## Page

`m1plus_idlelyrics_page` is a fullscreen 320 x 480 window (no status bar) with Now Playing's theme
(`theme=playing_page`, for the engine's lyric styles). Neutral colours only; the window colour is
Now Playing's (`np_idle_color`) and follows the track. In Tinted mode it keeps the cover tone
(`PAL_COVER_IL`, [accent](accent.md)). Children in order:

| Child | Role |
|---|---|
| `img_il_tint`, `img_il_scrim` | Now Playing's gradient and the lyrics scrim (alpha 68, 44-row smoothstep edges); insensitive |
| `il_view` | transparent touch target; paints the cover |
| `il_title` (19 px white), `il_artist` (17 px `#D0D0D0`) | `hscroll_label`s 196 px wide at x 96, y 25 and 49; ellipsis, never scroll |
| `il_lyrics` | the engine's `scroll_view` at (28, 96, 264 x 372) |
| `il_hint` | "No Lyrics Found", 20 px `#AAAAAA`, centred, hidden and insensitive |
| `label_title` | hidden, "Lyrics" |

The cover is the mini bar's `mb_art_*` at 56 px with radius 8 (same album-cache / `/tmp` file /
placeholder-disc source and settle ticks as the Home and lock bars). `il_view`'s `EVT_AFTER_PAINT`
blits it at (28, 20). Nothing is decoded in the paint.

## Behaviour

- **Opened by** `bc_timed_open` (hook 24) when Idle Display is Lyrics and the track has lyric rows
  now (`ly_has_rows()`, the child count of Now Playing's `scroll_lrc`); otherwise stock's Album
  Cover page opens. Also by **Lyrics Mode** on the More sheet's Display Mode page (`pm_on_lyr`,
  [playmore](playmore.md)), which is dimmed for a track without lyric rows. The page is the same
  either way.
- **`idlelyrics_open_idle()`** returns 0 once the page is up or already open, and -1 when it could
  not open, leaving nothing behind. Failures: no Now Playing window or engine, a missing widget, a
  refused destroy listener, `ly_retarget` or timer. After the window exists a failure closes it.
- **Timer.** One page timer (50 ms, then 500 ms). Each tick: the engine's view is still the page's
  (else the page closes once), screen lit, window colour, playing track (`mb_track_key`),
  `ly_tick()`, and the hint shown exactly when the engine reads no rows. A dark screen does no work.
- **Lyrics.** The existing engine, retargeted: anchor at 0.35 x 372 = 130 px, the chosen Lyrics Text
  Size (pitch and gap per [lyrics](lyrics.md) "Text size"). The engine's view height scales the
  anchor, edge fades and offset bound.
- **Touch.** A tap anywhere closes the page; a vertical drag over 10 px browses as on Now Playing and
  returns after 3 s. No tap seeks (`ly.noseek`). Listeners return `RET_OK` and grab nothing, so the
  pull-down and window manager see every drag. Hardware keys keep their stock actions.
- **Closing.** `il_close` calls `window_close(il.win)`, not `navigator_back`: when another page's
  Now Playing button brings the player forward, `np_on_foreground` gives the engine back and the
  tick closes the page while Now Playing is the top window.
- **End.** `EVT_DESTROY` calls `ly_release` (engine back to Now Playing), removes the timer, frees the
  cover bitmap and clears the state. `ly_refresh` also releases.

## Stock fact relied on

Stock rebuilds Now Playing's `scroll_lrc` rows from its 500 ms timer on every tick, even while
another window covers it (`LYRICS_PINS`). A track change under the page therefore shows the hint
until stock rebuilds the rows, at most one stock tick later.

## Constraints

All work is on the UI thread from the page timer and listeners: no new thread, lock, global paint or
main-loop work, and no stock word written. Every failure leaves stock behaviour. Hidden widgets are
also insensitive. The page does not stop the stock screen-off.
