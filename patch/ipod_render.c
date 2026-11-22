/* A display model owns strings and (only while moving) cloned images. Paint never allocates.
 * The stock framebuffer is not sampled. No borrowed library record survives a query.
 * MIT, Copyright (c) 2026 Xin. */
#include "stock.h"
#include "offsets.inc"
#include "ipod_render.h"

#define COMMANDS 192
#define TEXT_WORDS 2048
#define IMAGES 8
#define SLIDE_MS 280 /* the reference's push and pop: 280 ms, eased out (the iPod video) */
#define SPLIT_MS 200 /* the split: the halves part and close over a fullscreen page faster than a push */
#define COVER_MS \
    300 /* the cover slide: 320 px at a steady speed, the menu pushed over its second half (the reference video: 9 frames at 30 fps, linear) */
#define I(p, o) (*(int *)((char *)(p) + (o)))

enum { DRAW_FILL, DRAW_TEXT, DRAW_IMAGE };
struct command {
    int kind, rect[4], src[4],
        edge; /* edge: the image is the menu half's edge shadow (ip_render_edge): it belongs to the left half of a split */
    unsigned color, text, n;
    void *style, *bitmap;
};
struct picture {
    struct command commands[COMMANDS];
    unsigned text[TEXT_WORDS];
    unsigned count, used;
    int valid;
};
static struct {
    struct picture *last, *old, *cap; /* cap: what ip_render_raster records (dry: nothing is drawn) */
    struct picture *rec; /* the picture being recorded: last, or cap */
    void *style, *edge, *images[IMAGES];
    unsigned nimages, start, elapsed, ms;
    int recording, overflow, active, direction, width, split, cover, dry;
} render __attribute__((section(".scratch")));

static void clear_old(void) {
    unsigned i;
    for (i = 0; i < render.nimages; ++i) bitmap_destroy(render.images[i]);
    render.nimages = 0;
    render.active = 0;
}

void ip_render_cancel(void) {
    clear_old();
    if (render.last) render.last->valid = 0;
}

void ip_render_close(void) {
    clear_old();
    if (render.last) free(render.last);
    if (render.old) free(render.old);
    if (render.cap) free(render.cap);
    memset(&render, 0, sizeof render);
}

void ip_render_open(void) {
    ip_render_close();
    render.last = calloc(1, sizeof(struct picture));
    render.old = calloc(1, sizeof(struct picture));
    render.cap = calloc(1, sizeof(struct picture));
    if (!render.last || !render.old || !render.cap) ip_render_close();
}

static void *clone(void *source) {
    unsigned w = (unsigned)I(source, 0), h = (unsigned)I(source, 4), pitch, y;
    const unsigned char *src;
    unsigned char *dst;
    void *copy;
    if (!w || !h || w > 320 || h > 264 || *(unsigned short *)((char *)source + BITMAP_FORMAT) != BITMAP_RGBA8888)
        return (void *)0;
    pitch = bitmap_get_line_length(source);
    if (pitch < w * 4) return (void *)0;
    copy = bitmap_create_ex(w, h, w * 4, BITMAP_RGBA8888);
    if (!copy) return (void *)0;
    src = bitmap_lock_buffer_for_read(source);
    dst = bitmap_lock_buffer_for_write(copy);
    if (src && dst)
        for (y = 0; y < h; ++y) memcpy(dst + y * w * 4, src + y * pitch, w * 4);
    if (src) bitmap_unlock_buffer(source);
    if (dst) bitmap_unlock_buffer(copy);
    if (!src || !dst) {
        bitmap_destroy(copy);
        return (void *)0;
    }
    return copy;
}

