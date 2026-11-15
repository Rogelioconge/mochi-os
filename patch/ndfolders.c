/* The Subsonic Folders browser (docs/modules/subsonic.md "Folders"): the server's own directory tree on one page, opened by the Subsonic root's Folders row.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One window for every level (ui/m1plus_ndfolders.bin, tools/pod_nd.py build_folders): the local Folders page's look (patch/folders.c: 52 px rows, a 24 px glyph or a 40 px cover at x 8, the name at x 56, the shared
 * chevron) painted by the page itself in its content view's EVT_AFTER_PAINT, with the Artists page's A-Z furniture (patch/azlist.c) for the root index. The rows are the source's records (lib_nd.list(LS_FOLDERS) through
 * sbs_folder_list): a directory is type 4 (REC_TITLE, REC_ALBUM the root's index letter, the cover in its data), a song type 8 as in every track list, so a song's play, marks, "..." sheet and favourite are the source's own.
 *
 *   levels   a stack of (key, name, scroll offset): a directory tap pushes, Back pops with the offset it was left at (at the root it closes the window). The page asks lib_nd for the level's rows (the cache first) and
 *            the data layer refreshes in the background; the page reads again when the source's gen moves.
 *   rows     directory: the 40 px cover when the entry has one (decoded one a tick, the folder glyph until it is ready: the shared cover poll), else the folder glyph; chevron. Song: the file glyph, the title, the
 *            source's marks (downloaded, ring, DSD) ending at the text end, and the row's "..." (the shared track sheet).
 *   play     a song's tap and the Play / Shuffle pills (shown while the level holds a song) play the level's records through so_play_src, the source's rules: list order, a window of SBA_QUEUE_MAX, a DSD file not on the
 *            card asks "Download to Play?".
 *   index    the root (one music folder) has A-Z sections from the index letters and the rail; several music folders, and every deeper level, are plain rows.
 *   states   cached rows at once; no rows: the spinner under the large title while loading, else "Connect to Wi-Fi first", "Can't connect to the server" or "Empty folder".
 * No hook; everything runs from the page's widgets and timers.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "scroll.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "azlist.h"
#include "i18n.h"
#include "songops.h"
#include "rowmenu.h"
#include "libsrc.h"
#include "sbapi.h"
#include "sbsrc.h"
#include "entries.h"

#define NF_ROW POD_ROW_H
#define NF_TOP_PLAIN 60 /* the first row under the large title alone (SG_PILL_Y 52 + 8) */
#define NF_BOTTOM 24
#define NF_W 320
#define NF_ICON 24
#define NF_ICON_X 16
#define NF_COVER 40
#define NF_COVER_X 8
#define NF_TEXT_X 56
#define NF_TEXT_END 256
#define NF_CHEV_X LIST_CHEV_X
#define NF_MAX SBA_FOLDER_MAX
#define NF_DEPTH 24 /* levels deep */
#define NF_KEY (SBA_ID + 4)
#define NF_LOAD_MS 16 /* one cover a tick */
#define NF_TILES (GRID_VIEW_H / NF_ROW + 6)
#define NF_MARKS 32 /* rows whose marks one paint reads */

enum { NF_I_FOLDER, NF_I_FILE, NF_ICONS };
static const char *const NF_ICON_NAME[NF_ICONS] = {"pod_ic_folders", "fo_ic_file"};

static struct {
    void *win, *view, *sv, *list_w, *status, *spin, *title, *big, *fade, *st_title, *btn_play, *btn_shuffle;
    rowmenu_t rm;
    az_t al;
    grid_t g;
    ls_cpoll_t cp;
    void *chev, *ic[NF_ICONS];
    void *rows; /* the level's records (a deque the page owns) */
    unsigned count;
    unsigned char *rank; /* the root index's section rank of each row */
    int nsong, first_song; /* songs in the level, the first one's row (-1 none) */
    struct {
        char key[NF_KEY];
        char name[SBA_TEXT];
        int off; /* the scroll offset the level was left at */
    } lv[NF_DEPTH];
    int depth; /* the shown level */
    unsigned gen, grows, gen_timer, load_timer;
    int press, down;
    m1_tap_t tap;
    int title_on, noscroll;
} nf __attribute__((section(".scratch")));

