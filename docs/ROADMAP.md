# Roadmap (tentative, not promised release dates)

## Stage A — public development home

- [x] Project identity, initial documentation and contribution templates.
- [x] Host-side 64-bar waveform analyzer for real WAV/FLAC and native C renderer with tests.
- [ ] Publish source in its own GitHub repository with existing author history and license intact.
- [ ] Confirm current local sources versus upstream M1+ Music version and record base commit.

## Stage B — first visible native feature

- [ ] Integrate the Mochi Now Playing resource into the current AWTK build.
- [ ] Replace decorative bar profile with per-song intensity data, fall back safely.
- [ ] Real hardware test on M1 Plus: play, pause, seek, track change and cleanup.

## Stage C — independent user experience

- [ ] Flat-color UI with official accent presets including Tejano recolor.
- [ ] Minimalist library, song/album views and Cover Flow.
- [ ] Keep PEQ and AutoEQ fully usable without unnecessary menus.
- [ ] Hide Pod Mode and audit unused features before removal.

## Stage D — firmware identity and safety

- [ ] Make Mochi music-first interface the normal launcher.
- [ ] Restore previous song's cover and seek position without unintended auto-play.
- [ ] Integrate original boot/shutdown assets when available and licensed.
- [ ] Validate device recovery and the flash/upgrade path.
- [ ] Only then consider a signed/verified public preview release with checksums.