int ip_render_transition(int direction, int width) {
    void *original[IMAGES];
    unsigned i, j;
    /* Fast input settles immediately, rather than stacking transitions or snapshots. */
    if (render.active) {
        ip_render_cancel();
        return 0;
    }
    if (!render.last || !render.old || !render.last->valid) return 0;
    memcpy(render.old, render.last, sizeof(struct picture));
    /* width 0: the split. The menu half and the artwork pane of a split page part (opening a fullscreen page) or close over it; every command is kept. */
    render.split = width == 0;
    if (render.split) width = IP_SPLIT_X;
    /* width -1: the cover. A full-width page comes in over a split page's still artwork pane and pushes its menu half out on the left (closing, the reverse). */
    render.cover = width < 0;
    if (render.cover) width = IP_W;
    render.ms = render.cover ? COVER_MS : render.split ? SPLIT_MS : SLIDE_MS;
    /* Half-width navigation does not move or clone the stationary artwork pane. */
    for (i = 0, j = 0; i < render.old->count; ++i) {
        if (render.split) {
            j = render.old->count;
            break;
        }
        struct command *c = &render.old->commands[i];
        if (c->rect[0] >= width || c->rect[0] + c->rect[2] <= 0) continue;
        if (i != j) memcpy(&render.old->commands[j], c, sizeof *c);
        ++j;
    }
    render.old->count = j;
    for (i = 0; i < render.old->count; ++i) {
        struct command *c = &render.old->commands[i];
        if (c->kind != DRAW_IMAGE) continue;
        for (j = 0; j < render.nimages; ++j)
            if (original[j] == c->bitmap) break;
        if (j == render.nimages) {
            void *copy;
            if (j >= IMAGES || !(copy = clone(c->bitmap))) {
                ip_render_cancel();
                return 0;
            }
            original[j] = c->bitmap;
            render.images[render.nimages++] = copy;
        }
        c->bitmap = render.images[j];
    }
    render.direction = direction;
    render.width = width;
    render.start = time_now_ms();
    render.elapsed = 0;
    render.active = 1;
    render.last->valid = 0;
    return 1;
}

int ip_render_active(void) { return render.active; }
/* The slide's clock starts again: after the new level's query, which may take longer than the slide (Music > Songs on a big library), so the slide is seen whole. */
void ip_render_restart(void) {
    if (render.active) render.start = time_now_ms(), render.elapsed = 0;
}
int ip_render_width(void) { return render.width; }
int ip_render_split(void) { return render.active && render.split; }
int ip_render_cover(void) { return render.active && render.cover; }
int ip_render_direction(void) { return render.direction; }
void ip_render_edge(void *bitmap) {
    render.edge = bitmap;
} /* the menu edge's shadow image: recorded images that are it replay with the menu half */

int ip_render_tick(void) {
    if (!render.active) return 0;
    render.elapsed = time_now_ms() - render.start;
    if (render.elapsed >= render.ms) clear_old();
    return 1;
}

/* The shadow's leading columns left out while a split slides: none to all IP_SHADOW_W as the halves part, all to none as they close, so the shadow fades with the
 * slide and is whole only when the menu rests (no jump when the halves meet). 0 outside a split. */
int ip_render_shadow_skip(void) {
    unsigned p;
    if (!render.active || !render.split) return 0;
    p = render.elapsed * 1024 / render.ms;
    if (p > 1024) p = 1024;
    return (int)((render.direction > 0 ? p : 1024 - p) * IP_SHADOW_W / 1024);
}

void ip_render_offsets(int *outgoing, int *incoming) {
    unsigned p = render.elapsed * 1024 / render.ms;
    unsigned eased;
    if (p > 1024) p = 1024;
    if (render.cover)
        eased = p; /* the cover slide is linear */
    else if (render.split)
        eased = (p * p / 1024) * (3072 - 2 * p) / 1024; /* the split eases in and out */
    else
        eased = 1024 - (1024 - p) * (1024 - p) /
                           1024; /* push and pop ease out: a third of the way in the first frame, as the iPod's */
    int travel = (int)(render.width * eased / 1024);
    *outgoing = render.direction > 0 ? -travel : travel;
    *incoming = render.direction > 0 ? render.width - travel : travel - render.width;
}

void ip_render_begin(void) {
    if (!render.last) return;
    render.last->count = render.last->used = 0;
    render.last->valid = 0;
    render.rec = render.last;
    render.overflow = 0;
    render.recording = 1;
}

void ip_render_end(void) {
    render.recording = 0;
    if (render.last) render.last->valid = !render.overflow;
}

static struct command *append(int kind, const int *rect) {
    struct command *c;
    if (!render.recording || !render.rec) return (struct command *)0;
    if (render.rec->count == COMMANDS) {
        render.overflow = 1;
        return (struct command *)0;
    }
    c = &render.rec->commands[render.rec->count++];
    c->kind = kind, c->edge = 0;
    memcpy(c->rect, rect, 4 * sizeof(int));
    return c;
}

