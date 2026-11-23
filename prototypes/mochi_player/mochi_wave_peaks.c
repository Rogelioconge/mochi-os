#include "mochi_wave_peaks.h"

void mochi_wave_draw_peaks(const uint8_t levels[MOCHI_WAVE_PEAK_BARS],
                           uint32_t elapsed_ms, uint32_t duration_ms,
                           int x, int center_y, mochi_peaks_bar_fn paint, void *ctx) {
    uint32_t active = 0;
    int i;
    if (!levels || !paint) return;
    if (duration_ms != 0) {
        /* 64-bit multiplication avoids overflow for long tracks and audiobooks. */
        active = elapsed_ms >= duration_ms ? MOCHI_WAVE_PEAK_BARS
                : (uint32_t)(((uint64_t)elapsed_ms * MOCHI_WAVE_PEAK_BARS) / duration_ms);
    }
    for (i = 0; i < MOCHI_WAVE_PEAK_BARS; i++) {
        int height = 2 + ((int)levels[i] * 26 + 127) / 255;
        paint(ctx, x + i * (MOCHI_WAVE_PEAK_BAR_WIDTH + MOCHI_WAVE_PEAK_GAP),
              center_y - height / 2, MOCHI_WAVE_PEAK_BAR_WIDTH, height,
              (uint32_t)i < active);
    }
}
