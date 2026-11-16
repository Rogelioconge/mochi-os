/* M1+ Music Battery History page: the Since Last Charge card and the charts of Settings > Battery > Battery History (docs/modules/batthist.md "History page").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The Battery History page (tools/pod_pages.py BATTHIST_PAGE) carries the switch's two notes (the long one while the switch is off, a short one while it is on) and the History items after them: the Since Last Charge header, card and its note, the "Last 24 Hours" header and level chart, the Activity header and chart, and an empty
 * note. All but the long note start hidden in the asset; bhpage_show (called by m1plus.c page_refresh: as the page opens, each time it is back in front and when the switch is turned) shows the ones that belong to the
 * state: switch off, the long note; on with no closed bucket yet, the short note and the empty note; otherwise the short note and everything (the Since Last Charge header, card and note only with an unplug_at, else they stay hidden). The list_view layouter skips hidden items, so the page
 * closes up and grows in place.
 *
 * The card and the charts are bitmaps painted into a view the width of the list (the preset page's graph card: patch/peqpage.c, peq_blit): the card (#1C1C1E, rounded), the stacked bar of the card (screen on / playing with the screen off /
 * standby since the charger was removed), the dotted gridlines and the bars, from bh_snapshot; tools/batthist_model.py is the model test/pod/batthist.py compares them with. The level chart has 48 bars of two buckets (the later level; grey,
 * green when either bucket saw the charger, red at 20 % or less on battery, none without data), the activity chart 24 hourly bars of four buckets (the seconds with the screen on light grey at the bottom, playing with the screen off mid grey on
 * top); a bucket on external power has a faint band behind its bars. The legend marks are the same 10 px rounded squares everywhere. The texts, the axis and the hour ticks are real labels (the language's text and font). The hour ticks are
 * bucket boundaries at local multiples of six hours: the zone's offset is read once from localtime at the open bucket (the buckets are UTC quarter hours, which are quarter hours in every zone of the picker) and the labels follow 24-Hour Time.
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "i18n.h"
#include "entries.h"
#include "durations.h"
#include "podcasts.h"
#include "peqpage.h"
#include "lyrics.h"
#include "batthist.h"

#define BHP_CARD_GREY 28
#define BHP_GRID 48 /* the dotted gridlines */
#define BHP_TICK 62 /* the hour ticks under the plot */
#define BHP_LEVEL 165 /* level bars */
#define BHP_HAIR 51 /* the card's hairlines */
#define BHP_LOW 20 /* the level at which a bar on battery turns red */
#define BHP_BAR_W (BHC_W - 2 * BHS_PAD) /* the stacked bar */

/* The three kinds' colours (screen on, playing with the screen off, standby): the bar, the legend marks, the rows' marks. */
static const unsigned char bhp_kind[3][3] = {{0xE6, 0xE6, 0xE6}, {0x78, 0x78, 0x7C}, {0x58, 0x58, 0x5C}};

enum { I_NOTE0, I_NOTE1, I_SEC0, I_HIST0, I_NOTE2, I_SEC1, I_HIST1, I_SEC2, I_HIST2, I_NOTE3, I_COUNT };

static struct {
    void *win;
    void *item[I_COUNT]; /* the items that show and hide, I_* */
    void *bmp[3]; /* the card's, the level and the activity chart's bitmaps, made when the first data shows */
    void *tick[2][4], *axis[3], *cap, *dur, *left, *sc_val[3], *sc_pct[3];
} bhp __attribute__((section(".scratch")));

static unsigned bhp_px(unsigned a, unsigned r, unsigned g, unsigned b) { return a << 24 | b << 16 | g << 8 | r; }

static void bhp_text(void *w, const char *s) {
    if (w) widget_set_text_utf8(w, s);
}

/* ---------------------------------------------------------------------------
 * The bitmaps
 */
/* The card (tools/batthist_model.py blank): its fill, BHC_R corners in the alpha, in the first ch rows of a BHC_W x h bitmap; the rest transparent. */
static void bhp_card(unsigned *px, int h, int ch) {
    int x, y;
    for (y = 0; y < h; ++y)
        for (x = 0; x < BHC_W; ++x) {
            double a = 1;
            if (y >= ch) {
                px[y * BHC_W + x] = 0;
                continue;
            }
            if ((x < BHC_R || x >= BHC_W - BHC_R) && (y < BHC_R || y >= ch - BHC_R)) {
                double dx = x + 0.5 - (x < BHC_R ? BHC_R : BHC_W - BHC_R),
                       dy = y + 0.5 - (y < BHC_R ? BHC_R : ch - BHC_R);
                a = BHC_R - __builtin_sqrt(dx * dx + dy * dy) + 0.5;
                a = a < 0 ? 0 : a > 1 ? 1 : a;
            }
            px[y * BHC_W + x] = tb_cpx(BHP_CARD_GREY, a);
        }
}

