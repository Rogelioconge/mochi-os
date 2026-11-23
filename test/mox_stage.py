#!/usr/bin/env python3
"""Isolated tests for MOX cosmetic build-stage contract; no device used."""
from pathlib import Path
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "test"))

import awtk_ui
from mox_home import sample
import mod_mox_stage


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        target = root / mod_mox_stage.UI
        target.parent.mkdir(parents=True)
        tree = sample()
        tree.find("home_bottomview").set("style:normal:bg_color", "#000000")
        tree.find("home_scrlabel_artist").set("style:normal:text_color", "#AAAAAA")
        tree.find("home_sindicator").set("style:normal:selected_fg_color", "#EEEEEE")
        tree.find("home_sindicator").set("style:normal:fg_color", "#555555")
        old = awtk_ui.serialize(tree)
        target.write_bytes(old)
        target.chmod(0o644)
        sh_before, sh_after = mod_mox_stage.apply(root, root)
        result = target.read_bytes()
        assert result != old and sh_before != sh_after
        assert stat.S_IMODE(target.stat().st_mode) == 0o644
        edited = awtk_ui.parse(result)
        assert edited.find("home_bottomview").get("style:normal:bg_color") == "#0B0B0D"
        assert edited.find("home_scrlabel_artist").get("style:normal:text_color") == "#A9A9AF"
        assert len(list(edited.walk())) == len(list(tree.walk()))
        try:
            mod_mox_stage.apply(root, root)
        except ValueError as e:
            assert "Unexpected input" in str(e)
        else:
            raise AssertionError("Second application should fail closed")
        try:
            mod_mox_stage.apply(root, root / "other")
        except ValueError:
            pass
        else:
            raise AssertionError("Different directories should fail closed")
        print("MOX stage: 8/8 isolated checks passed")


if __name__ == "__main__":
    main()