static void nf_redraw(void) { grid_sv_redraw(nf.sv); }
static int nf_off(void) { return az_off(&nf.al); }
static int nf_is_dir(int r) { return I(deque_at(nf.rows, (unsigned)r), REC_TYPE) != 8; }
static const char *nf_key(void) { return nf.lv[nf.depth].key; }

/* ---------------------------------------------------------------------------
 * The level's rows
 */
static void nf_title_text(void) {
    const char *t = nf.depth ? nf.lv[nf.depth].name : TR("Folders");
    az_fit(nf.title, t);
    az_fit(nf.big, t);
}

static void nf_title_update(void) {
    m1_title_set(nf.title, &nf.title_on, nf.noscroll || m1_title_gone(nf_off(), 0));
    if (nf.fade) grid_fade(nf.fade, nf_off() > 0);
}

static void nf_pills(void) {
    widget_set_visible(nf.btn_play, nf.nsong != 0, 0);
    widget_set_visible(nf.btn_shuffle, nf.nsong != 0, 0);
    widget_set_sensitive(nf.btn_play, nf.nsong != 0);
    widget_set_sensitive(nf.btn_shuffle, nf.nsong != 0);
}

/* The index levels, the root and one music folder's: the first row is a directory that carries an index letter (the list of several music folders has none). The rank of a song row is its neighbour's. */
static void nf_sections(void) {
    unsigned i, prev = 0;
    nf.al.nsec = 0;
    if (strcmp(nf_key(), SBA_FOLDER_ROOT) && !(nf_key()[0] == 'm' && nf_key()[1] == 'f' && nf_key()[2] == ':'))
        return; /* (only these levels are indexes: a directory's rows carry their album names there) */
    if (!nf.count || !nf_is_dir(0) || !*cc_str(deque_at(nf.rows, 0), REC_ALBUM)) return;
    nf.rank = calloc(nf.count, 1);
    if (!nf.rank) return;
    for (i = 0; i < nf.count; ++i) {
        void *rec = deque_at(nf.rows, i);
        nf.rank[i] = nf_is_dir((int)i) ? (unsigned char)az_rank_of((unsigned char)cc_str(rec, REC_ALBUM)[0])
                                       : (unsigned char)prev;
        prev = nf.rank[i];
    }
    az_sections(&nf.al, nf.rank, 1);
}

static void nf_cover_kick(void);

/* Reads the shown level (the cache and the request: sbs_folder_list) and sets the page up for it. keep: the scroll offset stays; `pre`, a list read already, is taken instead of asking again. */
static void *nf_pre __attribute__((section(".scratch")));

static void nf_load(int keep) {
    void *list;
    int off = keep ? nf_off() : 0, st = LS_ST_READY, h;
    unsigned i;
    rowmenu_close(&nf.rm);
    if (nf.rows) deque_destroy(nf.rows);
    nf.rows = (void *)0;
    free(nf.rank);
    nf.rank = (unsigned char *)0;
    nf.count = 0, nf.press = nf.down = 0, nf.nsong = 0, nf.first_song = -1;
    nf.al.count = 0, nf.al.nsec = 0;
    grid_drop(&nf.g);
    if (!keep) widget_set_prop_int(nf.sv, "yoffset", 0);
    nf.gen = lib_nd.gen(&lib_nd);
    nf.grows = ls_gen_rows(&lib_nd);
    list = nf_pre ? nf_pre : sbs_folder_list(nf_key());
    nf_pre = (void *)0;
    if (list && deque_size(list))
        nf.rows = list, nf.count = deque_size(list);
    else if (list)
        deque_destroy(list);
    if (nf.count > NF_MAX) nf.count = NF_MAX;
    if (!nf.count) st = sbs_folder_state(nf_key());
    for (i = 0; i < nf.count; ++i)
        if (!nf_is_dir((int)i)) {
            if (nf.first_song < 0) nf.first_song = (int)i;
            ++nf.nsong;
        }
    nf.al.count = (int)nf.count;
    nf_sections();
    nf.al.top = nf.nsong ? SG_TOP : nf.al.nsec ? SG_TITLE_H : NF_TOP_PLAIN; /* the pills' room first */
    nf.al.content = az_rows_end(&nf.al) + NF_BOTTOM;
    h = nf.count ? nf.al.content : GRID_VIEW_H;
    widget_resize(nf.view, NF_W, h);
    widget_set_prop_int(nf.sv, "virtual_h", h);
    ls_room(nf.status, nf.spin, LS_ROOM_NAV + SG_TITLE_H);
    m1_show(nf.status, nf.count == 0 && st != LS_ST_LOADING);
    if (!nf.count) widget_set_tr_text(nf.status, ls_empty_key(st, "Empty folder"));
    ls_spin(nf.spin, st == LS_ST_LOADING && nf.count == 0);
    nf_pills();
    nf_title_text();
    az_rail_fit(&nf.al, GRID_VIEW_H);
    if (off > 0 && nf.count) {
        int max = nf.al.content - GRID_VIEW_H;
        widget_set_prop_int(nf.sv, "yoffset", off < max ? off : max > 0 ? max : 0);
    }
    nf_title_update();
    nf_redraw();
    nf_cover_kick();
}