static void bhp_rect(unsigned *px, int x, int y, int w, int h, unsigned c) {
    int i, j;
    for (j = y; j < y + h; ++j)
        for (i = x; i < x + w; ++i) px[j * BHC_W + i] = c;
}

static unsigned bhp_grey(unsigned v) { return bhp_px(255, v, v, v); }

static double bhp_clamp(double v, double lo, double hi) { return v < lo ? lo : v > hi ? hi : v; }

/* The coverage of the pixel (x, y) by the rounded rectangle x0, y0, w, h of radius r (tools/batthist_model.py cover). */
static double bhp_cover(int x, int y, int x0, int y0, int w, int h, int r) {
    double cx = bhp_clamp(x + 0.5, x0 + r, x0 + w - r), cy = bhp_clamp(y + 0.5, y0 + r, y0 + h - r), dx = x + 0.5 - cx,
           dy = y + 0.5 - cy;
    return bhp_clamp(r - __builtin_sqrt(dx * dx + dy * dy) + 0.5, 0, 1);
}

/* The colour c (r, g, b) over the opaque pixel at (x, y) with coverage a. */
static void bhp_blend(unsigned *px, int x, int y, const unsigned char *c, double a) {
    unsigned o = px[y * BHC_W + x], r, g, b;
    if (a <= 0) return;
    r = (unsigned)(c[0] * a + (o & 255) * (1 - a) + 0.5);
    g = (unsigned)(c[1] * a + (o >> 8 & 255) * (1 - a) + 0.5);
    b = (unsigned)(c[2] * a + (o >> 16 & 255) * (1 - a) + 0.5);
    px[y * BHC_W + x] = bhp_px(255, r, g, b);
}

/* A legend mark (BHS_MARK_SIZE px, radius BHS_MARK_R) of kind k at x, centred on cy: the one mark of the legend and every row. */
static void bhp_mark(unsigned *px, int x, int cy, int k) {
    int i, j, y0 = cy - BHS_MARK_SIZE / 2;
    for (j = y0; j < y0 + BHS_MARK_SIZE; ++j)
        for (i = x; i < x + BHS_MARK_SIZE; ++i)
            bhp_blend(px, i, j, bhp_kind[k], bhp_cover(i, j, x, y0, BHS_MARK_SIZE, BHS_MARK_SIZE, BHS_MARK_R));
}

/* The dotted gridlines at the plot's top, middle and bottom, and a tick under the plot at each of the n bucket boundaries idx. */
static void bhp_grid(unsigned *px, int py0, int ph, const int *idx, int n) {
    int x, k, y, ys[3];
    ys[0] = py0, ys[1] = py0 + ph / 2, ys[2] = py0 + ph;
    for (k = 0; k < 3; ++k)
        for (x = 0; x < 240; ++x)
            if (x % 4 < 2) px[ys[k] * BHC_W + BHC_PX0 + x] = bhp_grey(BHP_GRID);
    for (k = 0; k < n; ++k)
        for (y = py0 + ph + 3; y < py0 + ph + 6; ++y) px[y * BHC_W + BHC_PX0 + 5 * idx[k] / 2] = bhp_grey(BHP_TICK);
}

static int bhp_has(const struct bh_bucket *k) { return !(k->flags & BH_F_GAP); }

/* The faint band behind the bars: each bucket on external power is its slice of the plot (bucket i from BHC_PX0 + 5 i / 2 to BHC_PX0 + 5 (i + 1) / 2), the plot's height. */
static void bhp_band(unsigned *px, const struct bh_view *v, int py0, int ph) {
    int i;
    for (i = 0; i < BH_BUCKETS; ++i)
        if (bhp_has(&v->b[i]) && (v->b[i].flags & BH_F_CHG))
            bhp_rect(px, BHC_PX0 + 5 * i / 2, py0, 5 * (i + 1) / 2 - 5 * i / 2, ph, bhp_px(255, 0x2A, 0x2A, 0x2C));
}

