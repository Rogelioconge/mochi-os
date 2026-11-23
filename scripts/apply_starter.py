#!/usr/bin/env python3
"""Non-destructive Mochi OS documentation / waveform overlay installer.

Does not run Git, flash a device or modify build-time stock firmware inputs.
Requires --apply to change anything; default --dry-run.
"""

from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys

SOURCE_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {'.gitignore.mochi', 'README.md'}


def source_files():
    for p in sorted(SOURCE_ROOT.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        rel = p.relative_to(SOURCE_ROOT)
        if str(rel) in EXCLUDE:
            continue
        yield rel, p


def apply(repo: Path, dry_run: bool) -> int:
    if not (repo / '.git').exists():
        print(f'ERROR: {repo} does not contain a .git directory. Use your real local checkout.', file=sys.stderr)
        return 2
    expected = repo / 'Makefile'
    if not expected.is_file():
        print(f'ERROR: {repo} has no Makefile: is this the M1 Plus firmware source checkout?', file=sys.stderr)
        return 2
    changes = 0
    for rel, src in source_files():
        dest = repo / rel
        if dest.is_file():
            if dest.read_bytes() == src.read_bytes():
                print('  OK  ', rel)
            else:
                print('  SKIP (already exists, review manually):', rel)
            continue
        changes += 1
        print('  ADD ', rel)
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    src_readme = SOURCE_ROOT / 'README.md'
    dest_readme = repo / 'README.md'
    if dest_readme.exists() and dest_readme.read_bytes() != src_readme.read_bytes():
        backup_dir = repo / '.mochi-backups'
        backup = backup_dir / ('README-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.md')
        print('  REPLACE README.md (old README backed up to', backup, ')')
        if not dry_run:
            backup_dir.mkdir(exist_ok=True)
            shutil.copy2(dest_readme, backup)
            shutil.copy2(src_readme, dest_readme)
        changes += 1
    elif not dest_readme.exists():
        print('  ADD  README.md')
        if not dry_run:
            shutil.copy2(src_readme, dest_readme)
        changes += 1
    ignore = repo / '.gitignore'
    extras = (SOURCE_ROOT / '.gitignore.mochi').read_text(encoding='utf8').splitlines()
    present = set(ignore.read_text(encoding='utf8').splitlines()) if ignore.exists() else set()
    new_lines = [line for line in extras if line.strip() and not line.lstrip().startswith('#') and line not in present]
    print(f'  .gitignore: append {len(new_lines)} protective patterns')
    if not dry_run and new_lines:
        with ignore.open('a', encoding='utf8') as f:
            f.write('\n# Mochi OS: avoid publishing firmware and personal assets\n')
            f.write('\n'.join(new_lines) + '\n')
    if not dry_run:
        # Keep original README backups outside Git even when .gitignore existed.
        with ignore.open('a', encoding='utf8') as f:
            if '.mochi-backups/' not in (present | set(new_lines)):
                f.write('.mochi-backups/\n')
    print(('DRY RUN ONLY. ' if dry_run else 'APPLIED. ') + f'{changes} new/replaced paths. Inspect git status before committing.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    return apply(args.repo.expanduser().resolve(), not args.apply)


if __name__ == '__main__':
    raise SystemExit(main())