/* ---------------------------------------------------------------------------
 * Tiles and covers
 */
static void nf_prep(grid_tile_t *t, int r) {
    void *rec = deque_at(nf.rows, (unsigned)r);
    grid_set(t, cc_str(rec, REC_TITLE), "", 0);
    if (!nf_is_dir(r)) t->art = 2; /* a song: the glyph, nothing to load */
}

static grid_tile_t *nf_tile(int r) {
    int lo, hi, fresh;
    grid_tile_t *t;
    az_span(&nf.al, &lo, &hi);
    t = grid_tile(&nf.g, r, lo - 2, hi + 2, &fresh);
    if (fresh) nf_prep(t, r);
    return t;
}

/* A directory row's cover: the file lib_nd keeps for its coverArt id, asked for when missing (the poll looks again, the tile shows the spinner), none = the glyph. */
static void nf_cp_ask(void) {
    int i;
    if (!nf.view) return;
    for (i = 0; nf.g.tiles && i < nf.g.n; ++i)
        if (nf.g.tiles[i].album && nf.g.tiles[i].load) nf.g.tiles[i].art = 0;
    nf_cover_kick();
}
static int nf_cp_spin(void) {
    int n = grid_spin_turn(&nf.g);
    if (nf.view) nf_redraw();
    return n;
}
static void nf_cp_giveup(void) {
    int i;
    for (i = 0; nf.g.tiles && i < nf.g.n; ++i) nf.g.tiles[i].load = 0;
    if (nf.view) nf_redraw();
}

static void nf_cover_row(int r) {
    grid_tile_t *t = nf_tile(r);
    char url[80];
    int c;
    memcpy(url, "file://", 8);
    c = lib_nd.cover(&lib_nd, deque_at(nf.rows, (unsigned)r), 0, url + 7, sizeof url - 7);
    t->load = 0;
    if (c == 1) {
        grid_art_url(&nf.g, t, url);
        if (t->art != 1) t->art = 2;
        return;
    }
    t->art = 2;
    if (c == 0) {
        t->load = 1;
        grid_spin_open(&nf.g, "wf_spin", 14);
        ls_cover_poll(&nf.cp, nf.win, nf_cp_ask, nf_cp_spin, nf_cp_giveup);
    }
}

/* The directory row in view still to look at, the one nearest the middle of the view (-1: none). */
static int nf_next_cover(void) {
    int r0, r1, r, best = -1, bd = 0x7fffffff;
    if (!nf.g.tiles || !nf.count || !nf.rows) return -1;
    az_span(&nf.al, &r0, &r1);
    for (r = r0; r <= r1; ++r) {
        grid_tile_t *t;
        int d;
        if (!nf_is_dir(r)) continue;
        t = grid_find(&nf.g, r);
        if (t && t->art) continue;
        d = m1_abs(az_row_y(&nf.al, r) - nf_off() + NF_ROW / 2 - GRID_VIEW_H / 2);
        if (d < bd) bd = d, best = r;
    }
    return best;
}