static void bhp_level(unsigned *px, const struct bh_view *v, const int *idx, int n) {
    int j;
    bhp_card(px, BHL_H, BHL_CARD);
    bhp_grid(px, BHL_PY0, BHL_PH, idx, n);
    for (j = 0; j < 48; ++j) {
        const struct bh_bucket *e = &v->b[2 * j], *l = &v->b[2 * j + 1];
        int lev = bhp_has(l) && l->level <= 100   ? l->level
                  : bhp_has(e) && e->level <= 100 ? e->level
                                                  : -1,
            chg = (bhp_has(e) && (e->flags & BH_F_CHG)) || (bhp_has(l) && (l->flags & BH_F_CHG)), h;
        unsigned c;
        if (lev < 0) continue;
        h = (lev * BHL_PH + 50) / 100;
        c = chg ? bhp_px(255, 0x34, 0xC7, 0x59) : lev <= BHP_LOW ? bhp_px(255, 0xFF, 0x14, 0x48) : bhp_grey(BHP_LEVEL);
        bhp_rect(px, BHC_PX0 + BHL_PITCH * j, BHL_PY0 + BHL_PH - h, BHL_BAR, h, c);
    }
}

static void bhp_activity(unsigned *px, const struct bh_view *v, const int *idx, int n) {
    int m, i;
    bhp_card(px, BHA_H, BHA_CARD);
    bhp_band(px, v, BHA_PY0, BHA_PH);
    bhp_grid(px, BHA_PY0, BHA_PH, idx, n);
    for (m = 0; m < 24; ++m) {
        unsigned on = 0, play = 0, hon, hpl;
        for (i = 4 * m; i < 4 * m + 4; ++i)
            if (bhp_has(&v->b[i])) on += v->b[i].on * 8u, play += v->b[i].play * 8u;
        hon = (on * BHA_PH + 1800) / 3600, hpl = (play * BHA_PH + 1800) / 3600;
        if (hpl > BHA_PH - hon) hpl = BHA_PH - hon;
        bhp_rect(px, BHC_PX0 + BHA_PITCH * m, BHA_PY0 + BHA_PH - hon, BHA_BAR, hon,
                 bhp_px(255, bhp_kind[0][0], bhp_kind[0][1], bhp_kind[0][2]));
        bhp_rect(px, BHC_PX0 + BHA_PITCH * m, BHA_PY0 + BHA_PH - hon - hpl, BHA_BAR, hpl,
                 bhp_px(255, bhp_kind[1][0], bhp_kind[1][1], bhp_kind[1][2]));
    }
    bhp_mark(px, 14, BHA_LEGEND_Y, 0);
    bhp_mark(px, 124, BHA_LEGEND_Y, 1);
}

/* The Since Last Charge card: the card, the stacked bar (screen on, playing with the screen off, standby; rounded ends) and the three rows' marks (on the name's line) and hairlines. The seconds are halved until the total is under 2**20. */
static void bhp_summary(unsigned *px, const struct bh_view *v) {
    unsigned total = v->sc_total, on = v->sc_on, play = v->sc_play;
    int e1 = 0, e2 = 0, x, y, k;
    if (on > total) on = total;
    if (play > total - on) play = total - on;
    while (total > 0xFFFFF) total >>= 1, on >>= 1, play >>= 1;
    if (total)
        e1 = (int)((BHP_BAR_W * on + total / 2) / total), e2 = (int)((BHP_BAR_W * (on + play) + total / 2) / total);
    bhp_card(px, BHS_CARD, BHS_CARD);
    for (y = BHS_BAR_Y; y < BHS_BAR_Y + BHS_BAR_H; ++y)
        for (x = BHS_PAD; x < BHS_PAD + BHP_BAR_W; ++x)
            bhp_blend(px, x, y,
                      bhp_kind[x - BHS_PAD < e1   ? 0
                               : x - BHS_PAD < e2 ? 1
                                                  : 2],
                      bhp_cover(x, y, BHS_PAD, BHS_BAR_Y, BHP_BAR_W, BHS_BAR_H, BHS_BAR_H / 2));
    for (k = 0; k < 3; ++k) {
        bhp_mark(px, BHS_MARK_X, BHS_ROW0_Y + BHS_ROW_H * k + BHS_MARK_CY, k);
        if (k) bhp_rect(px, BHS_PAD, BHS_ROW0_Y + BHS_ROW_H * k, BHP_BAR_W, 1, bhp_grey(BHP_HAIR));
    }
}