void ip_render_prepare(void *style, void *canvas) {
    render.style = style;
    widget_prepare_text_style(style, canvas);
}

void ip_render_fill(void *canvas, int x, int y, int w, int h, unsigned rgb) {
    int rect[4] = {x, y, w, h};
    struct command *c = append(DRAW_FILL, rect);
    if (c) c->color = rgb;
    if (render.dry) return;
    canvas_set_fill_color(canvas, 0xff000000u | rgb);
    canvas_fill_rect(canvas, x, y, w, h);
}

void ip_render_text(void *canvas, const unsigned *text, unsigned n, const int *rect) {
    struct command *c = append(DRAW_TEXT, rect);
    if (c) {
        if (n > TEXT_WORDS - render.rec->used) {
            render.overflow = 1;
            --render.rec->count;
        } else {
            c->text = render.rec->used, c->n = n, c->style = render.style;
            memcpy(render.rec->text + c->text, text, n * sizeof(unsigned));
            render.rec->used += n;
        }
    }
    if (render.dry) return;
    canvas_draw_text_in_rect(canvas, text, n, rect);
}

void ip_render_image(void *canvas, void *bitmap, const int *src, const int *dst) {
    struct command *c = append(DRAW_IMAGE, dst);
    if (c) {
        c->bitmap = bitmap;
        c->edge = bitmap == render.edge;
        memcpy(c->src, src, 4 * sizeof(int));
    }
    if (render.dry) return;
    canvas_draw_image(canvas, bitmap, src, dst);
}

void ip_render_out(void *canvas, int half) {
    unsigned i;
    if (!render.active || !render.old) return;
    for (i = 0; i < render.old->count; ++i) {
        const struct command *c = &render.old->commands[i];
        if (half < 2 && (!c->edge && c->rect[0] >= IP_SPLIT_X) != half) continue;
        if (c->kind == DRAW_FILL) {
            canvas_set_fill_color(canvas, 0xff000000u | c->color);
            canvas_fill_rect(canvas, c->rect[0], c->rect[1], c->rect[2], c->rect[3]);
        } else if (c->kind == DRAW_TEXT) {
            widget_prepare_text_style(c->style, canvas);
            canvas_draw_text_in_rect(canvas, render.old->text + c->text, c->n, c->rect);
        } else if (c->edge && render.split) { /* the split's fading shadow: its outer columns only */
            int skip = ip_render_shadow_skip();
            int src[4] = {c->src[0] + skip, c->src[1], c->src[2] - skip, c->src[3]};
            int dst[4] = {c->rect[0], c->rect[1], c->rect[2] - skip, c->rect[3]};
            if (skip < c->src[2]) canvas_draw_image(canvas, c->bitmap, src, dst);
        } else
            canvas_draw_image(canvas, c->bitmap, c->src, c->rect);
    }
}

/* ---------------------------------------------------------------------------
 * Pixels from a paint: what paint(canvas) would draw, recorded (dry: the canvas is not drawn on) and laid into d, the w x h
 * rectangle at (x, y) of the screen (pitch w). Fills and images as the canvas draws them; text from the font the canvas
 * takes for the style (widget_prepare_text_style puts font and size there), each glyph's 8-bit alpha blended in ink(style), as
 * canvas_draw_text_in_rect places it: left in the rect, the line top at rect.y + (rect.h - size) / 2 (text_align_v middle),
 * x + glyph.x, top + glyph.y + ascent, advancing by the glyph's advance + 1 (4 for a missing glyph). */
typedef struct {
    short x, y;
    unsigned short w, h, advance;
    unsigned char format, pitch;
    const unsigned char *data;
} raster_glyph;

static unsigned mix(unsigned v, unsigned c, unsigned a) {
    unsigned k = a + (a >> 7);
    return 0xff000000u | (((v & 0xff00ffu) * (256 - k) + (c & 0xff00ffu) * k) >> 8 & 0xff00ffu) |
           (((v & 0xff00u) * (256 - k) + (c & 0xff00u) * k) >> 8 & 0xff00u);
}

