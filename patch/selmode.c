/* The multi-select every page shares: see patch/selmode.h and docs/modules/selmode.md.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "grid.h"
#include "azlist.h"
#include "i18n.h"
#include "selmode.h"

static int sm_can(const m1_sel_t *s, int i) { return !s->can || s->can(s->ctx, i); }

int m1_sel_init(m1_sel_t *s, void *win, void *back, void *title, void *btn_selall, void *bar, void *pill0, void *pill1,
                int (*can)(void *ctx, int i), void *ctx) {
    memset(s, 0, sizeof *s);
    s->back = back, s->title = title, s->btn_selall = btn_selall, s->bar = bar;
    s->pill[0] = pill0, s->pill[1] = pill1;
    s->can = can, s->ctx = ctx;
    return m1_make_marks(win, s->mark);
}

void m1_sel_free(m1_sel_t *s) {
    int i;
    if (s->own) free(s->bits);
    s->bits = (unsigned char *)0, s->count = s->nsel = s->nmark = 0, s->own = 0;
    for (i = 0; i < 2; ++i) {
        if (s->mark[i]) bitmap_destroy(s->mark[i]);
        s->mark[i] = (void *)0;
    }
}

static void sm_count(m1_sel_t *s) {
    unsigned i;
    s->nsel = s->nmark = 0;
    for (i = 0; i < s->count; ++i)
        if (sm_can(s, (int)i)) ++s->nmark;
}

int m1_sel_reset(m1_sel_t *s, unsigned count) {
    if (s->own) free(s->bits);
    s->bits = (unsigned char *)0, s->own = 0, s->count = s->nsel = s->nmark = 0;
    if (!count) return 1;
    s->bits = calloc((count + 7) / 8, 1);
    if (!s->bits) return 0;
    s->own = 1, s->count = count;
    sm_count(s);
    return 1;
}

int m1_sel_bind(m1_sel_t *s, unsigned char *bits, unsigned count) {
    if (s->own) free(s->bits);
    s->bits = bits, s->own = 0, s->count = count;
    if (bits) memset(bits, 0, (count + 7) / 8);
    sm_count(s);
    return bits != (unsigned char *)0;
}

void m1_sel_clear(m1_sel_t *s) {
    if (s->bits) memset(s->bits, 0, (s->count + 7) / 8);
    s->nsel = 0;
}

int m1_sel_is(const m1_sel_t *s, int i) {
    return s->bits && i >= 0 && (unsigned)i < s->count && (s->bits[i >> 3] >> (i & 7) & 1);
}

int m1_sel_toggle(m1_sel_t *s, int i) {
    if (!s->bits || i < 0 || (unsigned)i >= s->count || !sm_can(s, i)) return 0;
    s->bits[i >> 3] ^= (unsigned char)(1 << (i & 7));
    s->nsel += m1_sel_is(s, i) ? 1 : (unsigned)-1;
    return 1;
}

int m1_sel_every(const m1_sel_t *s) { return s->nmark && s->nsel >= s->nmark; }

void m1_sel_toggle_all(m1_sel_t *s) {
    if (!s->bits) return;
    s->nsel = m1_sel_all_can(s->bits, s->count, s->nsel, s->nmark, s->can, s->ctx);
}

void m1_selall_fit(void *btn) {
    const unsigned *t = widget_get_text(btn);
    int w = (t && *t ? m1_text_w(btn, t) : 0) + 2 * SG_SELALL_PAD;
    widget_move(btn, SG_SELALL_R - w, SG_SELALL_Y);
    widget_resize(btn, w, SG_SELALL_H);
}

void m1_sel_head(m1_sel_t *s) {
    char buf[64];
    int i, any = s->nsel != 0;
    if (!s->on) return;
    if (any) {
        m1_fmt(buf, sizeof buf, TR("%d Selected"), (int)s->nsel);
        widget_set_text_utf8(s->title, buf);
    } else
        widget_set_text_utf8(s->title, TR("Select Items"));
    widget_set_tr_text(s->btn_selall, m1_sel_every(s) ? "Deselect All" : "Select All");
    m1_selall_fit(s->btn_selall);
    for (i = 0; i < 2; ++i)
        if (s->pill[i]) { /* enable picks the disable style (dimmed glyph and label); sensitive drops the taps */
            widget_set_prop_int(s->pill[i], "enable", any);
            widget_set_sensitive(s->pill[i], any);
        }
}

void m1_sel_enter(m1_sel_t *s, int on, int off_end) {
    s->on = on;
    m1_sel_clear(s);
    m1_show(s->btn_selall, on);
    m1_show(s->bar, on);
    grid_icons(s->back, on ? "ah_nav_close" : "ah_nav_back", on ? "ah_nav_close_down" : "ah_nav_back_down");
    grid_title_end(s->title, on ? SG_SELALL_X : off_end);
    m1_sel_head(s);
}

void m1_sel_paint(const m1_sel_t *s, void *canvas, int i, int y, int rh, int w, int mark_x, int view_h) {
    if (!s->on || !s->mark[0] || !sm_can(s, i)) return;
    if (m1_sel_is(s, i)) az_fill_h(canvas, 0, y, y + rh - 1, w, LIST_SEL_FILL, view_h);
    grid_mark_draw(canvas, s->mark[m1_sel_is(s, i)], mark_x, y + (rh - SG_MARK) / 2, view_h);
}
