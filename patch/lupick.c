/* Update Library > Choose Folders: our folder picker in place of stock's systemset/specfolder_page (docs/modules/libupdate.md "The folder picker").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One window for every level, ui/m1plus_lupick.bin (tools/pod_ui.py build_lupick_page): the Folders page's structure (patch/folders.c): the glass navbar (Back, the title, the Select All text button)
 * over a stock list whose one content view paints the rows itself (a rounded card, a select circle, the name, a chevron), and a bar at the bottom with the Scan pill. No widget per row, so a level may hold
 * any number of folders (LP_MAX are read).
 *
 *   levels   a level is the directory `path` (the card's /mnt/mmc at the root); its folders are read with opendir / readdir by the filter of stock's toolsLoadDirectory (0x5e85c8): directories only (d_type 4;
 *            a link or unknown type by one opendir), no name starting with '.', and not lost+found, System Volume Information, RECYCLER, $RECYCLE.BIN, lockscreenimage; the listing of /mnt/mmc/Android/data
 *            (0x5e86bc) is empty. Sorted by the lists' name order (cc_key_cmp), not stock's own comparator (algo_sort_if, not read).
 *   chevron  a row shows one when its folder holds a folder: found by a timer, one row per tick for the rows in view, the first folder found ends the probe (LP_PROBE_MAX entries at most). A row not probed yet
 *            has no chevron and a tap on it probes it first.
 *   select   a set of full paths (LP_SELMAX), kept across the levels of this visit. A folder in the set covers everything under it: those rows show selected, dimmed and cannot be toggled; selecting a folder
 *            takes its selected descendants out of the set, so nothing is scanned twice. The circle toggles; the rest of a row opens the folder when it holds one, else toggles. Select All toggles the rows of the
 *            current level that are not covered.
 *   scan     the pill is stock's btn_startscan (0x4ac9f8): stop_player, a "char*" deque of the full paths, navigator_back (this page closes, so the dialog returns to Update Library), then
 *            navigator_to_with_context("dialog/scanmusic_dialog", {deque, 0, 1, 0}). Stock destroys the deque right after that call while the dialog's worker thread (scanSpecFolder, 0x4e9e90) reads it; we keep
 *            it and lu_scan_finish (patch/libupdate.c) destroys it at the first finished tick, when the worker has returned.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "azlist.h"
#include "i18n.h"
#include "entries.h"
#include "selmode.h"

#define ROW POD_ROW_H
#define LP_ASSET "m1plus_lupick"
#define LP_ROOT "/mnt/mmc"
#define LP_W 320 /* the content view's width */
#define LP_CARD_X 10 /* the card, as the Settings cards (CM, CARD_W, CARD_R in tools/pod_settings.py) */
#define LP_CARD_W 300
#define LP_CARD_R 12
#define LP_CARD_RGB 0xff1e1c1cu /* SURFACE #1C1C1E as a color_t word */
#define LP_PRESS_RGB 0xff2e2c2cu /* RAISED #2C2C2E */
#define LP_DIM_RGB 0xa01e1c1cu /* over a covered row's mark: the card's colour at 63 % */
#define LP_TOP_ROOT 44 /* the card's top under the caption of the root ("MUSIC CARD"), else under the navbar */
#define LP_TOP 10
#define LP_END 24
#define LP_CAP_X 24 /* the caption's text */
#define LP_MARK_X 22 /* the select circle (SG_MARK px) */
#define LP_MARK_ZONE 54 /* a tap left of this is the circle's */
#define LP_TEXT_X 58
#define LP_TEXT_END 280
#define LP_HAIR_END (LP_CARD_X + LP_CARD_W)
#define LP_MAX 1500 /* folders read of one level (the rest is not shown) */
#define LP_SELMAX 256 /* folders in the set (a further tap is ignored) */
#define LP_PATH 512 /* the longest full path (a folder whose path is longer is not listed) */
#define LP_NAME 256
#define LP_DEPTH 24 /* levels whose scroll offset is kept (deeper levels return to the top) */
#define LP_PROBE_MS 16
#define LP_PROBE_MAX 4000 /* entries read to find a folder's first folder */
#define LP_CAP_KEY (1 << 20) /* the caption's tile */
#define LP_NAMES_MAX (256 * 1024)

