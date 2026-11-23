# Publish Mochi OS on GitHub — initial setup

**Do this from the most recent local working repository on your Mac.** Do not replace it with a stale snapshot from a chat ZIP. First create a **public, empty** `mochi-os` repository in your GitHub account. Do not initialize with README, license or `.gitignore`, since the local source tree already has Git history.

## 1. Apply the documentation / source overlay

```bash
cd ~/Documents/M1Plus/MOX-OS
python3 "/path/to/unzipped/Mochi-OS-GitHub-Starter/scripts/apply_starter.py" --repo . --dry-run
python3 "/path/to/unzipped/Mochi-OS-GitHub-Starter/scripts/apply_starter.py" --repo . --apply
```

The script backs up an existing README, refuses to silently overwrite non-README files and appends protective ignore patterns. It does not touch firmware inputs or perform any flash operation.

## 2. Inspect before committing

```bash
git status --short
git remote -v
git ls-files | grep -Ei '(firmware/|update\.bin|\.env|\.flac$|\.mp3$|\.key$)' || true
python3 scripts/preflight_public.py
```

Review all findings, and consider the existing Git history: even deleted binary secrets can survive in old commits. If a problematic file was ever committed, scrub the history **before** pushing public.

## 3. Create the first Mochi commit

```bash
git add README.md CONTRIBUTING.md SECURITY.md docs/ tools/mochi_waveform.py test/test_mochi_waveform.py prototypes/mochi_player .github scripts/preflight_public.py .gitignore
git diff --cached --stat
git commit -m "docs: establish Mochi OS project and waveform prototype"
```

Confirm that the staged files are only intentional source/documentation; never use blind `git add .` for the first publication.

## 4. Publish

```bash
git remote add mochi https://github.com/Rogelioconge/mochi-os.git
git push -u mochi HEAD:main
```

This does not change an existing `origin` remote and publishes the current checked-out branch to `main` of the new empty repository. If `mochi` already exists, inspect `git remote -v` rather than re-adding it. Authentication may request a Git credential manager/login.

## 5. After publication

In GitHub Settings → General, confirm the default branch is `main`. In Settings, enable Issues, Discussions if wanted, and consider private vulnerability reporting and repository rules. Add topic tags `shanling`, `m1-plus`, `firmware`, `awtk`, `audio-player`, and `mochi-os`. Never enable automatic firmware flashing from CI.

## Common errors

- `repository not found`: the empty GitHub repository hasn't been created, or authentication lacks access.
- `remote mochi already exists`: keep it and inspect `git remote -v`.
- `non-fast-forward`: the GitHub repo was initialized with README; inspect both histories before reconciling. Don't force-push blindly.
- `working tree clean`: check whether overlay files were actually applied in the expected repo.
