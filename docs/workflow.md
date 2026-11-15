# Build, test and flash

Run `make help` for common tasks. Direct tools use `uv run python -I tools/<name>.py`.

## Setup

```sh
brew install uv squashfs llvm lld
make setup
cp "M1 Plus Firmware V2.1.zip" firmware/
uv run python -I tools/mod_font.py --fetch
uv run python -I tools/mod_wpa.py --fetch   # hostap sources for the Wi-Fi supplicant ([wifi](modules/wifi.md))
make doctor
```

- Each checkout and worktree runs its own `make setup`: its own uv `.venv` (Python 3.15) and its
  own `work/` and `out/`. Never borrow another checkout's interpreter or write into its outputs.
- Firmware, fonts and a matching stock tree may be read from the main checkout through
  `tools/paths.py`, which resolves read-only inputs.
- Update `pyproject.toml` and `uv.lock` together (`uv sync --locked`).
- Use Homebrew LLVM/LLD (Apple clang lacks MIPS support); override with `LLVM_BIN` / `LLD_BIN`.
- Keep `-I` on Python tools. Never execute code from extracted firmware or a reference clone.
- `make doctor` checks pinned inputs, native tools and Unicorn MIPS execution. SIGILL can mean a
  sandbox forbids native JIT; use an environment that permits it.

## Editing rules

- Run builds and tests in the foreground; never background them and sleep-poll.
- Edit with the editor tool. Use `tools/sub.py --pairs` for checked mechanical replacements,
  `tools/peek.py` for image crops, zooms and diffs, and `tools/stock.py` for stock-tree searches.
- No heredoc scripts, `VAR=value cmd` prefixes or `cd X && ...` chains; use tool flags,
  absolute paths and `git -C`.
- Stage explicit paths, never `-A`. Never commit virtual environments, packages or previews.
- Do not run `ruff format`.
- Start UI fixes with a failing emulation test or device capture. Previews use the shared AWTK
  layout/text model and the built font.

## Development

```sh
make test TEST=albums           # selected tests; comma-separated modules or module/section
make test                      # feature-branch done criterion; no package or goldens
make test PERF=1               # the same plus instruction budgets and stress-scale inputs
make dev                       # fresh dev tag, one tree, full tests and verified package
make preview                   # approximate render of that dev tree
make flash                     # verified SD copy, then eject
make ota                       # push that build to the local update server (make ota-serve; see update)
```

Dev artifacts stay in `out/dev/<tag>/`: `tree/`, `update.bin`, logs and `results.json`.
`tree/build.json` records the tag, inputs, environment and artifact hashes. Tests and packaging
use the same tree; About, the preview and the package use its tag.

- Only a fully passing build becomes `latest`. A failed dev run leaves the previous latest
  selected; pass `BUILD=out/dev/<tag>` to choose another.
- `make flash` verifies the full test receipt, package, target card and read-back hash. It never
  rebuilds. `VOLUME=/Volumes/Name` picks another card; `DRY_RUN=1` checks without copying.
- Dev tags are `V2.1z` plus four checkout-namespace letters and four counter letters. Keep the
  gitignored `.dev-number.json`; never reset the counter or reuse an output directory.
  Collisions, moved worktrees and exhausted counters fail explicitly.
- Release tags are `V2.1-<VERSION>`.
- `JOBS=4` limits workers (default one per CPU, at most 16).
- `make clean` removes `work/check` only.

```sh
uv run python -I tools/check.py --list
uv run python -I tools/check.py --test albums/toggle_tests
uv run python -I tools/check.py --tests-only --jobs 4 --timeout 300
```

Previews: `tools/preview/preview*.py` write to `out/preview/` (gitignored). Generate the release
sheet with `uv run python -I tools/preview/preview.py WORKDIR`.

## Context budget

An audit found cache reads dominate cost, mostly in long sessions and subagents. Keep sessions small:

- Give subagents one stage (probe, implement or test), ending with branch, commit and doc
  handoff; start the next stage fresh.
- One topic per session. Past ~250k context or at a topic change, document conclusions and
  start fresh. Close unused sessions.
- Search large files first, then read relevant ranges. Do not reread unchanged files;
  `docs/history.md` is for people, not agent context.
- Crop and zoom images with `tools/peek.py`, then read once.
- Batch mechanical edits with `tools/sub.py FILE... --pairs PAIRS.json --stat`. Run selected
  tests while iterating and the full suite at completion.

## Formatting and lint

- `make format`, then `make format-check`, for tracked payload C and headers. `.clang-format`
  sets four spaces, attached braces and 120 columns. Select Homebrew clang-format with
  `LLVM_BIN` or `CLANG_FORMAT`. Keep formatting apart from functional changes and verify package
  hashes afterward.
- `make lint` runs pinned Ruff bug and syntax checks without formatting. Test, dev and check
  targets run it first. Star imports are allowed in `test/pod/*.py` and
  `tools/preview/preview_tape.py`.

## Integration and restore

Feature branches leave `VERSION`, goldens and history unchanged. GitHub releases and git tags use
the plain `VERSION` without a `v`; dev About shows the dev tag.

At integration, bump `VERSION` in `tools/build.py` (patch for fixes, minor for features, major by
decision). `TAG = V2.1-<VERSION>` is the package version the updater compares; About shows the
plain `VERSION`. Then run:

```sh
make check                     # both packages and all tests against existing goldens
make accept                    # accept intended changes; reuse complete matching evidence
```

- CHANGED and NEW fail until accepted. Acceptance needs both packages and every test;
  `--no-tests` and `--only` cannot bypass it. Source changes during a run invalidate its evidence.
- Commit the golden; add history only for milestones or device findings. Resolve golden and
  history conflicts from the integration side and rerun.
- Checked packages stay in `work/check/release/out` and `work/check/restore/out`.
- Release and restore copies require golden bytes; dev copies require a full receipt. There is
  no `--force`. `build.py --dev` alone creates no test receipt; use `make dev` to install.
- `--pack-only` rejects stale trees. `--no-cache` supports cold-build comparisons.

Direct builds:

```sh
uv run python -I tools/build.py
uv run python -I tools/build.py --restore
uv run python -I tools/fwtool.py verify out/M1Plus-<tag>-release-update.bin
uv run python -I tools/flash_sd.py out/M1Plus-<tag>-release-update.bin
```

The `V2.1R` restore package (stock images, own tag) is a developer tool. Users restore with
Shanling's official V2.1 ([version](modules/version.md)).

## Publish

After the integration commit and a matching `make check`, `make publish` uploads the golden
release package (as `update.bin`, with `SHA256SUMS`) to a draft GitHub release named `VERSION`,
created with `--target HEAD`. The notes are the golden's last commit message. It downloads the
assets back and compares hashes.

- It creates and pushes no tag: GitHub creates the tag `VERSION` at HEAD when the draft is
  published.
- Review the draft, then `make publish PUBLISH=1` (or publish on GitHub).
- `DRY_RUN=1` checks and stages `out/publish/<VERSION>/` only.
- It refuses a dirty tree, a package that is not the golden, a local tag on another commit and
  an already published release. The restore image stays local.

## Device checks

Follow [Install](install.md) for card preparation, update confirmation and restore, and the
feature's module doc to validate a build. Emulation does not certify hardware timing or
appearance.

**Settings → Developer → Screenshot** asks first, then captures after a delay
([screenshot](modules/screenshot.md)).
With the card mounted:

```sh
uv run python -I tools/pull_shots.py --build latest
uv run python -I tools/peek.py info out/dev/<tag>/device/<capture>.png
```
