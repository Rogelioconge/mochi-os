# Contributing to Mochi OS

Thanks for your interest! Mochi OS is an experimental alternative firmware project for the Shanling M1 Plus.

## Good first contributions

- Improve accessibility and typography at **320 × 480**.
- Add host-side tests for the waveform renderer, track changes, seeking and silence.
- Inspect the AWTK resource generator for name and event compatibility.
- Document firmware behaviors with reproducible evidence and hardware version.
- Improve Spanish/English documentation.

## Before sending a pull request

1. Open an issue with the goal, impact and test plan for any hardware-facing change.
2. Work in a branch (`git switch -c feature/description`).
3. Keep commits small, focused and documented. Explain why addresses, hooks and event assumptions are safe.
4. Run `python3 -m unittest discover -s test -p 'test_mochi_waveform.py' -v`. If the full M1 Plus toolchain is available, also run the project's native lint/tests; see `docs/DEVELOPMENT.md`.
5. Include screenshots at native resolution for visual changes and explain whether they're mockups, AWTK captures or device photos.
6. Never commit official firmware ZIPs, extracted proprietary binaries, generated `update.bin`, private music files, tokens, credentials or unlicensed cover art.
7. State device-test status separately from emulator/host tests. **No unverified hardware flash instructions in PRs.**

## Reviews and respect

Please be constructive, avoid personal attacks and respect licensing and contributor credit. The maintainers may decline changes that add needless UI complexity, compromise responsiveness or increase brick risk.

## Prior art

Preserve original copyright and attribution of reused M1+ Music / other third-party code. Do not use the project to redistribute copyrighted music or private firmware dumps. See `docs/CREDITS.md`.