static struct {
    void *win, *view, *sv, *status, *title, *fade, *back, *selall, *scan, *bar;
    void *st_title, *st_dim,
        *st_cap; /* hidden labels whose styles are the row's text, the covered row's and the caption's */
    void *mark[2], *chev;
    grid_t g;
    char path[LP_PATH];
    int depth;
    int offs[LP_DEPTH];
    char *names; /* the level's folder names, NUL separated */
    unsigned names_n, names_cap;
    unsigned *off; /* name offsets, in the order read, then sorted (LP_MAX) */
    unsigned n;
    unsigned char *sub; /* by row: 0 not probed, 1 holds a folder, 2 none */
    char *selp[LP_SELMAX];
    int nsel;
    int press, down, title_on, noscroll;
    m1_tap_t tap;
    unsigned probe_timer;
    void *pending; /* the deque of the scan being started (see lu_scan_finish) */
} lp __attribute__((section(".scratch")));

static void lp_kick(void);

/* ---------------------------------------------------------------------------------------------------------------------------------------- reading a level */

static const char *const lp_junk[] = {
    "lost+found", "System Volume Information", "RECYCLER", "$RECYCLE.BIN",   ".LOST.DIR",
    ".fseventsd", ".Spotlight-V100",           ".Trashes", "lockscreenimage"};

/* The directory entry `ent` of `parent` as a folder this page lists: its name, else NULL. */
static const char *lp_dir_name(const char *parent, char *ent) {
    const char *name = ent + 11; /* struct dirent: d_type at 10, d_name at 11 */
    unsigned i;
    char full[LP_PATH];
    if (name[0] == '.' || name[0] == 0 || strlen(name) >= LP_NAME) return (const char *)0;
    if (ent[10] != 4) {
        void *d;
        if (ent[10] != 0 && ent[10] != 10)
            return (const char *)0; /* only an unknown type or a link may still be a folder */
        if (strlen(parent) + 1 + strlen(name) >= sizeof full) return (const char *)0;
        snprintf(full, sizeof full, "%s/%s", parent, name);
        d = opendir(full);
        if (!d) return (const char *)0;
        closedir(d);
    }
    for (i = 0; i < sizeof lp_junk / sizeof lp_junk[0]; i++)
        if (strcmp(name, lp_junk[i]) == 0) return (const char *)0;
    return name;
}

static int lp_blocked(const char *path) { return strcmp(path, "/mnt/mmc/Android/data") == 0; }

/* Whether the folder `path` holds a folder: the first one found. A folder whose first LP_PROBE_MAX entries are no folder may still hold one further on: it counts as holding one (the row opens; a level with none shows "No folders"). */
static int lp_holds(const char *path) {
    void *d;
    char *ent;
    int n = 0, found = 0;
    if (lp_blocked(path) || !(d = opendir(path))) return 0;
    while (!found && (ent = readdir(d)) != (char *)0)
        if (n++ >= LP_PROBE_MAX || lp_dir_name(path, ent)) found = 1;
    closedir(d);
    return found;
}

static const char *lp_name(unsigned i) { return lp.names + lp.off[i]; }
static int lp_cmp(unsigned a, unsigned b) {
    int c = cc_key_cmp(lp_name(a), lp_name(b));
    return c ? c : a < b ? -1 : a > b;
}

static void lp_free_level(void) {
    free(lp.names);
    free(lp.off);
    free(lp.sub);
    lp.names = (char *)0, lp.off = (unsigned *)0, lp.sub = (unsigned char *)0;
    lp.names_n = lp.names_cap = lp.n = 0;
}