static int nf_on_cover(const void *unused) {
    int r;
    (void)unused;
    nf.load_timer = 0;
    if (!nf.view) return RET_OK;
    if (grid_moving(nf.sv)) { /* nothing is decoded while the list moves */
        nf_cover_kick();
        return RET_OK;
    }
    r = nf_next_cover();
    if (r >= 0) {
        nf_cover_row(r);
        nf_redraw();
    }
    nf_cover_kick();
    return RET_OK;
}

static void nf_cover_kick(void) {
    if (nf.view && !nf.load_timer && nf_next_cover() >= 0)
        nf.load_timer = timer_add(nf_on_cover, (void *)0, NF_LOAD_MS);
}

/* ---------------------------------------------------------------------------
 * Paint (patch/artists.c ar_paint_rows: window coordinates, the canvas moved back by the offset for the paint)
 */
static void nf_blit(void *canvas, void *bmp, int w, int h, int x, int y) {
    grid_blit_from(canvas, bmp, 0, 0, w, h, x, y, GRID_VIEW_H);
}

static int nf_more_right(void) { return RM_MORE_RIGHT - az_inset(&nf.al); }
static int nf_zone_x(void) { return rowmenu_zone_x(nf_more_right()); }
/* The right end of the text of a row: a directory's, at the chevron; a song's, before its "..." when the sheet is there. */
static int nf_text_end(int dir) {
    return dir || !rowmenu_on(&nf.rm) ? NF_TEXT_END - az_inset(&nf.al)
                                      : rowmenu_text_end(nf_more_right(), az_inset(&nf.al) > 0);
}

static void nf_paint_rows(void *canvas) {
    int r0, r1, r, off = nf_off(), tx = NF_TEXT_X;
    ls_row_t xr[NF_MARKS];
    az_span(&nf.al, &r0, &r1);
    if (r1 - r0 >= NF_MARKS) r1 = r0 + NF_MARKS - 1;
    for (r = r0; r <= r1; ++r) {
        int y = az_row_y(&nf.al, r) - off, dir = nf_is_dir(r);
        void *rec = deque_at(nf.rows, (unsigned)r);
        grid_tile_t *t = nf_tile(r);
        if (nf.press == r + 1) az_fill(canvas, 0, y, y + NF_ROW - 1, NF_W, LIST_PRESS);
        if (dir && t->art == 1) /* (a cover still loading shows the folder glyph) */
            grid_blit(canvas, &nf.g, t, NF_COVER_X, y + (NF_ROW - NF_COVER) / 2, GRID_VIEW_H);
        else
            nf_blit(canvas, nf.ic[dir ? NF_I_FOLDER : NF_I_FILE], NF_ICON, NF_ICON, NF_ICON_X,
                    y + (NF_ROW - NF_ICON) / 2);
        if (dir)
            nf_blit(canvas, nf.chev, POD_CHEV_W, POD_CHEV_H, NF_CHEV_X - az_inset(&nf.al),
                    y + (NF_ROW - 1 - POD_CHEV_H) / 2);
        else {
            lib_nd.row(&lib_nd, rec, &xr[r - r0]);
            if (rowmenu_on(&nf.rm))
                rowmenu_paint(canvas, &nf.rm, nf_more_right(), az_inset(&nf.al) > 0, y, NF_ROW, GRID_VIEW_H);
        }
        az_fill(canvas, tx, y + NF_ROW - 1, y + NF_ROW, az_end(&nf.al) - tx, LIST_HAIR);
    }
    widget_prepare_text_style(nf.st_title, canvas);
    for (r = r0; r <= r1; ++r) {
        int dir = nf_is_dir(r), y = az_row_y(&nf.al, r) - nf_off(), end = nf_text_end(dir), pre = 0;
        grid_tile_t *t = nf_tile(r);
        if (!dir) {
            ls_row_t *x = &xr[r - r0];
            pre = ls_marks_w(x);
            if (pre) {
                ls_marks_draw(canvas, nf.win, x, end - pre, y + (NF_ROW - LIST_TITLE_H) / 2 + LIST_TITLE_H / 2,
                              GRID_VIEW_H);
                pre += LS_MK_GAP;
            }
        }
        if (t->xw != pre) { /* the marks' room changed: the title is cut again */
            t->xw = pre;
            nf_prep(t, r), t->fit = 0;
        }
        grid_text(canvas, t, 0, tx, y + (NF_ROW - LIST_TITLE_H) / 2, end - pre - tx, LIST_TITLE_H, 0);
    }
    az_paint_heads(&nf.al, canvas);
}

