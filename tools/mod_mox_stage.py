#!/usr/bin/env python3
"""MOX OS: cosmetic Home asset step for M1+ Music 1.8.0 build pipeline.

Run automatically by tools/build.py after mod_theme, with:
    mod_mox_stage.py WORKDIR WORKDIR

This only changes validated home_page.bin style properties. It does NOT remove
Shanling's launcher, change startup, or claim RAM / touch improvements.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import awtk_ui
import mod_mox_home
from modlib import edit_ui

UI = Path(awtk_ui.RAW) / "ui/home_page.bin"


def apply(source: Path, output: Path) -> tuple[str, str]:
    # This module must operate only on the throwaway build tree already created
    # by the upstream pipeline, never on an extracted pristine stock workdir.
    if source.resolve() != output.resolve():
        raise ValueError("Expected an in-place build step: WORKDIR WORKDIR")
    path = output / UI
    if not path.is_file():
        raise FileNotFoundError(path)

    raw, root = mod_mox_home.read_resource(path)
    idx, _ = mod_mox_home.audit(root)

    # Verify that mod_theme has already applied its expected transformation.
    expectations = {
        ("home_bottomview", "style:normal:bg_color"): "#000000",
        ("home_scrlabel_artist", "style:normal:text_color"): "#AAAAAA",
        ("home_sindicator", "style:normal:selected_fg_color"): "#EEEEEE",
        ("home_sindicator", "style:normal:fg_color"): "#555555",
    }
    for (name, key), expected in expectations.items():
        actual = idx[name].get(key)
        if actual != expected:
            raise ValueError(f"Unexpected input for {name}/{key}: {actual!r} != {expected!r}")

    signature = mod_mox_home.signature(root)
    expected_root = mod_mox_home.transform(root)
    expected_bytes = awtk_ui.serialize(expected_root)
    if expected_bytes == raw:
        raise ValueError("No MOX changes were produced")

    old, new, transformed = edit_ui(str(path), mod_mox_home.transform)
    if old != raw or new != expected_bytes or signature != mod_mox_home.signature(transformed):
        raise AssertionError("MOX stage output is not reproducible")
    if awtk_ui.serialize(awtk_ui.parse(new)) != new:
        raise AssertionError("MOX stage AWTK roundtrip failed")
    print(f"MOX Home: {len(old)} -> {len(new)} bytes; SHA-256 {mod_mox_home.sha(new)}")
    return mod_mox_home.sha(old), mod_mox_home.sha(new)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: mod_mox_stage.py WORKDIR WORKDIR")
    apply(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
