/* The multi-select every page shares (patch/selmode.c, docs/modules/selmode.md): the marks bitset, the chrome of the mode (the close x, "N Selected" / "Select Items",
 * Select All / Deselect All, the bottom bar and its pills) and a row's mark and faint fill.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

typedef struct {
    unsigned char *bits; /* (count + 7) / 8 bytes, bit i = row i marked */
    unsigned count; /* rows the bits cover */
    unsigned nsel; /* rows marked */
    unsigned nmark; /* rows that can be marked (can() true), counted by m1_sel_reset / m1_sel_bind */
    int own; /* bits is ours (freed by m1_sel_reset / m1_sel_free); 0 for a borrowed vector (m1_sel_bind) */
    int on; /* the mode is on */
    int (*can)(void *ctx, int i); /* NULL: every row can be marked */
    void *ctx;
    void *mark[2]; /* the marks: unselect, selected (both NULL: no marks, so no mode) */
    void *back, *title, *btn_selall, *bar; /* the page's chrome widgets */
    void *pill[2]; /* the bar's pills (either may be NULL): sensitive only while something is marked */
} m1_sel_t;

/* The page's widgets and the marks (win: any widget of the page). Returns 1 with the marks made, 0 without (the page has no select mode). */
int m1_sel_init(m1_sel_t *s, void *win, void *back, void *title, void *btn_selall, void *bar, void *pill0, void *pill1,
                int (*can)(void *ctx, int i), void *ctx);
void m1_sel_free(m1_sel_t *s); /* the bits (when ours) and the marks */
/* A new list of count rows, nothing marked: own bits (calloc), or `bits` (borrowed, cleared, never freed: a fixed vector). 0 when there was no memory (count 0 then). */
int m1_sel_reset(m1_sel_t *s, unsigned count);
int m1_sel_bind(m1_sel_t *s, unsigned char *bits, unsigned count);
void m1_sel_clear(m1_sel_t *s); /* nothing marked */
int m1_sel_is(const m1_sel_t *s, int i);
int m1_sel_toggle(m1_sel_t *s, int i); /* 1 when row i could be marked (and flipped) */
void m1_sel_toggle_all(m1_sel_t *s); /* every markable row, unless all are: then none */
int m1_sel_every(const m1_sel_t *s); /* every markable row is marked (and there is one) */
/* The mode on or off: the marks cleared, the close x / back icon, Select All and the bar shown, the title's end at SG_SELALL_X (off: off_end, the page's own). The page's other
 * widgets (nav buttons, the pills it dims, the size and scroll, the rail) stay its own. Then m1_sel_head. */
void m1_sel_enter(m1_sel_t *s, int on, int off_end);
/* The title ("Select Items", "%d Selected"), the Select All label ("Deselect All" once every row is marked) and the bar's pills (dim and dead while nothing is marked), in the mode;
 * nothing off it (the page sets its own title). */
void m1_sel_head(m1_sel_t *s);
/* The Select All glass pill as wide as its label plus SG_SELALL_PAD each side, its right edge at SG_SELALL_R (also the folder picker's: patch/lupick.c). */
void m1_selall_fit(void *btn);
/* A row's select look, under the rest of the row (before its cover and text): the faint fill when marked (full window width, y .. y + rh - 1: not over the hairline), the mark at
 * x (the row's top y), only when the row can be marked. view_h: the window's height (GRID_VIEW_H, or the album page's whole 450 px). */
void m1_sel_paint(const m1_sel_t *s, void *canvas, int i, int y, int rh, int w, int mark_x, int view_h);
