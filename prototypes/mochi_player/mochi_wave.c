#include "mochi_wave.h"

static int lobe(int i, int center, int radius, int peak) {
    int distance = i >= center ? i - center : center - i;
    return distance >= radius ? 0 : (radius - distance) * peak / radius;
}

void mochi_wave_draw(int x, int center_y, int elapsed, int duration, mochi_bar_fn paint, void *ctx) {
    int active = 0, i, h;
    if (!paint) return;
    if (duration > 0 && elapsed > 0) {
        /* Avoid elapsed*64 overflow on long tracks and podcasts. */
        active = elapsed >= duration ? MOCHI_WAVE_BARS
                                     : (elapsed / duration) * MOCHI_WAVE_BARS +
                                           ((elapsed % duration) * MOCHI_WAVE_BARS) / duration;
    }
    for (i = 0; i < MOCHI_WAVE_BARS; i++) {
        h = 4 + lobe(i, 14, 15, 12) + lobe(i, 37, 11, 9) + lobe(i, 54, 8, 6);
        paint(ctx, x + i * (MOCHI_WAVE_BAR_W + MOCHI_WAVE_GAP), center_y - h / 2, MOCHI_WAVE_BAR_W, h,
              i < active);
    }
}
