/* Bounded Pod display model and internal page slides. MIT, Copyright (c) 2026 Xin. */
#pragma once
void ip_render_open(void);
void ip_render_close(void);
void ip_render_cancel(void);
int ip_render_transition(int direction, int width);
int ip_render_active(void);
void ip_render_restart(void); /* after a level's query: the slide counts from now */
int ip_render_tick(void);
int ip_render_width(void);
void ip_render_offsets(int *outgoing, int *incoming);
void ip_render_begin(void);
void ip_render_end(void);
void ip_render_out(void *canvas, int half); /* half: 0 the commands left of the split, 1 right of it, 2 all */
int ip_render_split(
    void); /* a split transition is running (width 0 in ip_render_transition: the menu half and the pane open or close a fullscreen page) */
int ip_render_shadow_skip(
    void); /* the split shadow's leading columns left out: it fades out as the halves part and in as they close */
int ip_render_cover(
    void); /* a cover transition is running (width -1: a full-width page over a split page's still pane, its left edge pushing the menu half) */
int ip_render_direction(void);
void ip_render_edge(
    void *
        bitmap); /* the bitmap of the shadow the menu half casts on the pane: its commands belong to the left half of a split */
void ip_render_prepare(void *style, void *canvas);
void ip_render_text(void *canvas, const unsigned *text, unsigned n, const int *rect);
void ip_render_image(void *canvas, void *bitmap, const int *src, const int *dst);
void ip_render_fill(void *canvas, int x, int y, int w, int h, unsigned rgb);
/* What paint(canvas) draws inside the screen's w x h rectangle at (x, y), as pixels in d (pitch w; text in ink(style)); the canvas
 * is not drawn on. 0: it did not fit the model (d partly painted). */
int ip_render_raster(void (*paint)(void *), void *canvas, unsigned *d, int x, int y, int w, int h,
                     unsigned (*ink)(const void *style));
