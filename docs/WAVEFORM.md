# Real-song waveform (not a decorative animation)

## What we mean

The 64 rounded bars display a **time-ordered amplitude envelope** of the *actual decoded audio file*. Each bar summarizes approximately 1/64 of a track. Loud passages produce higher bars; silence produces very small markers. Progress changes **color**, not the bar shape.

This differs from:
- **Volume setting:** gain on the Shanling knob, which must not alter the stored envelope.
- **Spectrum analyzer:** live frequency energy, which does not tell the future amplitude of a track.
- **Old Mochi mockup:** three decorative lobes created in C without inspecting audio. That renderer remains in the archived visual prototype but is being superseded.

## Current host-side prototype

Install FFmpeg (`brew install ffmpeg` on macOS), then:

```sh
python3 tools/mochi_waveform.py "/path/to/your.flac" --out /tmp/mochi-waveform.json
```

The script reads the source without modifying it, decodes via FFmpeg to 8 kHz mono signed 16-bit PCM, computes RMS energy per time window, then normalizes and mildly compresses the result to 64 values in the 0–255 range. These values are small enough for a fixed-size C renderer. For example:

```json
{"schema":"mochi.waveform.v1", "bar_count":64, "amplitudes":[0,42,75]}
```

That JSON fragment shows *format only*, not a full valid 64-bar result. The actual tool outputs all 64 values plus duration and algorithm.

The separate `prototypes/mochi_player/mochi_wave_peaks.c` renderer uses these values and playback time to paint bars. It has no heap allocation and does not access audio, the filesystem or AWTK. **This has been tested on the host only, not on the device.**

## Next on-device implementation

1. Identify an existing decoder/PCM analysis path from the installed firmware. Do **not** assume FFmpeg runs on M1 Plus.
2. Produce or lazily cache an envelope per track using decoded PCM on a low-priority worker, or leverage an existing safe analysis API if one exists.
3. Key cache by a robust track identifier plus modification metadata; invalidate after file changes. Handle missing/streaming/DSD tracks with a plain seek bar if necessary.
4. Deliver a copy of exactly 64 levels to the UI; paint only when progress or track changes and preserve slider touch/seek events.
5. Profile CPU, battery, memory, playback interruptions, short tracks, long tracks, clipped peaks and seeking; reject designs that cause audible glitches.
6. Consider a peak/RMS hybrid after listening and visual evaluation; RMS alone is an approximate measure of intensity, not perceptual LUFS loudness.

The first on-device version may be deliberately limited to supported local PCM/FLAC files. Gapless playback must never wait for waveform analysis.

## Testing

```sh
python3 -m unittest discover -s test -p test_mochi_waveform.py -v
```

Tests generate original synthetic WAV audio and FLAC conversions; no copyrighted samples are required.