static int nf_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = nf_off();
    (void)ctx;
    if (!canvas || !nf.view || !nf.g.tiles || !nf.count || !nf.rows) return RET_OK;
    I(canvas, CANVAS_OY) += off;
    nf_paint_rows(canvas);
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Play and levels
 */
/* The queue is the level's songs only (the source's window of SBA_QUEUE_MAX counts the list's rows, so directories must not be in it): a level with directories plays a songs-only list of its own, the tapped row mapped
 * to its place among the songs; ls_dsd_confirm copies the row it asks about, so the list can go at once. */
static void nf_play_at(int at, int how) {
    void *list = nf.rows, *own = (void *)0;
    int sat = at, r;
    if (!nf.rows || (at >= 0 && at >= (int)nf.count)) return;
    if (nf.nsong < (int)nf.count) {
        own = _create_deque("stSongInfo");
        if (!own) return;
        deque_init(own);
        for (r = 0; r < (int)nf.count; ++r) {
            if (nf_is_dir(r)) continue;
            if (r == at) sat = (int)deque_size(own);
            _deque_push_back(own, deque_at(nf.rows, (unsigned)r));
        }
        list = own;
    }
    if (so_play_src(&lib_nd, 0, list, sat, how, pod_start_player) == -2) ls_dsd_confirm(&lib_nd, list, sat);
    if (own) deque_destroy(own);
}

/* A directory's tap: the next level (the offset this one is left at is kept for Back). */
static void nf_enter(int r) {
    void *rec = deque_at(nf.rows, (unsigned)r);
    const char *id = lib_nd.rec_id(&lib_nd, rec), *name = cc_str(rec, REC_TITLE);
    unsigned n;
    if (!id[0] || nf.depth >= NF_DEPTH - 1 || strlen(id) >= NF_KEY) return;
    nf.lv[nf.depth].off = nf_off();
    ++nf.depth;
    memcpy(nf.lv[nf.depth].key, id, strlen(id) + 1);
    for (n = 0; name[n] && n < sizeof nf.lv[0].name - 1; ++n) nf.lv[nf.depth].name[n] = name[n];
    if (name[n]) /* cut before a character, not inside one */
        while (n > 0 && ((unsigned char)nf.lv[nf.depth].name[n] & 0xc0) == 0x80) --n;
    nf.lv[nf.depth].name[n] = 0;
    nf_load(0);
}

static void nf_tap(int r) {
    if (r < 0 || r >= (int)nf.count || !nf.rows) return;
    if (nf_is_dir(r))
        nf_enter(r);
    else
        nf_play_at(r, SO_KEEP);
}

static int nf_on_back(void *ctx, void *e) {
    int off;
    (void)ctx;
    (void)e;
    if (!nf.depth) {
        navigator_back();
        return RET_OK;
    }
    --nf.depth;
    off = nf.lv[nf.depth].off;
    nf_load(0);
    if (off > 0) {
        int max = nf.al.content - GRID_VIEW_H;
        widget_set_prop_int(nf.sv, "yoffset", off < max ? off : max > 0 ? max : 0);
    }
    nf_title_update();
    return RET_OK;
}

static int nf_on_play(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (nf.view && nf.first_song >= 0) nf_play_at(nf.first_song, SO_IN_ORDER);
    return RET_OK;
}

