#ifndef MOCHI_WAVE_PEAKS_H
#define MOCHI_WAVE_PEAKS_H

#include <stdint.h>

#define MOCHI_WAVE_PEAK_BARS 64
#define MOCHI_WAVE_PEAK_BAR_WIDTH 2
#define MOCHI_WAVE_PEAK_GAP 2

/* Callback receives a solid vertical bar rectangle, active if before playback head. */
typedef void (*mochi_peaks_bar_fn)(void *ctx, int x, int y, int w, int h, int active);

/* 64 real-amplitude bars from host waveform analyzer or future on-device cache.
 * levels are normalized uint8 amplitude 0..255, not current output volume.
 * Values 0 produce a 2px silent marker. No heap allocations or audio access.
 * NOT YET CONNECTED TO AWTK OR A REAL DEVICE DECODER.
 */
void mochi_wave_draw_peaks(const uint8_t levels[MOCHI_WAVE_PEAK_BARS],
                           uint32_t elapsed_ms, uint32_t duration_ms,
                           int x, int center_y, mochi_peaks_bar_fn paint, void *ctx);

#endif
