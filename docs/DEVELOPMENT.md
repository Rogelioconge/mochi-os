# Development workflow

## Requirements

- macOS Apple Silicon supported by the inherited build pipeline (local MacBook Air M1 workflow).
- Homebrew: `uv`, `squashfs`, `llvm`, `lld` for inherited firmware build.
- For the **host waveform prototype only**: Python 3 and FFmpeg/FFprobe, plus `cc` for one optional test.
- Official stock firmware V2.1 **obtained by the developer separately**; do not commit it.

## Host waveform tests (fast and non-flashing)

```sh
python3 -m unittest discover -s test -p test_mochi_waveform.py -v
python3 tools/mochi_waveform.py "/path/to/track.flac" --out /tmp/waveform.json
```

## Full firmware build (later)

The existing inherited `Makefile`, `uv.lock`, toolchain setup and tests should be preserved from the **most recent local working checkout**, not rebuilt from old ZIP exports. Consult the original project docs and run the inherited `make doctor` / `make test` before attempting a release candidate. The overlay in this starter pack adds only host-level waveform and documentation; it does not claim `make dev` will embed Mochi UI.

## Source control

Work on a feature branch for every major change. PRs should contain a test plan, source baseline reference, visual captures and a warning if device-unverified. Do not commit `update.bin`, worktrees, caches, official firmware inputs, secrets, copyrighted album art or personal audio.

See [GitHub setup](GITHUB-SETUP.md) and [security](../SECURITY.md).