static void raster_text(unsigned *d, int w, int h, const struct command *c, const unsigned *text, void *canvas,
                        unsigned rgb) {
    void *font = *(void **)((char *)canvas + CANVAS_FONT);
    unsigned size = *(unsigned short *)((char *)canvas + CANVAS_FONT_SIZE), i;
    int pen = c->rect[0], top, r, k;
    short vm[4];
    raster_glyph g;
    if (!font) return;
    font_get_vmetrics(vm, font, size);
    top = c->rect[1] + ((c->rect[3] - (int)size) >> 1) + vm[0];
    for (i = 0; i < c->n; ++i) {
        if (font_get_glyph(font, text[i], size, &g)) {
            pen += 4;
            continue;
        }
        if (g.data && g.format == GLYPH_FORMAT_ALPHA)
            for (r = 0; r < g.h; ++r) {
                int y = top + g.y + r;
                if ((unsigned)y >= (unsigned)h) continue;
                for (k = 0; k < g.w; ++k) {
                    int x = pen + g.x + k;
                    unsigned a = g.data[r * g.w + k];
                    if (a && (unsigned)x < (unsigned)w) d[y * w + x] = mix(d[y * w + x], rgb, a);
                }
            }
        pen += g.advance + 1;
    }
}

static void raster_image(unsigned *d, int w, int h, const struct command *c) {
    const unsigned char *src;
    unsigned pitch;
    int x, y;
    if (*(unsigned short *)((char *)c->bitmap + BITMAP_FORMAT) != BITMAP_RGBA8888 || c->rect[2] <= 0 || c->rect[3] <= 0)
        return;
    pitch = bitmap_get_line_length(c->bitmap);
    src = bitmap_lock_buffer_for_read(c->bitmap);
    if (!src) return;
    for (y = 0; y < c->rect[3]; ++y) {
        int dy = c->rect[1] + y, sy = c->src[1] + y * c->src[3] / c->rect[3];
        if ((unsigned)dy >= (unsigned)h) continue;
        for (x = 0; x < c->rect[2]; ++x) {
            int dx = c->rect[0] + x, sx = c->src[0] + x * c->src[2] / c->rect[2];
            unsigned p;
            if ((unsigned)dx >= (unsigned)w) continue;
            p = *(const unsigned *)(src + sy * pitch + sx * 4);
            if (p >> 24) d[dy * w + dx] = mix(d[dy * w + dx], p, p >> 24);
        }
    }
    bitmap_unlock_buffer(c->bitmap);
}

int ip_render_raster(void (*paint)(void *), void *canvas, unsigned *d, int x, int y, int w, int h,
                     unsigned (*ink)(const void *style)) {
    struct picture *rec = render.rec, *cap = render.cap;
    void *style = render.style;
    int recording = render.recording, overflow = render.overflow, ok;
    unsigned i;
    if (!cap || !d) return 0;
    cap->count = cap->used = 0;
    render.rec = cap, render.recording = 1, render.overflow = 0, render.dry = 1;
    paint(canvas);
    ok = !render.overflow;
    render.rec = rec, render.recording = recording, render.overflow = overflow, render.dry = 0;
    if (ok)
        for (i = 0; i < cap->count; ++i) {
            struct command c = cap->commands[i];
            c.rect[0] -= x, c.rect[1] -= y;
            if (c.kind == DRAW_FILL) {
                int x0 = c.rect[0] < 0 ? 0 : c.rect[0], x1 = c.rect[0] + c.rect[2] > w ? w : c.rect[0] + c.rect[2];
                int y0 = c.rect[1] < 0 ? 0 : c.rect[1], y1 = c.rect[1] + c.rect[3] > h ? h : c.rect[1] + c.rect[3], r,
                    k;
                for (r = y0; r < y1; ++r)
                    for (k = x0; k < x1; ++k) d[r * w + k] = 0xff000000u | c.color;
            } else if (c.kind == DRAW_TEXT) {
                widget_prepare_text_style(c.style, canvas);
                raster_text(d, w, h, &c, cap->text + c.text, canvas, ink(c.style));
            } else
                raster_image(d, w, h, &c);
        }
    render.style = style;
    if (style) widget_prepare_text_style(style, canvas); /* the canvas back in the style the paint had */
    return ok;
}
