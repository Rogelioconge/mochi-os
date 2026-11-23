from __future__ import annotations

import ctypes
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from player_ui import build, flat_surface, THEMES
from wave import BAR_COUNT, BAR_WIDTH, BAR_GAP, segments

class TestWave(unittest.TestCase):
    def test_geometry_and_progress(self):
        bars = segments(32, 362, 15, 60)
        self.assertEqual(len(bars), BAR_COUNT)
        self.assertEqual(sum(b.active for b in bars), 16)
        self.assertEqual(bars[0].x, 32)
        self.assertEqual(bars[-1].x, 32 + (BAR_COUNT - 1) * (BAR_WIDTH + BAR_GAP))
        self.assertTrue(all(4 <= b.h <= 16 and b.w == 2 for b in bars))
    def test_edge_cases(self):
        self.assertFalse(any(b.active for b in segments(0, 0, -4, 100)))
        self.assertFalse(any(b.active for b in segments(0, 0, 1, 0)))
        self.assertTrue(all(b.active for b in segments(0, 0, 1000, 1)))
    def test_host_c_renderer(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d) / "wave.so"
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", str(HERE / "mochi_wave.c"), "-o", str(lib)], check=True)
            dll = ctypes.CDLL(str(lib))
            cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
            dll.mochi_wave_draw.argtypes = [ctypes.c_int] * 4 + [cb, ctypes.c_void_p]
            events = []
            painter = cb(lambda ctx, x, y, w, h, a: events.append((x, y, w, h, a)))
            dll.mochi_wave_draw(32, 362, 15, 60, painter, None)
            expected = [(b.x,b.y,b.w,b.h,int(b.active)) for b in segments(32,362,15,60)]
            self.assertEqual(events, expected)
            events.clear()
            dll.mochi_wave_draw(32, 362, 1000, 1, painter, None)
            self.assertEqual(sum(e[-1] for e in events), 64)
    def test_ui(self):
        src = (ROOT / "stock_playing_page.bin").read_bytes()
        output = build(src)
        self.assertGreater(len(output), len(src))
        self.assertEqual(build(src), output)
        import awtk_ui
        w = awtk_ui.parse(output)
        self.assertIsNotNone(w.find("mochi_wave"))
        self.assertIsNotNone(w.find("slider_play"))
        self.assertIsNotNone(w.find("btn_prev"))
        self.assertEqual(w.find("img_np_tint").get("image"), "mochi_surface")
        self.assertEqual(w.find("slider_play").get("sensitive"), None)
    def test_palette(self):
        self.assertEqual(len(THEMES), 6)
        self.assertEqual(flat_surface().getpixel((10, 10)), (18,20,23,255))

if __name__ == "__main__":
    unittest.main(verbosity=2)
