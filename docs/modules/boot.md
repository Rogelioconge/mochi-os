# Boot logo, quotes, settings slides

**Sources:** `tools/mod_boot.py`, `tools/boot_logo.py`, `assets/boot-logo.svg`.

## Logo

`/etc/init.d/S11logo_display_shell` runs `display_logo` on `images/xx/logo180.jpg` when
`/mnt/data/config.ini` has `ROTATEMODE=1`, else on `logo.jpg`. These are the only splash images.
`display_logo` draws 1:1, so a replacement must be a 320x480 baseline JPEG (`logo180` is `logo`
turned 180 degrees).

`assets/boot-logo.svg` is just the outlined **M1+** wordmark on black, with no product name, so
renaming the launcher does not touch it (q2-pod style). `tools/boot_logo.py` (`brew install
librsvg`) renders it into the committed `assets/boot-logo.jpg` and `boot-logo180.jpg`.
`mod_boot.py` checks both stock files by SHA-256 and each new file's frame header, and keeps
mode 755.

## Quotes

The stock font gives the curly quotes the CJK em advance, so "Paul's" shows a wide gap. The step
can map them to the straight glyphs, but it accepts a non-stock font only if every curly quote is
already mapped and narrower than half an em. With Inter the quotes are proper, so the release
keeps them curly.

## Slides

Every settings window in `ui/systemset/` gets `open_anim_hint` and `close_anim_hint` =
`slide_left(duration=200,easing=cubic_out)` (what the stock lock screen's close hint uses): a page
slides in from the right and back out. `fwupdate_page` and `fwdownload_page` stay stock, the way
back to a known build. There is no switch; a stuck page needs a code change in
`mod_boot.apply_anim`.

## Settings slide safety audit (static, on stock `demo`)

A close animation keeps the window in the stack, visible, until it ends in the main loop (200 ms).
The one hazard is code that pops windows in a loop and expects the stack to change synchronously:
`while (top != X) navigator_back();` would spin and the watchdog would reboot.

The only such loops are Album detail "play from here" and the jump list. Both stop at the first
`playing_page` or `home_page`, and they open only from library pages, the Now Playing "more"
dialog, the Home dispatcher and search, never from settings code. Decision: the slides stay on all
settings windows. The evidence is a static reachability search over stock `demo`, not a device
test.

Behaviour differences without hanging: the folder-scan dialog on the specified-folder page opens
about 200 ms late after Back, two closes or opens within one slide share a pending slot, and the
pull-down to settings slides in while the finger is down.

## Theme at boot

A pinned clamp makes `config_init` read any non-zero `[SYSSET] THEME` as 0, so the `default` theme
always loads and the System page has no Theme row ([theme](theme.md) "theme1 is off"). No payload
code or kill switch is involved.