static int nf_on_shuffle(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (nf.view && nf.nsong) nf_play_at(-1, SO_SHUFFLE);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Touch (patch/artists.c: DOWN remembers, ABORT forgets, UP within the drag threshold on the same row acts)
 */
static int nf_item_of(void *e) {
    int pt[2];
    grid_ev_local(nf.view, e, pt);
    return az_pin_hit(&nf.al, pt[1]) ? -1 : az_at(&nf.al, pt[1]);
}

static int nf_in_zone(void *e, int a) {
    int pt[2], x0;
    if (a < 0 || a >= (int)nf.count || nf_is_dir(a) || !rowmenu_on(&nf.rm)) return 0;
    grid_ev_local(nf.view, e, pt);
    x0 = nf_zone_x();
    return pt[0] >= x0 && pt[0] < x0 + RM_MORE_W;
}

static int nf_on_down(void *ctx, void *e) {
    int a;
    (void)ctx;
    nf.down = 0;
    if (!e || !nf.view || !nf.count) return RET_OK;
    a = nf_item_of(e);
    nf.down = a + 1, m1_tap_at(&nf.tap, e);
    grid_set_press(&nf.press, a + 1, nf.sv);
    return RET_OK;
}

static int nf_on_up(void *ctx, void *e) {
    int a = nf.down - 1;
    (void)ctx;
    grid_press_end(&nf.down, &nf.press, nf.sv);
    if (a < 0 || !e || !nf.view || !nf.rows) return RET_OK;
    if (m1_tap_near(&nf.tap, e) && nf_item_of(e) == a) {
        if (nf_in_zone(e, a))
            rowmenu_open_src(&nf.rm, a, deque_at(nf.rows, (unsigned)a), (rowmenu_add_fn)0, &lib_nd);
        else
            nf_tap(a);
    }
    return RET_OK;
}

static int nf_on_abort(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    grid_press_end(&nf.down, &nf.press, nf.sv);
    return RET_OK;
}

static int nf_on_rail(void *ctx, void *e) {
    (void)ctx;
    if (nf.view) az_rail_event(&nf.al, e);
    return RET_OK;
}

static int nf_on_rail_paint(void *ctx, void *e) {
    (void)ctx;
    if (nf.view) az_rail_paint(&nf.al, e);
    return RET_OK;
}

static int nf_on_scroll(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (nf.view) nf_title_update(), nf_cover_kick();
    return RET_OK;
}

static int nf_on_bg(void *ctx, void *e) {
    az_rail_end(&nf.al);
    return nf_on_abort(ctx, e);
}

/* The source's gen moved (a level file replaced, a status changed, a download's progress): the rows are read again, the scroll position kept, only when no finger is down, the list is still and the page is on top.
 * The same rows only swap the records (the covers stay). Repeats while the page lives. */
static int nf_on_gen(const void *unused) {
    (void)unused;
    if (nf.view && lib_nd.gen(&lib_nd) != nf.gen && !nf.down && !nf.press && !nf.rm.open && !grid_moving(nf.sv) &&
        m1_is_top(nf.win)) {
        unsigned g = lib_nd.gen(&lib_nd), n;
        void *list;
        if (ls_gen_rows(&lib_nd) == nf.grows) { /* only a download's progress moved: no row changed */
            nf.gen = g;
            nf_redraw(); /* the rows' rings and marks read the source again */
            return RET_REPEAT;
        }
        list = sbs_folder_list(nf_key());
        n = list ? deque_size(list) : 0;
        if (n > NF_MAX) n = NF_MAX;
        if (n && nf.count == n && nf.rows && ls_same_list(nf.rows, n, list, n)) {
            deque_destroy(nf.rows);
            nf.rows = list;
            nf.gen = g, nf.grows = ls_gen_rows(&lib_nd);
        } else {
            nf_pre = list;
            nf_load(1);
        }
    }
    return RET_REPEAT;
}

static int nf_on_destroy(void *ctx, void *e) {
    int i;
    (void)ctx;
    (void)e;
    m1_timer_stop(&nf.load_timer);
    m1_timer_stop(&nf.gen_timer);
    ls_spin_end(nf.spin);
    ls_cover_end(&nf.cp);
    rowmenu_free(&nf.rm);
    if (nf.rows) deque_destroy(nf.rows);
    if (nf_pre) deque_destroy(nf_pre);
    nf_pre = (void *)0;
    grid_free(&nf.g);
    az_free(&nf.al);
    if (nf.chev) bitmap_destroy(nf.chev);
    for (i = 0; i < NF_ICONS; ++i)
        if (nf.ic[i]) bitmap_destroy(nf.ic[i]);
    free(nf.rank);
    memset(&nf, 0, sizeof nf);
    return RET_OK;
}

/* A stock 24 px glyph as a bitmap (patch/folders.c fo_bitmap), NULL when it cannot be made. */
static void *nf_bitmap(void *win, const char *name) {
    unsigned *px;
    void *b = bitmap_create_ex(NF_ICON, NF_ICON, NF_ICON * 4, BITMAP_RGBA8888);
    int ok;
    if (!b) return b;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != NF_ICON * 4) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return (void *)0;
    }
    ok = cc_decode(win, name, 1, NF_ICON, 1, px);
    bitmap_unlock_buffer(b);
    if (!ok) {
        bitmap_destroy(b);
        return (void *)0;
    }
    return b;
}

