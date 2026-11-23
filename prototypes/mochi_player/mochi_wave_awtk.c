/* Optional AWTK adapter for the standalone Mochi waveform.
 * NOT linked into the current firmware. Before integration this must be tested
 * against the device's AWTK event/paint semantics and play-position updates.
 */
#include "offsets.inc"
#include "mochi_wave.h"

static void *mw_slider __attribute__((section(".scratch")));
static void *mw_view __attribute__((section(".scratch")));

static void mw_bar(void *ctx, int x, int y, int w, int h, int active) {
    /* AWTK color_t layout on MIPS is 0xAABBGGRR. Jade and graphite. */
    void *canvas = ctx;
    canvas_set_fill_color(canvas, active ? 0xffcfd4c1u : 0xff595047u);
    canvas_fill_rect(canvas, x, y, w, h);
}

static int mw_paint(void *ctx, void *event) {
    void *canvas = event ? *(void **)((char *)event + EVENT_PAINT_CANVAS) : (void *)0;
    int lo, hi, value;
    if (!canvas || ctx != mw_view || !mw_slider) return RET_OK;
    lo = widget_get_prop_int(mw_slider, "min", 0);
    hi = widget_get_prop_int(mw_slider, "max", 100);
    value = widget_get_prop_int(mw_slider, "value", lo);
    mochi_wave_draw(0, 12, value - lo, hi - lo, mw_bar, canvas);
    return RET_OK;
}

static int mw_changed(void *ctx, void *event) {
    (void)event;
    if (ctx == mw_slider && mw_view) widget_invalidate_force(mw_view, (void *)0);
    return RET_OK;
}

void mochi_wave_detach(void) {
    /* The host Now Playing page must call this before it destroys the widgets. */
    mw_slider = (void *)0;
    mw_view = (void *)0;
}

int mochi_wave_attach(void *win) {
    void *slider = widget_lookup(win, "slider_play", 1);
    void *wave = widget_lookup(win, "mochi_wave", 1);
    if (!slider || !wave) return 0;
    mochi_wave_detach();
    mw_slider = slider;
    mw_view = wave;
    if (!widget_on(wave, EVT_AFTER_PAINT, mw_paint, wave)) {
        mochi_wave_detach();
        return 0;
    }
    if (!widget_on(slider, EVT_VALUE_CHANGED, mw_changed, slider)) {
        mochi_wave_detach();
        return 0;
    }
    return 1;
}
