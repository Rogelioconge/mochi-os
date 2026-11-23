"""Host-only tests for the real-audio amplitude envelope and pure C renderer."""
import ctypes
import importlib.util
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "mochi_waveform.py"
spec = importlib.util.spec_from_file_location("mochi_waveform", MODULE)
mochi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mochi)


class WaveformTests(unittest.TestCase):
    def test_silent_song(self):
        self.assertEqual(mochi.envelope_from_samples([0] * 1000), [0] * 64)

    def test_loudness_changes_heights(self):
        samples = ([100] * 4096) + ([8000] * 4096) + ([0] * 4096) + ([1000] * 4096)
        bars = mochi.envelope_from_samples(samples)
        self.assertGreater(bars[20], bars[2])
        self.assertEqual(bars[33], 0)
        self.assertGreater(bars[54], 0)

    def test_short_audio_and_empty(self):
        self.assertEqual(len(mochi.envelope_from_samples([])), 64)
        self.assertEqual(len(mochi.envelope_from_samples([500])), 64)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
    def test_real_wav_and_flac_decode(self):
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "test.wav"
            flac = Path(td) / "test.flac"
            rate = 8000
            with wave.open(str(audio), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(rate)
                frames = bytearray()
                for i in range(rate * 4):
                    amp = [0.03, 0.65, 0.0, 0.18][i // rate]
                    sample = round(32767 * amp * math.sin(2 * math.pi * 220 * i / rate))
                    frames.extend(struct.pack("<h", sample))
                writer.writeframes(frames)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(audio), str(flac)], check=True)
            for source in [audio, flac]:
                values, seconds = mochi.analyze(source)
                self.assertEqual(len(values), 64)
                self.assertAlmostEqual(seconds, 4, delta=0.02)
                self.assertGreater(values[24], values[3])
                self.assertLessEqual(max(values[32:48]), 1)

    @unittest.skipUnless(shutil.which("cc"), "C compiler not found")
    def test_c_renderer_tracks_progress_and_amplitude(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "wave.so"
            source = ROOT / "prototypes" / "mochi_player" / "mochi_wave_peaks.c"
            subprocess.run(["cc", "-shared", "-fPIC", "-O2", str(source), "-o", str(binary)], check=True)
            lib = ctypes.CDLL(str(binary))
            callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int)
            levels = (ctypes.c_uint8 * 64)(*([0] * 32 + [255] * 32))
            bars = []

            def receive(ctx, x, y, w, h, active):
                bars.append((x, y, w, h, active))

            callback = callback_type(receive)
            lib.mochi_wave_draw_peaks.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32,
                                                   ctypes.c_uint32, ctypes.c_int, ctypes.c_int,
                                                   callback_type, ctypes.c_void_p]
            lib.mochi_wave_draw_peaks(levels, 5000, 10000, 0, 16, callback, None)
            self.assertEqual(len(bars), 64)
            self.assertTrue(all(b[3] == 2 for b in bars[:32]))
            self.assertTrue(all(b[3] == 28 for b in bars[32:]))
            self.assertEqual(sum(b[4] for b in bars), 32)


if __name__ == "__main__":
    unittest.main()
