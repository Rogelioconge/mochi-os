#!/usr/bin/env python3
"""Add the MOX cosmetic Home stage after mod_theme, with guarded textual edit."""
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    assert (root / "tools/mod_mox_home.py").is_file(), "Missing tools/mod_mox_home.py"
    assert (root / "tools/mod_mox_stage.py").is_file(), "Missing tools/mod_mox_stage.py"
    p = root / "tools/build.py"
    src = p.read_text(encoding="utf-8")
    before = "STEPS = [('mod_theme', []), ('mod_lists', []),"
    after = "STEPS = [('mod_theme', []), ('mod_mox_stage', []), ('mod_lists', []),"
    if after in src:
        raise SystemExit("MOX Home stage already enabled: no changes")
    if src.count(before) != 1:
        raise SystemExit("Unexpected build.py structure; no changes")
    p.write_text(src.replace(before, after, 1), encoding="utf-8")
    print("MOX: mod_mox_stage added immediately after mod_theme")
    print("Only cosmetic Home resource changes; native launcher removal NOT enabled")


if __name__ == "__main__":
    main()
