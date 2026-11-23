#ifndef MOCHI_WAVE_H
#define MOCHI_WAVE_H

/* The 64 bars are a seek-progress metaphor, not decoded PCM data. */
#define MOCHI_WAVE_BARS 64
#define MOCHI_WAVE_BAR_W 2
#define MOCHI_WAVE_GAP 2

typedef void (*mochi_bar_fn)(void *ctx, int x, int y, int w, int h, int active);

/* Duration <= 0 or elapsed <= 0: no active bars. No heap, audio decoding or floating point. */
void mochi_wave_draw(int x, int center_y, int elapsed, int duration, mochi_bar_fn paint, void *ctx);

#endif
