"""Mochi OS: lightweight, deterministic waveform-shaped seek representation.

The bars are a visual seek metaphor, NOT a PCM waveform or live audio analysis.
Geometry is independent of state, and active bars encode elapsed playback.
"""

from __future__ import annotations

from dataclasses import dataclass

BAR_COUNT = 64
BAR_WIDTH = 2
BAR_GAP = 2


def heights() -> tuple[int, ...]:
    """Constant shape: restrained with natural rhythm, not distracting animation."""
    # Integer-only calculation; the same algorithm is implemented in C.
    def lobe(i: int, center: int, radius: int, peak: int) -> int:
        distance = abs(i - center)
        return max(0, (radius - distance) * peak // radius)
    return tuple(4 + lobe(i, 14, 15, 12) + lobe(i, 37, 11, 9) + lobe(i, 54, 8, 6)
                 for i in range(BAR_COUNT))


@dataclass(frozen=True)
class Segment:
    x: int
    y: int
    w: int
    h: int
    active: bool


def segments(x: int, center_y: int, elapsed: int, duration: int) -> tuple[Segment, ...]:
    if duration <= 0:
        active = 0
    else:
        active = min(BAR_COUNT, max(0, elapsed) * BAR_COUNT // duration)
    return tuple(Segment(x + i * (BAR_WIDTH + BAR_GAP), center_y - h // 2, BAR_WIDTH, h, i < active)
                 for i, h in enumerate(heights()))