/* The root's Folders row. 0 once the page is up (or already open), -1 when it did not open. */
int nd_folders_open(void) {
    int i, az_ok;
    if (nf.win) return 0;
    memset(&nf, 0, sizeof nf);
    nf.first_song = -1;
    nf.win = window_open("m1plus_ndfolders");
    if (!nf.win) {
        memset(&nf, 0, sizeof nf);
        return -1;
    }
    widget_on(nf.win, EVT_DESTROY, nf_on_destroy, (void *)0);
    m1_bind(nf.win, "btn_return", nf_on_back, (void *)0);
    m1_bind(nf.win, "btn_backtoplayer", m1_on_player, (void *)0);
    nf.list_w = widget_lookup(nf.win, "nf_listview", 1);
    nf.sv = widget_lookup(nf.win, "nf_scrollview", 1);
    nf.view = widget_lookup(nf.win, "view_grid", 1);
    nf.status = widget_lookup(nf.win, "label_status", 1);
    nf.spin = widget_lookup(nf.win, "nf_spin", 1);
    nf.title = widget_lookup(nf.win, "label_title", 1);
    nf.big = widget_lookup(nf.win, "nf_title", 1);
    nf.fade = widget_lookup(nf.win, "img_nb_fade", 1);
    nf.st_title = widget_lookup(nf.win, "label_row_title", 1);
    nf.btn_play = m1_bind(nf.win, "btn_play", nf_on_play, (void *)0);
    nf.btn_shuffle = m1_bind(nf.win, "btn_shuffle", nf_on_shuffle, (void *)0);
    nf.al.win = nf.win, nf.al.sv = nf.sv, nf.al.top = NF_TOP_PLAIN, nf.al.row = NF_ROW;
    az_prefs(&nf.al);
    az_ok = az_bind(&nf.al, nf.win);
    if (!nf.list_w || !nf.sv || !nf.view || !nf.status || !nf.spin || !nf.title || !nf.big || !nf.st_title ||
        !nf.btn_play || !nf.btn_shuffle || !az_ok || !grid_init(&nf.g, nf.win, NF_TILES, NF_COVER, 0)) {
        grid_free(&nf.g);
        navigator_back(); /* an asset that is not ours: the destroy handler clears the state */
        return -1;
    }
    grid_shape(&nf.g, NF_COVER, LIST_R,
               1); /* the covers: LIST_R corners cut in the alpha, as the local Folders page's */
    m1_centre_pill(nf.btn_play, SG_PILL_W);
    m1_centre_pill(nf.btn_shuffle, SG_PILL_W);
    rowmenu_bind(&nf.rm, nf.win); /* optional: no widgets, no "..." */
    az_make_disc(&nf.al);
    nf.chev = m1_make_chevron();
    for (i = 0; i < NF_ICONS; ++i) nf.ic[i] = nf_bitmap(nf.win, NF_ICON_NAME[i]);
    nf.noscroll = grid_scroll_bind(nf.sv, nf_on_scroll, nf.title, &nf.title_on);
    widget_on(nf.win, EVT_WINDOW_TO_BG, nf_on_bg, (void *)0);
    widget_on(nf.view, EVT_POINTER_DOWN, nf_on_down, (void *)0);
    widget_on(nf.view, EVT_POINTER_UP, nf_on_up, (void *)0);
    widget_on(nf.view, EVT_POINTER_ABORT, nf_on_abort, (void *)0);
    widget_on(nf.view, EVT_AFTER_PAINT, nf_on_paint, (void *)0);
    az_bind_rail(&nf.al, nf_on_rail, nf_on_rail_paint);
    memcpy(nf.lv[0].key, SBA_FOLDER_ROOT, sizeof SBA_FOLDER_ROOT);
    nf_load(0);
    nf.gen_timer = timer_add(nf_on_gen, (void *)0, LS_GEN_MS);
    return 0;
}
