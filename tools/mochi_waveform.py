#!/usr/bin/env python3
"""Generate a lightweight real-audio waveform envelope for Mochi OS development.

Host-side only: not wired to Shanling M1 Plus firmware.
Requires ffmpeg and ffprobe on PATH. Streams decoded 8 kHz mono PCM; never
modifies the source file. Output: 64 amplitudes 0..255 for the C renderer.
"""

from __future__ import annotations

import argparse
from array import array
import json
import math
from pathlib import Path
import subprocess
import sys

BARS = 64
SAMPLE_RATE = 8000


def envelope_from_samples(samples: list[int], bars: int = BARS) -> list[int]:
    """Compute RMS amplitudes for fixed, equal-duration windows.

    Returns 0..255 values normalized to the maximum of the track, not volume
    wheel level or an audio spectrum. Useful for tests and short demo clips.
    """
    if bars < 1:
        raise ValueError("bars must be positive")
    sums = [0] * bars
    counts = [0] * bars
    n = len(samples)
    if n == 0:
        return [0] * bars
    for i, sample in enumerate(samples):
        pos = min(bars - 1, i * bars // n)
        sums[pos] += int(sample) * int(sample)
        counts[pos] += 1
    return _scale_rms(sums, counts)


def _scale_rms(sums: list[int], counts: list[int]) -> list[int]:
    rms = [math.sqrt(s / n) if n else 0.0 for s, n in zip(sums, counts)]
    biggest = max(rms, default=0.0)
    if biggest <= 0:
        return [0] * len(rms)
    # Compress dynamic range a little so quieter passages remain visible.
    return [min(255, round(255 * ((v / biggest) ** 0.72))) for v in rms]


def _probe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    seconds = float(result.stdout.strip())
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Audio duration is not a positive finite number")
    return seconds


def analyze(path: Path, bars: int = BARS) -> tuple[list[int], float]:
    """Read real audio without loading the whole track into RAM."""
    if not path.is_file():
        raise FileNotFoundError(path)
    duration = _probe_duration(path)
    nominal_samples = max(1, round(duration * SAMPLE_RATE))
    sums = [0] * bars
    counts = [0] * bars
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
           "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-f", "s16le", "pipe:1"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processed = 0
    try:
        assert process.stdout is not None
        while chunk := process.stdout.read(65536):
            # S16LE decoder; guard against a partial trailing sample.
            if len(chunk) % 2:
                raise ValueError("Invalid decoded PCM byte count")
            pcm = array('h')
            pcm.frombytes(chunk)
            if sys.byteorder != "little":
                pcm.byteswap()
            for sample in pcm:
                idx = min(bars - 1, processed * bars // nominal_samples)
                sums[idx] += sample * sample
                counts[idx] += 1
                processed += 1
        assert process.stderr is not None
        errors = process.stderr.read().decode("utf8", "replace")
        status = process.wait()
        if status != 0:
            raise RuntimeError(f"FFmpeg decoding failed ({status}): {errors.strip()}")
        if processed == 0:
            raise ValueError("Audio contained no decoded samples")
        return _scale_rms(sums, counts), duration
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def analyze_to_json(path: Path) -> dict:
    values, seconds = analyze(path)
    return {
        "schema": "mochi.waveform.v1",
        "algorithm": "track-normalized-rms-envelope",
        "source_basename": path.name,
        "duration_seconds": round(seconds, 3),
        "bar_count": BARS,
        "amplitudes": values,
        "integration_status": "host-prototype-only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="A FLAC, WAV, MP3 or other ffmpeg-supported audio file")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON file")
    args = parser.parse_args()
    try:
        result = analyze_to_json(args.audio)
        args.out.parent.mkdir(exist_ok=True, parents=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {args.out}: {result['bar_count']} real-audio RMS bars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