/* The bitmap k (0 card, 1 level, 2 activity) locked for writing, made the first time; 0 with no memory. */
static unsigned *bhp_lock(int k) {
    unsigned *px;
    void *b = bhp.bmp[k] ? bhp.bmp[k]
                         : bitmap_create_ex(BHC_W,
                                            k == 2 ? BHA_H
                                            : k    ? BHL_H
                                                   : BHS_CARD,
                                            BHC_W * 4, BITMAP_RGBA8888);
    if (!b) return (unsigned *)0;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != (unsigned)(BHC_W * 4)) {
        if (px) bitmap_unlock_buffer(b);
        if (!bhp.bmp[k]) bitmap_destroy(b);
        return (unsigned *)0;
    }
    bhp.bmp[k] = b;
    return px;
}

static int bhp_on_paint(void *ctx, void *e) {
    int k = (int)(long)ctx;
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    if (bhp.win && canvas && bhp.bmp[k])
        peq_blit(canvas, bhp.bmp[k], BHC_W, k == 2 ? BHA_H : k ? BHL_H : BHS_CARD, BHC_X, 0);
    return RET_OK;
}

static int bhp_on_destroy(void *ctx, void *e) {
    int k;
    (void)ctx;
    (void)e;
    for (k = 0; k < 3; ++k)
        if (bhp.bmp[k]) bitmap_destroy(bhp.bmp[k]);
    memset(&bhp, 0, sizeof bhp);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The texts
 */
/* "4 h 18 min", "2 h", "45 min": rounded to the minute. */
static void bhp_dur(char *out, unsigned size, unsigned secs) {
    unsigned m = (secs + 30) / 60;
    if (m >= 60 && m % 60)
        pc_fmt2(out, size, TR("%d h %d min"), m / 60, m % 60);
    else if (m >= 60)
        pc_fmt(out, size, TR("%d h"), m / 60);
    else
        pc_fmt(out, size, TR("%d min"), m);
}

/* A tick's label (both charts): "18:00" or "6 PM". */
static void bhp_hour(char *out, unsigned size, int hour) {
    if (dt_24h())
        snprintf(out, size, "%02d:00", hour);
    else
        snprintf(out, size, "%d %s", hour % 12 ? hour % 12 : 12, hour < 12 ? "AM" : "PM");
}

/* One Since Last Charge row's percent the gauge fell, "~12%" (bold: the estimate is the row's figure). */
static void bhp_pct(int k, unsigned d) {
    char num[12];
    snprintf(num, sizeof num, "~%u%%", d);
    bhp_text(bhp.sc_pct[k], num);
    ly_title_face(bhp.sc_pct[k], num);
}

/* The bucket boundaries (0 .. 95) of the view that fall on a local multiple of six hours, and their local hours: four of them. The zone's offset is the one at the open bucket. */
static int bhp_ticks(const struct bh_view *v, int *idx, int *hr) {
    long t = (long)v->head * BH_SECS, off = 0;
    int i, n = 0;
    const int *tm = localtime(&t);
    if (tm) off = ((long)tm[2] * 3600 + tm[1] * 60 + tm[0] - t % 86400 + 86400) % 86400;
    for (i = 0; i < BH_BUCKETS && n < 4; ++i) {
        long tod = (((long)v->head - (BH_BUCKETS - 1) + i) * BH_SECS + off) % 86400;
        if (tod % 21600 == 0) idx[n] = i, hr[n++] = (int)(tod / 3600);
    }
    return n;
}

/* The local time of day t as 24-Hour Time says it: "21:25" or "9:25 PM". */
static void bhp_clock(char *out, unsigned size, long t) {
    const int *tm = localtime(&t);
    int h = tm ? tm[2] : 0, m = tm ? tm[1] : 0;
    if (dt_24h())
        snprintf(out, size, "%02d:%02d", h, m);
    else
        snprintf(out, size, "%d:%02d %s", h % 12 ? h % 12 : 12, m, h < 12 ? "AM" : "PM");
}

/* The local calendar date of t as year * 10000 + month * 100 + day into *d, and its seconds into the day; -1 when localtime has none. */
static long bhp_date(long t, long *d) {
    const int *tm = localtime(&t);
    if (!tm) return -1;
    *d = (long)(tm[5] + 1900) * 10000 + (tm[4] + 1) * 100 + tm[3];
    return (long)tm[2] * 3600 + tm[1] * 60 + tm[0];
}

/* The caption's time: the clock when t is on the local day of now, "yesterday 21:25" the day before, else "11-14 21:25". localtime has one buffer, so each date is copied out at once. The day before is the date half a day before the local midnight by the clock, which a DST step (it moves that point by its hour) leaves inside yesterday. */
static void bhp_when(char *out, unsigned size, long t, long now) {
    long dt, dn, dy, sod = bhp_date(now, &dn);
    char clock[16];
    bhp_clock(clock, sizeof clock, t);
    if (bhp_date(t, &dt) < 0 || sod < 0 || bhp_date(now - sod - 43200, &dy) < 0 || dt == dn)
        snprintf(out, size, "%s", clock);
    else if (dt == dy)
        dur_subst(out, size, TR("yesterday %s"), 0, clock, (const char *)0);
    else
        snprintf(out, size, "%02d-%02d %s", (int)(dt / 100 % 100), (int)(dt % 100), clock);
}

/* The Since Last Charge card's texts: "Unplugged 21:25, 100%" (or "Recording since 14:05, 85%" when the run began with the recording; without the level when it is unknown), the total on battery in bold, "58% left", and the three kinds' durations and percents (standby is the rest of the total). */
static void bhp_since(const struct bh_view *v, long now) {
    char line[96], when[40], lvl[8], dur[24];
    unsigned rest = v->sc_total > v->sc_on + v->sc_play ? v->sc_total - v->sc_on - v->sc_play : 0;
    bhp_when(when, sizeof when, v->unplug_at, now);
    snprintf(lvl, sizeof lvl, "%u%%", v->unplug_lvl);
    if (v->unplug_lvl <= 100)
        dur_subst(line, sizeof line, v->since_on ? TR("Recording since %s, %s") : TR("Unplugged %s, %s"), 0, when, lvl);
    else
        dur_subst(line, sizeof line, v->since_on ? TR("Recording since %s") : TR("Unplugged %s"), 0, when,
                  (const char *)0);
    bhp_text(bhp.cap, line);
    bhp_dur(dur, sizeof dur, v->sc_total);
    bhp_text(bhp.dur, dur);
    ly_title_face(bhp.dur, dur);
    line[0] = 0;
    if (v->level <= 100) {
        snprintf(lvl, sizeof lvl, "%u%%", v->level);
        dur_subst(line, sizeof line, TR("%s left"), 0, lvl, (const char *)0);
    }
    bhp_text(bhp.left, line);
    bhp_dur(dur, sizeof dur, v->sc_on);
    bhp_text(bhp.sc_val[0], dur);
    bhp_dur(dur, sizeof dur, v->sc_play);
    bhp_text(bhp.sc_val[1], dur);
    bhp_dur(dur, sizeof dur, rest);
    bhp_text(bhp.sc_val[2], dur);
    bhp_pct(0, v->sc_d_on);
    bhp_pct(1, v->sc_d_play);
    bhp_pct(2, v->sc_d_idle);
}

/* ---------------------------------------------------------------------------
 * The page
 */
static void *bhp_find(void *win, const char *name) { return widget_lookup(win, name, 1); }

/* The page's widgets, bound the first time the window shows; 0 when the asset is not ours. */
static int bhp_init(void *win) {
    static const char *const names[I_COUNT] = {"pod_note0", "pod_note1", "pod_sec0", "pod_hist0", "pod_note2",
                                               "pod_sec1",  "pod_hist1", "pod_sec2", "pod_hist2", "pod_note3"};
    char nm[24];
    int i, k;
    if (bhp.win == win) return 1;
    memset(&bhp, 0, sizeof bhp);
    for (i = 0; i < I_COUNT; ++i)
        if (!(bhp.item[i] = bhp_find(win, names[i]))) goto bad;
    for (k = 0; k < 2; ++k)
        for (i = 0; i < 4; ++i) {
            snprintf(nm, sizeof nm, k ? "pod_ha_t%d" : "pod_hl_t%d", i);
            if (!(bhp.tick[k][i] = bhp_find(win, nm))) goto bad;
        }
    for (i = 0; i < 3; ++i) {
        snprintf(nm, sizeof nm, "pod_ha_a%d", i);
        if (!(bhp.axis[i] = bhp_find(win, nm))) goto bad;
        snprintf(nm, sizeof nm, "pod_hs_d%d", i);
        bhp.sc_val[i] = bhp_find(win, nm);
        snprintf(nm, sizeof nm, "pod_hs_p%d", i);
        bhp.sc_pct[i] = bhp_find(win, nm);
        if (!bhp.sc_val[i] || !bhp.sc_pct[i]) goto bad;
    }
    bhp.cap = bhp_find(win, "pod_hs_cap");
    bhp.dur = bhp_find(win, "pod_hs_dur");
    bhp.left = bhp_find(win, "pod_hs_left");
    if (!bhp.cap || !bhp.dur || !bhp.left) goto bad;
    bhp.win = win;
    widget_on(bhp.item[I_HIST0], EVT_BEFORE_PAINT, bhp_on_paint, (void *)0L);
    widget_on(bhp.item[I_HIST1], EVT_BEFORE_PAINT, bhp_on_paint, (void *)1L);
    widget_on(bhp.item[I_HIST2], EVT_BEFORE_PAINT, bhp_on_paint, (void *)2L);
    widget_on(win, EVT_DESTROY, bhp_on_destroy, (void *)0);
    return 1;
bad: /* an asset that is not ours: the items stay hidden */
    memset(&bhp, 0, sizeof bhp);
    return 0;
}

/* The state the page's items show: 0 off, 1 on with no closed bucket yet, 2 data; fills the bitmaps and the texts in that last case. */
void bhpage_show(void *win) {
    struct bh_view v;
    char buf[40];
    int idx[4], hr[4], nt = 0, mode = 0, i, k;
    static const unsigned char show[3][I_COUNT] = {
        {1, 0, 0, 0, 0, 0, 0, 0, 0, 0}, /* off: the long note */
        {0, 1, 0, 0, 0, 0, 0, 0, 0, 1}, /* on, nothing complete yet: the short note and the empty note */
        {0, 1, 1, 1, 1, 1, 1, 1, 1,
         0}}; /* the data (the Since Last Charge header, card and note only with an unplug_at) */
    if (!bhp_init(win)) return;
    if (bh_setting() && bh_snapshot(&v)) {
        mode = 1;
        for (i = 0; i < BH_BUCKETS - 1; ++i)
            if (bhp_has(&v.b[i])) mode = 2;
    } else if (bh_setting())
        mode = 1;
    for (i = 0; i < I_COUNT; ++i) widget_set_visible(bhp.item[i], show[mode][i], 0);
    if (mode != 2) return;
    widget_set_visible(bhp.item[I_SEC0], v.unplug_at != 0, 0); /* hidden until a charger removal was seen: no dashes */
    widget_set_visible(bhp.item[I_HIST0], v.unplug_at != 0, 0);
    widget_set_visible(bhp.item[I_NOTE2], v.unplug_at != 0, 0);
    nt = bhp_ticks(&v, idx, hr);
    for (k = 0; k < 3; ++k) {
        unsigned *px;
        if (!k && !v.unplug_at) continue;
        px = bhp_lock(k);
        if (px) {
            if (!k)
                bhp_summary(px, &v);
            else if (k == 2)
                bhp_activity(px, &v, idx, nt);
            else
                bhp_level(px, &v, idx, nt);
            bitmap_unlock_buffer(bhp.bmp[k]);
        }
        if (!k) continue;
        for (i = 0; i < 4; ++i) {
            bhp_hour(buf, sizeof buf, hr[i]);
            bhp_text(bhp.tick[k - 1][i], buf);
            widget_move(bhp.tick[k - 1][i], BHC_X + BHC_PX0 + 5 * idx[i] / 2 - BHC_TICK_W / 2,
                        (k == 2 ? BHA_TICK_Y : BHL_TICK_Y) - 9);
        }
    }
    pc_fmt(buf, sizeof buf, TR("%d min"), 60);
    bhp_text(bhp.axis[0], buf);
    pc_fmt(buf, sizeof buf, TR("%d min"), 30);
    bhp_text(bhp.axis[1], buf);
    bhp_text(bhp.axis[2], "0");
    if (v.unplug_at) bhp_since(&v, time((long *)0));
}
