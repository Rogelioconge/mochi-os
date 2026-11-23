"""First distinct Mochi OS AWTK Now Playing resource (development-only).

Builds from the tested imfing adaptation for the Shanling M1 Plus, preserving
stock control names and their callbacks. It does not patch a bootable firmware.
The generated opaque background and waveform decoration are in separate assets.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import awtk_ui  # noqa: E402
import mod_nowplaying as np  # noqa: E402

WIDTH, WINDOW_HEIGHT = 320, 450
BG = "#121417"
TEXT = "#F4F4F1"
SECONDARY = "#9EA3AA"
ACCENT = "#C1D4CF"  # pale jade / muted teal as a restrained default
THEMES = {
    "Grafito": "#D0D4D7",
    "Jade": ACCENT,
    "Azul": "#A5C5E8",
    "Violeta": "#C4B2DF",
    "Coral": "#DDAF9F",
    "Ámbar": "#D9C398",
}


def build(src: bytes) -> bytes:
    root = awtk_ui.parse(src)
    if root.name != "playing_page":
        raise ValueError("Expected unmodified stock playing_page.bin")
    if awtk_ui.serialize(root) != src:
        raise ValueError("AWTK bytes must round-trip exactly")
    np.apply_ui(root)  # Proven widget names, stock MIPS control hookup remains intact.

    root.set("style:normal:bg_color", BG)
    local = np.find(root, "view_local")
    surface = np.find(root, "img_np_tint")
    surface.set("image", "mochi_surface")
    assert local.children[0] is surface

    # Flat, centered music-first typography. Preserve the stock action buttons,
    # moving Fav and More to the top edges instead of crowding the song title.
    title = np.find(root, "scrlabel_title")
    artist = np.find(root, "scrlabel_artist")
    np.move(title, 28, 305, 264, 24)
    np.move(artist, 28, 330, 264, 22)
    np.text_style(title, 20, TEXT, "center")
    np.text_style(artist, 16, SECONDARY, "center")
    np.move(np.find(root, "btn_fav"), 0, 0, 44, 44)
    np.move(np.find(root, "btn_more"), 276, 0, 44, 44)

    slider = np.find(root, "slider_play")
    # Hide the stock solid track, but *keep* its 264x30 hitbox and stock seek
    # behavior. The future AWTK paint hook draws the waveform visual above it.
    for state in np.BTN_STATES:
        slider.set(f"style:{state}:bg_color", "#00000000")
        slider.set(f"style:{state}:fg_color", "#00000000")
    parent = np.parent_of(root, slider)
    assert parent is local
    wave = awtk_ui.Widget(
        "view", 32, 350, 256, 24,
        [("name", "mochi_wave"), ("sensitive", "false"), ("clickable", "false")]
    )
    # The decoration must be after the slider in paint order but never intercepts taps.
    parent.children.insert(parent.children.index(slider) + 1, wave)

    # Retain native touch targets; source title+artist positions are intentionally
    # changed, so test hitboxes rather than old text geometry.
    np.check_touch(root)
    found = [w for w in root.walk() if w.name == "mochi_wave"]
    assert len(found) == 1 and wave.get("sensitive") == "false"
    assert np.find(root, "img_playcover").w == np.ART
    result = awtk_ui.serialize(root)
    assert awtk_ui.serialize(awtk_ui.parse(result)) == result
    return result


def flat_surface():
    from PIL import Image
    return Image.new("RGBA", (WIDTH, WINDOW_HEIGHT), (*bytes.fromhex(BG[1:]), 255))