/* The path's folders into names / off, sorted. */
static void lp_read(void) {
    void *d;
    char *ent;
    unsigned *ord, i;
    char *sorted;
    unsigned sn = 0;
    lp_free_level();
    if (lp_blocked(lp.path) || !(d = opendir(lp.path))) return;
    lp.off = calloc(LP_MAX, sizeof(unsigned));
    if (!lp.off) {
        closedir(d);
        return;
    }
    while (lp.n < LP_MAX && (ent = readdir(d)) != (char *)0) {
        const char *name = lp_dir_name(lp.path, ent);
        unsigned len;
        if (!name) continue;
        len = (unsigned)strlen(name) + 1;
        if (strlen(lp.path) + 1 + len > LP_PATH) continue;
        if (lp.names_n + len > lp.names_cap) {
            unsigned cap = lp.names_cap ? lp.names_cap * 2 : 4096;
            char *p;
            if (cap > LP_NAMES_MAX || lp.names_n + len > cap) break;
            p = calloc(cap, 1);
            if (!p) break;
            if (lp.names) memcpy(p, lp.names, lp.names_n);
            free(lp.names);
            lp.names = p, lp.names_cap = cap;
        }
        memcpy(lp.names + lp.names_n, name, len);
        lp.off[lp.n++] = lp.names_n;
        lp.names_n += len;
    }
    closedir(d);
    if (!lp.n) return;
    ord = calloc(lp.n, sizeof(unsigned));
    sorted = calloc(lp.names_n, 1);
    if (ord && sorted) {
        for (i = 0; i < lp.n; i++) ord[i] = i;
        cc_heapsort(ord, lp.n, lp_cmp);
        for (i = 0; i < lp.n; i++) {
            const char *nm = lp_name(ord[i]);
            unsigned len = (unsigned)strlen(nm) + 1;
            memcpy(sorted + sn, nm, len);
            ord[i] = sn;
            sn += len;
        }
        memcpy(lp.names, sorted, sn);
        memcpy(lp.off, ord, lp.n * sizeof(unsigned));
    }
    free(ord);
    free(sorted);
    lp.sub = calloc(lp.n, 1);
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- the selection */

static int lp_child(unsigned r, char *out, unsigned n) {
    if (strlen(lp.path) + 1 + strlen(lp_name(r)) >= n) return 0;
    snprintf(out, n, "%s/%s", lp.path, lp_name(r));
    return 1;
}

static int lp_under(const char *path, const char *dir) { /* path is strictly under dir */
    unsigned n = (unsigned)strlen(dir), i;
    for (i = 0; i < n; i++)
        if (path[i] != dir[i]) return 0;
    return path[n] == '/';
}

static int lp_find(const char *path) {
    int i;
    for (i = 0; i < lp.nsel; i++)
        if (strcmp(lp.selp[i], path) == 0) return i;
    return -1;
}

/* A selected folder above `path` (path itself excluded). */
static int lp_covered(const char *path) {
    int i;
    for (i = 0; i < lp.nsel; i++)
        if (lp_under(path, lp.selp[i])) return 1;
    return 0;
}

static void lp_drop(int i) {
    free(lp.selp[i]);
    lp.selp[i] = lp.selp[--lp.nsel];
}

/* Adding `path` drops the selected folders under it, so the limit is on the size after that: size - dropped + 1. 1 added, 0 over the limit, -1 out of memory. */
static int lp_select(const char *path) {
    int i, dropped = 0;
    char *c;
    for (i = 0; i < lp.nsel; i++)
        if (lp_under(lp.selp[i], path)) dropped++;
    if (lp.nsel - dropped >= LP_SELMAX) return 0;
    c = calloc(strlen(path) + 1, 1);
    if (!c) return -1;
    for (i = lp.nsel - 1; i >= 0; i--)
        if (lp_under(lp.selp[i], path)) lp_drop(i);
    memcpy(c, path, strlen(path) + 1);
    lp.selp[lp.nsel++] = c;
    return 1;
}

/* 0 plain, 1 selected, 2 covered by a folder above (selected, dimmed, not toggleable) */
static int lp_state(unsigned r) {
    char full[LP_PATH];
    if (!lp_child(r, full, sizeof full)) return 2;
    if (lp_covered(full)) return 2;
    return lp_find(full) >= 0;
}

static void lp_toggle(unsigned r) {
    char full[LP_PATH];
    int i;
    if (r >= lp.n || !lp_child(r, full, sizeof full) || lp_covered(full)) return;
    i = lp_find(full);
    if (i >= 0)
        lp_drop(i);
    else
        lp_select(full);
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- geometry */

static int lp_root(void) { return strcmp(lp.path, LP_ROOT) == 0; }
static int lp_top(void) { return lp_root() ? LP_TOP_ROOT : LP_TOP; }
static int lp_row_y(int r) { return lp_top() + r * ROW; }
static int lp_content(void) { return lp_top() + (int)lp.n * ROW + LP_END + SG_BAR_H; }
static int lp_off(void) { return grid_sv_off(lp.sv); }
static int lp_max_scroll(void) {
    int m = lp_content() - GRID_VIEW_H;
    return m > 0 ? m : 0;
}
static int lp_at(int y) {
    int r = (y - lp_top()) / ROW;
    return y < lp_top() || r >= (int)lp.n ? -1 : r;
}
static void lp_span(int *r0, int *r1) {
    int s = lp_off(), n = (int)lp.n;
    *r0 = s <= lp_top() ? 0 : (s - lp_top()) / ROW;
    *r1 = s + GRID_VIEW_H - 1 < lp_top() ? -1 : (s + GRID_VIEW_H - 1 - lp_top()) / ROW;
    if (*r1 > n - 1) *r1 = n - 1;
}

static grid_tile_t *lp_tile(int r) {
    int r0, r1, fresh;
    grid_tile_t *t;
    lp_span(&r0, &r1);
    t = grid_tile(&lp.g, r, r0, r1, &fresh);
    if (fresh) {
        char title[LP_NAME];
        snprintf(title, sizeof title, "%s", lp_name((unsigned)r));
        grid_set(t, title, "", 0);
    }
    return t;
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- paint */

static void lp_blit(void *canvas, void *bmp, int w, int h, int x, int y) {
    grid_blit_from(canvas, bmp, 0, 0, w, h, x, y, GRID_VIEW_H);
}

static void lp_paint_rows(void *canvas) {
    int r0, r1, r, off = lp_off(), n = (int)lp.n;
    lp_span(&r0, &r1);
    m1_capsule(canvas, GRID_VIEW_H, LP_CARD_X, lp_top() - off, LP_CARD_W, n * ROW, LP_CARD_R, LP_CARD_RGB);
    if (lp.press && lp.press - 1 >= r0 &&
        lp.press - 1 <= r1) { /* the pressed row: its fill follows the card's corners at the ends */
        int p = lp.press - 1, y = lp_row_y(p) - off;
        if (n == 1)
            m1_capsule(canvas, GRID_VIEW_H, LP_CARD_X, y, LP_CARD_W, ROW, LP_CARD_R, LP_PRESS_RGB);
        else if (p == 0) {
            m1_capsule(canvas, GRID_VIEW_H, LP_CARD_X, y, LP_CARD_W, ROW + LP_CARD_R, LP_CARD_R, LP_PRESS_RGB);
            az_fill(canvas, LP_CARD_X, y + ROW, y + ROW + LP_CARD_R, LP_CARD_W, LP_CARD_RGB);
        } else if (p == n - 1) {
            m1_capsule(canvas, GRID_VIEW_H, LP_CARD_X, y - LP_CARD_R, LP_CARD_W, ROW + LP_CARD_R, LP_CARD_R,
                       LP_PRESS_RGB);
            az_fill(canvas, LP_CARD_X, y - LP_CARD_R, y, LP_CARD_W, LP_CARD_RGB);
        } else
            az_fill(canvas, LP_CARD_X, y, y + ROW, LP_CARD_W, LP_PRESS_RGB);
    }
    for (r = r0; r <= r1; ++r) {
        int y = lp_row_y(r) - off, st = lp_state((unsigned)r);
        lp_blit(canvas, lp.mark[st != 0], SG_MARK, SG_MARK, LP_MARK_X, y + (ROW - SG_MARK) / 2);
        if (st == 2) az_fill(canvas, LP_MARK_X, y + (ROW - SG_MARK) / 2, y + (ROW + SG_MARK) / 2, SG_MARK, LP_DIM_RGB);
        if (lp.sub && lp.sub[r] == 1)
            lp_blit(canvas, lp.chev, POD_CHEV_W, POD_CHEV_H, LIST_CHEV_X, y + (ROW - 1 - POD_CHEV_H) / 2);
        if (r < n - 1) az_fill(canvas, LP_TEXT_X, y + ROW - 1, y + ROW, LP_HAIR_END - LP_TEXT_X, CARD_HAIR);
    }
    for (r = r0; r <= r1; ++r) {
        int y = lp_row_y(r) - off;
        widget_prepare_text_style(lp_state((unsigned)r) == 2 ? lp.st_dim : lp.st_title, canvas);
        grid_text(canvas, lp_tile(r), 0, LP_TEXT_X, y + (ROW - LIST_TITLE_H) / 2, LP_TEXT_END - LP_TEXT_X, LIST_TITLE_H,
                  0);
    }
    if (lp_root()) {
        grid_tile_t *t;
        int fresh;
        t = grid_tile(&lp.g, LP_CAP_KEY, 0, 0, &fresh);
        if (fresh) grid_set(t, TR("MUSIC CARD"), "", 0);
        widget_prepare_text_style(lp.st_cap, canvas);
        grid_text(canvas, t, 0, LP_CAP_X, 14 - off, LP_W - 2 * LP_CAP_X, 22, 0);
    }
}

static int lp_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = lp_off();
    (void)ctx;
    if (!canvas || !lp.view || !lp.g.tiles || !lp.n) return RET_OK;
    I(canvas, CANVAS_OY) += off;
    lp_paint_rows(canvas);
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- the page's state shown */

static const char *lp_title(void) {
    const char *s = strrchr(lp.path, '/');
    return lp_root() ? TR("Choose Folders") : s ? s + 1 : lp.path;
}

static void lp_title_update(void) {
    az_fit(lp.title, lp_title());
    if (lp.fade) grid_fade(lp.fade, lp_off() > 0);
}

enum { LP_SA_NONE, LP_SA_ADD, LP_SA_CLEAR };
static int lp_selall_action(void);

/* The Select All button says what a tap does (lp_selall_action): Select All, Deselect All, or Deselect All dimmed and inert when the tap would do nothing. */
static void lp_selall_label(void) {
    int act = lp_selall_action();
    widget_set_tr_text(lp.selall, act == LP_SA_ADD ? "Select All" : "Deselect All");
    m1_selall_fit(lp.selall);
    widget_set_sensitive(lp.selall, act != LP_SA_NONE);
    widget_set_prop_bool(lp.selall, "enable",
                         act != LP_SA_NONE); /* the style's disable state follows the enable flag, not sensitive */
}

/* The pill: "Scan N Folders", dimmed and inert with none. */
static void lp_pill(void) {
    char buf[96];
    if (lp.nsel == 0)
        snprintf(buf, sizeof buf, "%s", TR("Scan Folders"));
    else if (lp.nsel == 1)
        snprintf(buf, sizeof buf, "%s", TR("Scan 1 Folder"));
    else
        m1_fmt(buf, sizeof buf, TR("Scan %d Folders"), lp.nsel);
    widget_set_text_utf8(lp.scan, buf);
    widget_set_sensitive(lp.scan, lp.nsel != 0);
    widget_set_prop_bool(lp.scan, "enable",
                         lp.nsel != 0); /* the style's disable state follows the enable flag, not sensitive */
}

static void lp_changed(void) {
    lp_pill();
    lp_selall_label();
    grid_sv_redraw(lp.sv);
}

static void lp_size(void) {
    int h = lp.n ? lp_content() : GRID_VIEW_H;
    widget_resize(lp.view, LP_W, h);
    widget_set_prop_int(lp.sv, "virtual_h", h);
}

static void lp_load(int at) {
    int m;
    lp_read();
    grid_drop(&lp.g);
    m1_timer_stop(&lp.probe_timer);
    lp.press = lp.down = 0;
    m1_show(lp.view, lp.n != 0);
    m1_show(lp.status, lp.n == 0);
    if (!lp.n) widget_set_tr_text(lp.status, "No folders");
    lp_size();
    m = lp_max_scroll();
    widget_set_prop_int(lp.sv, "yoffset", at < 0 ? 0 : at > m ? m : at);
    lp.title_on = -1;
    lp_title_update();
    lp_changed();
    lp_kick();
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- the chevron probe */

static int lp_next_probe(void) {
    int r0, r1, r;
    if (!lp.sub) return -1;
    lp_span(&r0, &r1);
    for (r = r0; r <= r1; ++r)
        if (!lp.sub[r]) return r;
    return -1;
}

static int lp_probe(unsigned r) {
    char full[LP_PATH];
    lp.sub[r] = lp_child(r, full, sizeof full) && lp_holds(full) ? 1 : 2;
    return lp.sub[r];
}

static int lp_on_probe(const void *unused) {
    int r;
    (void)unused;
    lp.probe_timer = 0;
    if (!lp.view) return RET_OK;
    if (grid_moving(lp.sv)) {
        lp_kick();
        return RET_OK;
    }
    r = lp_next_probe();
    if (r >= 0) {
        lp_probe((unsigned)r);
        grid_sv_redraw(lp.sv);
    }
    lp_kick();
    return RET_OK;
}

static void lp_kick(void) {
    if (!lp.probe_timer && lp.view && lp_next_probe() >= 0)
        lp.probe_timer = timer_add(lp_on_probe, (void *)0, LP_PROBE_MS);
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- taps */

static void lp_enter(unsigned r) {
    char full[LP_PATH];
    if (!lp_child(r, full, sizeof full)) return;
    if (lp.depth < LP_DEPTH) lp.offs[lp.depth] = lp_off();
    lp.depth++;
    memcpy(lp.path, full, strlen(full) + 1);
    lp_load(0);
}

/* A row's tap: the circle toggles; the rest opens a folder that holds one, else toggles. */
static void lp_tap(unsigned r, int x) {
    if (r >= lp.n || !lp.sub) return;
    if (x >= LP_MARK_ZONE) {
        if (!lp.sub[r]) lp_probe(r);
        if (lp.sub[r] == 1) {
            lp_enter(r);
            return;
        }
    }
    lp_toggle(r);
    lp_changed();
}

static int lp_item_of(void *e, int *x) {
    int pt[2];
    grid_ev_local(lp.view, e, pt);
    *x = pt[0];
    return lp_at(pt[1]);
}

static int lp_on_down(void *ctx, void *e) {
    int a, x;
    (void)ctx;
    lp.down = 0;
    if (!e || !lp.view || !lp.n) return RET_OK;
    a = lp_item_of(e, &x);
    lp.down = a + 1, m1_tap_at(&lp.tap, e);
    grid_set_press(&lp.press, a + 1, lp.sv);
    return RET_OK;
}

static int lp_on_up(void *ctx, void *e) {
    int a = lp.down - 1, x;
    (void)ctx;
    grid_press_end(&lp.down, &lp.press, lp.sv);
    if (a < 0 || !e || !lp.view) return RET_OK;
    if (m1_tap_near(&lp.tap, e) && lp_item_of(e, &x) == a && (unsigned)a < lp.n) lp_tap((unsigned)a, x);
    return RET_OK;
}

static int lp_on_abort(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    grid_press_end(&lp.down, &lp.press, lp.sv);
    return RET_OK;
}

/* The selected folders under row r's folder (what choosing the row drops). */
static int lp_below(unsigned r) {
    char full[LP_PATH];
    int i, n = 0;
    if (!lp_child(r, full, sizeof full)) return 0;
    for (i = 0; i < lp.nsel; i++)
        if (lp_under(lp.selp[i], full)) n++;
    return n;
}

/* What a Select All tap does now (its label and sensitivity show the same): LP_SA_ADD when a row is plain and one of them fits the limit (a row holding chosen folders always fits: it drops
 * them), or none fits and the level has no chosen row (the tap only tells the limit); else LP_SA_CLEAR when the level has a chosen row (also after the limit stopped an add, so the next tap
 * clears); else LP_SA_NONE (no rows, or every row covered by a chosen folder above). */
static int lp_selall_action(void) {
    unsigned r;
    int plain = 0, held = 0, fits = 0;
    for (r = 0; r < lp.n; r++) {
        int st = lp_state(r);
        if (st == 1) held = 1;
        if (st != 0) continue;
        plain = 1;
        if (!fits && lp.nsel - lp_below(r) < LP_SELMAX) fits = 1;
    }
    if (plain && (fits || !held)) return LP_SA_ADD;
    return held ? LP_SA_CLEAR : LP_SA_NONE;
}

/* Select All (lp_selall_action): add every plain row of this level (each dropping the chosen folders under it), or take the level's chosen rows out. The limit is on the size after the change,
 * size - the chosen folders under the plain rows + those rows: when that is over 256 as many rows go in as fit, the rows that free room (they hold chosen folders) first, then the rest in the order
 * shown, and the limit is told in a message. */
static int lp_on_selall(void *ctx, void *e) {
    unsigned r;
    int pass, act, capped = 0, oom = 0;
    (void)ctx;
    (void)e;
    if (!lp.view || !lp.n) return RET_OK;
    act = lp_selall_action();
    if (act == LP_SA_ADD) {
        for (pass = 0; pass < 2 && !oom; pass++)
            for (r = 0; r < lp.n && !oom; r++) {
                char full[LP_PATH];
                int got;
                if (lp_state(r) != 0 || !lp_child(r, full, sizeof full)) continue;
                if (pass == 0 && !lp_below(r)) continue;
                got = lp_select(full);
                if (got == 0)
                    capped = 1;
                else if (got < 0)
                    oom = 1; /* not the limit: stop, keep what is chosen */
            }
        if (capped) pod_toast(TR("You can choose up to 256 folders."));
    } else if (act == LP_SA_CLEAR) {
        for (r = 0; r < lp.n; r++) {
            char full[LP_PATH];
            int i;
            if (lp_state(r) != 1 || !lp_child(r, full, sizeof full)) continue;
            i = lp_find(full);
            if (i >= 0) lp_drop(i);
        }
    }
    lp_changed();
    return RET_OK;
}

/* Back: one level up; at the root the page closes. */
static int lp_on_back(void *ctx, void *e) {
    char *s;
    int at;
    (void)ctx;
    (void)e;
    if (lp.depth == 0 || lp_root()) {
        navigator_back();
        return RET_OK;
    }
    s = strrchr(lp.path, '/');
    if (s) *s = 0;
    lp.depth--;
    at = lp.depth < LP_DEPTH ? lp.offs[lp.depth] : 0;
    lp_load(at);
    return RET_OK;
}

/* Stock's btn_startscan (0x4ac9f8). */
static int lp_on_scan(void *ctx, void *e) {
    char buf[0x400];
    int i, ctxw[4];
    void *dq;
    (void)ctx;
    (void)e;
    if (!lp.nsel) return RET_OK;
    stop_player();
    dq = _create_deque("char*");
    if (!dq) return RET_OK;
    deque_init(dq);
    for (i = 0; i < lp.nsel; i++) {
        memset(buf, 0, sizeof buf);
        snprintf(buf, sizeof buf, "%s", lp.selp[i]);
        _deque_push_back(dq, buf);
    }
    lp.pending = dq;
    navigator_back(); /* the page closes first, as stock's: the dialog returns to Update Library */
    ctxw[0] = (int)dq, ctxw[1] = 0, ctxw[2] = 1, ctxw[3] = 0;
    navigator_to_with_context("dialog/scanmusic_dialog", ctxw);
    return RET_OK;
}

/* Called by lu_scan_finish at the first finished tick: the worker has returned, the deque is ours to free. */
void lp_scan_done(void) {
    if (lp.pending) deque_destroy(lp.pending);
    lp.pending = (void *)0;
}

static int lp_on_scroll(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (lp.view) lp_title_update();
    lp_kick();
    return RET_OK;
}

static int lp_on_bg(void *ctx, void *e) { return lp_on_abort(ctx, e); }

static int lp_on_destroy(void *ctx, void *e) {
    int i;
    void *keep = lp.pending;
    (void)ctx;
    (void)e;
    m1_timer_stop(&lp.probe_timer);
    grid_free(&lp.g);
    for (i = 0; i < 2; ++i)
        if (lp.mark[i]) bitmap_destroy(lp.mark[i]);
    if (lp.chev) bitmap_destroy(lp.chev);
    for (i = 0; i < lp.nsel; i++) free(lp.selp[i]);
    lp_free_level();
    memset(&lp, 0, sizeof lp);
    lp.pending = keep; /* (the dialog's worker may still read it) */
    return RET_OK;
}

/* ---------------------------------------------------------------------------------------------------------------------------------------- opening */

/* Choose Folders: the picker, when the card is mounted (the caller checked). 0 once it is up, -1 when it could not open (the stock page is the caller's fallback), -2 when the asset is not ours. */
int lupick_open(void) {
    if (lp.win) return -1;
    {
        void *keep = lp.pending;
        memset(&lp, 0, sizeof lp);
        lp.pending = keep;
    }
    lp.win = window_open(LP_ASSET);
    if (!lp.win) return -1;
    widget_on(lp.win, EVT_DESTROY, lp_on_destroy, (void *)0);
    lp.back = m1_bind(lp.win, "btn_return", lp_on_back, (void *)0);
    lp.selall = m1_bind(lp.win, "btn_selall", lp_on_selall, (void *)0);
    lp.scan = m1_bind(lp.win, "lp_scan", lp_on_scan, (void *)0);
    lp.title = widget_lookup(lp.win, "label_title", 1);
    lp.fade = widget_lookup(lp.win, "img_nb_fade", 1);
    lp.view = widget_lookup(lp.win, "view_grid", 1);
    lp.sv = widget_lookup(lp.win, "lupick_scrollview", 1);
    lp.status = widget_lookup(lp.win, "label_status", 1);
    lp.st_title = widget_lookup(lp.win, "label_row_title", 1);
    lp.st_dim = widget_lookup(lp.win, "label_row_dim", 1);
    lp.st_cap = widget_lookup(lp.win, "label_cap", 1);
    lp.bar = widget_lookup(lp.win, "lp_bar", 1);
    if (!lp.back || !lp.selall || !lp.scan || !lp.title || !lp.view || !lp.sv || !lp.status || !lp.st_title ||
        !lp.st_dim || !lp.st_cap || !lp.bar) {
        navigator_back(); /* an asset that is not ours */
        return -2;
    }
    if (!m1_make_marks(lp.win, lp.mark)) {
        navigator_back();
        return -2;
    }
    lp.chev = m1_make_chevron();
    lp.noscroll = grid_scroll_bind(lp.sv, lp_on_scroll, lp.title, &lp.title_on);
    widget_on(lp.win, EVT_WINDOW_TO_BG, lp_on_bg, (void *)0);
    widget_on(lp.view, EVT_POINTER_DOWN, lp_on_down, (void *)0);
    widget_on(lp.view, EVT_POINTER_UP, lp_on_up, (void *)0);
    widget_on(lp.view, EVT_POINTER_ABORT, lp_on_abort, (void *)0);
    widget_on(lp.view, EVT_AFTER_PAINT, lp_on_paint, (void *)0);
    if (!grid_init(&lp.g, lp.win, GRID_TILES, 40, 0)) {
        navigator_back();
        return -1;
    }
    snprintf(lp.path, sizeof lp.path, "%s", LP_ROOT);
    lp_load(0);
    return 0;
}
