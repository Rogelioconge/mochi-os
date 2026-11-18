/* M1+ Music Audiobooks, the LibriVox levels (docs/modules/audiobooks.md "LibriVox"): finding a book in the Internet Archive's librivoxaudio collection and starting its download. Two more levels of the page
 * in patch/bkpage.c, switched in place (the Podcasts Discover and search levels' pair):
 *
 *   LibriVox  (BL_LV) the Discover level's look: the large title (it collapses into the navbar's), the grey line Public domain audiobooks, the section header Popular and the 25 most downloaded books: a
 *             thumbnail, the title and the author. The navbar's magnifier opens the search level. A status line (Loading..., No Wi-Fi, ...) where there are no rows.
 *   Search    (BL_SRCH) the Podcasts search level's: no large title, the field at the top (the keyboard page opens on entering with nothing typed, and from a tap on the field), the rows of the term under it.
 *             Back returns to LibriVox at its offset.
 *   Preview   a tap on a row: the Book level's header (cover, title, author, "37 parts - 13 h 6 min - 380 MB", a white capsule Download or Open Book) over the parts as plain rows.
 *
 * The catalog and the preview are patch/bknet.c's jobs (one worker slot, patch/pcnetw.h), read from the page's 1 s tick; Download makes the folder (bd_create), starts the download job (bd_start) and shows
 * the Book level of the new folder. No hook. The numbers are books.h's BK_LV_* and offsets.inc's PQ_*; tools/pod_books.py is the same arithmetic.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "bkpage.h"
#include "common.h"
#include "azlist.h"
#include "i18n.h"
#include "podcasts.h"
#include "bknet.h"
#include "bkdl.h"
#include "pcjson.h"
#include "pcnet.h"
#include "keyboard.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */

#define BF_DNA 32 /* rows remembered as having no book we can take (PN_NOBOOK), for the session */
enum { BF_P_NONE = 0, BF_P_CAT = 1, BF_P_PREV = 2, BF_P_THUMB = 3 }; /* the job the level waits to start */

static struct {
    char sq[160], sp[160],
        ask[BN_ID + BN_TERM +
            64]; /* the field's text; what the keyboard handed over; the term (or identifier) a waiting job takes */
    int sdone, pend, code, loading, sel, lv_off, disc_off, from, mine, ok, want,
        sig; /* lv_off: the offset of the level a preview was opened from (from); disc_off: the LibriVox level's, kept while the search level is up */
    unsigned gen, spin_t, dna[BF_DNA];
    int ndna;
    void *field, *hint, *text, *clear; /* the search field's widgets (tools/pod_ui.py search_field) */
    char pid[BN_ID], ptitle[BK_TITLE], pauthor[BN_AUTHOR], pdir[BK_FILE]; /* the preview's book */
    int pn, has_open, y_auth, y_tot;
    unsigned on_card,
        on_total; /* a book of the preview that is on the card with parts missing: the parts there and the manifest's (on_total 0: none) */
} bf __attribute__((section(".scratch")));

void bf_reset(void) { memset(&bf, 0, sizeof bf); }

void bf_setup(void *win) {
    bf.field = widget_lookup(win, "ps_field", 1);
    bf.hint = widget_lookup(win, "ps_hint", 1);
    bf.text = widget_lookup(win, "ps_text", 1);
    bf.clear = widget_lookup(win, "ps_clear", 1);
    bf.ok = bf.field && bf.hint && bf.text;
}

/* ---------------------------------------------------------------------------
 * The words
 */
const char *bf_word(int code) {
    switch (code) {
    case PN_NOWIFI:
        return TR("No Wi-Fi");
    case PN_NOCLOCK:
        return TR("Set the date first");
    case PN_NOCERT:
        return TR("Certificates missing");
    case PN_CERT:
        return TR("Certificate problem");
    case PN_NET:
        return TR("Can't connect");
    case PN_GONE:
    case PN_HTTP:
    case PN_NOTFEED:
    case PN_NOTAUDIO:
        return TR("Server error");
    case PN_STORAGE:
    case PN_CARDFULL:
        return TR("Storage unavailable");
    case PN_NOBOOK:
        return TR("Not available");
    case PN_QFULL:
        return TR("Queue is full");
    default:
        return TR("Not enough memory");
    }
}

static unsigned bf_kb(unsigned bytes) { return bytes / 1024 + (bytes % 1024 ? 1 : 0); }

/* A whole book's running time: Podcasts' "19m" under an hour, else hours and minutes in the same short style ("18h 28m", "2h" on the hour). A part's own time stays pc_len_text's. */
static void bf_total_len(char *out, unsigned size, unsigned secs) {
    unsigned m = (secs + 59) / 60;
    if (m < 60)
        pc_len_text(out, size, secs);
    else if (m % 60)
        pc_fmt2(out, size, TR("%dh %dm"), m / 60, m % 60);
    else
        pc_fmt(out, size, TR("%dh"), m / 60);
}

/* "19m · 9 MB" of one part (parts 0), or the whole book (parts is its count, 1 or more) with its number of parts first when there are several: the pieces that are known. */
void bf_line(char *out, unsigned size, unsigned parts, unsigned secs, unsigned bytes) {
    char t[48];
    out[0] = 0;
    if (parts > 1) {
        pc_fmt(t, sizeof t, TR("%d parts"), parts);
        bk_cat(out, size, t);
    }
    if (secs) {
        if (parts)
            bf_total_len(t, sizeof t, secs);
        else
            pc_len_text(t, sizeof t, secs); /* (Podcasts' "19m") */
        if (out[0])
            bk_dot(out, size, t);
        else
            bk_cat(out, size, t);
    }
    if (bytes) {
        bk_kb_text(t, sizeof t, bf_kb(bytes));
        if (out[0])
            bk_dot(out, size, t);
        else
            bk_cat(out, size, t);
    }
}

/* ---------------------------------------------------------------------------
 * The rows of the level
 */
static int bf_dna(const char *id) {
    unsigned h = pc_hash(id);
    int i;
    for (i = 0; i < bf.ndna; ++i)
        if (bf.dna[i] == h) return 1;
    return 0;
}

static int bf_dim_row(int a) {
    const bn_row_t *r = bn_row(a);
    return r && bf_dna(r->id);
}

/* The LibriVox level (Popular) or the search level: the two that list the catalog's rows. */
static int bf_list(void) { return bk.level == BL_LV || bk.level == BL_SRCH; }

/* The rows the current answer gives: those of the set asked for (the popular list or the search), once its query has answered. The search level has none until something is typed. */
static int bf_rows(void) {
    if (bf.pend == BF_P_CAT || bf.code)
        return 0; /* (a preview or the pictures waiting for the slot: the rows are still the answer) */
    if (bk.level == BL_SRCH && !bf.sq[0]) return 0;
    if (bn_catalog_state() < BN_S_THUMBS || bn_catalog_code() != PN_OK) return 0;
    if (bn_catalog_search() != bf.want) return 0;
    return bn_catalog_count();
}

int bf_count(void) { return bk.level == BL_PRE ? bf.pn : bf_rows(); }
/* The search level of Podcasts has the field and the rows under it (PQ_TOP); the LibriVox level has its large title, the grey line and Popular's line over its rows, so they start lower. */
int bf_top(void) { return bk.level == BL_PRE ? bk.y_list : bk.level == BL_SRCH ? PQ_TOP : BK_LV_POP_TOP; }
int bf_content(void) {
    int n = bf_count();
    if (bk.level == BL_PRE) return bk.y_list + n * PC_ROW_H + (n ? BK_BOTTOM : 0);
    return n ? bf_top() + n * PC_ROW_H + (bk.level == BL_SRCH ? PQ_BOTTOM : BK_BOTTOM)
             : GRID_VIEW_H; /* (no rows: the status line's room) */
}

static void bf_text(grid_tile_t *t, const bn_row_t *r, int a) {
    int dim = bf_dna(r->id);
    grid_set(t, r->title, dim ? TR("Not available") : bf.loading && bf.sel == a + 1 ? TR("Loading…") : r->author, 0);
    t->fit = 0;
    t->nochev = dim;
}

static grid_tile_t *bf_tile(int a) {
    int fresh;
    grid_tile_t *t = grid_tile(&bk.g, a, 0, bf_count() - 1, &fresh);
    if (fresh) {
        const bn_row_t *r = bn_row(a);
        if (r) bf_text(t, r, a);
    }
    return t;
}

static grid_tile_t *bf_tile_of(void *ctx, int a) {
    (void)ctx;
    return bf_tile(a);
}

/* The text of row a again (its state changed: Loading, Not available). */
static void bf_retext(int a) {
    grid_tile_t *t = grid_find(&bk.g, a);
    const bn_row_t *r = bn_row(a);
    if (t && r) bf_text(t, r, a);
}

static void bf_rows_reset(void) {
    grid_drop(&bk.g);
    grid_placeholder(&bk.g);
    bk.press = bk.down = 0;
    bk.g_lv = 1;
}

/* A part of the preview: its title and "duration - size". */
static grid_tile_t *bf_ptile(int i) {
    int fresh;
    grid_tile_t *t = grid_tile(&bk.pt, i, 0, -1, &fresh);
    if (fresh) {
        const bn_part_t *p = bn_part(i);
        char sub[96];
        if (p) {
            bf_line(sub, sizeof sub, 0, p->secs, p->bytes);
            grid_set(t, p->title, sub, 0);
        }
    }
    return t;
}

/* ---------------------------------------------------------------------------
 * The status line
 */
/* The text under the field where the level has no rows (NULL: none); *busy: a job is on and the spinner turns before it. */
static const char *bf_status(int *busy) {
    int st = bn_catalog_state(), c;
    *busy = 0;
    if (!bf_list() || (bk.level == BL_SRCH && !bf.sq[0] && !bf.pend))
        return (const char *)0; /* (the empty search level says nothing) */
    if (bf.pend == BF_P_CAT) return *busy = 1, TR("Loading…");
    if (bf.code) return bf_word(bf.code);
    if (st == BN_S_QUERY || st < BN_S_THUMBS) return *busy = 1, TR("Loading…");
    c = bn_catalog_code();
    if (c == PN_CANCELLED || bn_catalog_search() != bf.want) return *busy = 1, TR("Loading…");
    if (c) return bf_word(c);
    return bn_catalog_count() ? (const char *)0 : TR("No results");
}

static int bf_spin_busy(void) {
    int busy;
    return bk.win && bk.fg && bf_list() && (bf_status(&busy), busy);
}

static int bf_spin_tick(const void *timer) {
    (void)timer;
    if (!bf_spin_busy()) {
        bf.spin_t = 0;
        if (bk.win && bk.fg) bk_redraw(); /* (the line without the spinner) */
        return RET_OK;
    }
    if (!m1_screen_lit()) return RET_REPEAT;
    ++bk.hg.spin_n;
    bk_redraw();
    return RET_REPEAT;
}

static void bf_spin_arm(void) {
    if (bf.spin_t || !bf_spin_busy()) return;
    grid_spin_open(&bk.hg, "wf_spin", PS_SPIN_PX);
    bf.spin_t = timer_add(bf_spin_tick, (void *)0, PS_SPIN_MS);
}

/* ---------------------------------------------------------------------------
 * The search field
 */
static void bf_field_show(int on) {
    if (!bf.ok) return;
    widget_set_visible(bf.field, on, 0);
    if (!on) return;
    widget_move(bf.field, PQ_FIELD_X, PQ_FIELD_Y);
    widget_set_tr_text(bf.hint, "Search LibriVox");
}

static void bf_field_texts(void) {
    if (!bf.ok) return;
    widget_set_visible(bf.hint, bf.sq[0] == 0, 0);
    if (bf.clear)
        widget_set_visible(bf.clear, bf.sq[0] != 0, 0); /* (an image: insensitive for life, the touch is BP_CLEAR) */
    az_fit(bf.text, bf.sq);
    widget_set_visible(bf.text, bf.sq[0] != 0, 0);
}

/* What the level shows after the state moved: the rows (made again when the set changed), the status line, the field. */
static void bf_apply(void) {
    int n = bf_count(), max, sig;
    const bn_row_t *r = n ? bn_row(0) : (const bn_row_t *)0;
    sig = (n << 1 | bf.want) ^ (int)(r ? pc_hash(r->id) : 0);
    if (sig != bf.sig) {
        bf.sig = sig;
        bf_rows_reset();
    }
    bf.gen = bn_gen();
    bf_field_texts();
    bk_size();
    max = bf_content() - GRID_VIEW_H;
    if (max < 0) max = 0;
    if (bk_off() > max) widget_set_prop_int(bk.sv, "yoffset", max);
    bk_collapse(); /* (the offset may have moved: the LibriVox level's small title follows it) */
    bf_spin_arm();
    bk_redraw();
    bk_kick();
}

/* ---------------------------------------------------------------------------
 * The catalog and the preview jobs
 */
/* Show the popular list (term "") or search for term. The held list needs no worker; a search made while a job runs waits for it (bf_pump; the downloads go on beside it). */
static void bf_ask(const char *term) {
    char t[BN_TERM];
    int r, a = bf.sel - 1;
    bf.code = 0, bf.pend = BF_P_NONE;
    /* The rows are about to change: a preview that was asked for belongs to the old ones. The row is no longer chosen, a held answer is let go (one still being fetched is cancelled by bf_pump and
     * dropped by the next bn_preview), so it can never open under another row's title. */
    bf.loading = 0, bf.sel = 0;
    bf_retext(a);
    bn_preview_drop();
    bf.want = bn_clean_term(term, t, sizeof t) > 0;
    r = bn_catalog(term);
    if (r == PN_BUSY) {
        bf.ask[0] = 0;
        bk_cat(bf.ask, sizeof bf.ask, term);
        bf.pend = BF_P_CAT;
    } else if (r)
        bf.code = r;
    else
        bf.mine = 1;
    bf_apply();
}

static void bf_preview_fail(int code) {
    int a = bf.sel - 1;
    bf.loading = 0;
    if (code == PN_NOBOOK && bf.ndna < BF_DNA) {
        const bn_row_t *r = bn_row(a);
        if (r) bf.dna[bf.ndna++] = pc_hash(r->id);
    } else if (code != PN_CANCELLED)
        pod_toast(bf_word(code));
    bf_retext(a);
    bk_redraw();
}

/* Start the job the level waits for: a job of ours that runs (the pictures of the last answer) is cancelled, another page's job is waited for (the tick asks again). The downloads, a book's and the
 * episodes', have threads of their own and go on beside it. */
static void bf_pump(void) {
    int r, job = bf.pend;
    if (!job) return;
    if (pn_busy() || pn_job_busy()) {
        pn_cancel(PN_K_BOOKS);
        return;
    }
    r = job == BF_P_CAT ? bn_catalog(bf.ask) : job == BF_P_THUMB ? bn_thumbs() : bn_preview(bf.ask);
    if (r == PN_BUSY) return;
    bf.pend = BF_P_NONE;
    if (!r)
        bf.mine = 1;
    else if (job == BF_P_CAT)
        bf.code = r;
    else if (job == BF_P_PREV)
        bf_preview_fail(r); /* (pictures that cannot be fetched say nothing: the rows stay) */
    bf_apply();
}

/* A tap on row a: its parts are fetched (the row's grey line reads Loading... meanwhile). */
static void bf_row_tap(int a) {
    const bn_row_t *r = bn_row(a);
    if (!r || bf_dna(r->id) || bf.loading) return;
    bf.sel = a + 1;
    bf.loading = 1;
    bf.pend = BF_P_PREV;
    bf.ask[0] = 0;
    bk_cat(bf.ask, sizeof bf.ask, r->id);
    bf_retext(a);
    bk_redraw();
    bf_pump();
}

/* The thumbnails of the rows that are shown but untried (a Cancel cut them): asking again fetches them. */
static int bf_untried(void) {
    int i, n = bf_count();
    for (i = 0; i < n; ++i)
        if (bn_thumb_state(i) == 0) return 1;
    return 0;
}

/* The preview is held: its page. */
static void bf_open_pre(void) {
    const bn_row_t *r = bn_row(bf.sel - 1);
    int a = bf.sel - 1;
    bf.pn = bn_preview_count();
    if (r && strcmp(bn_preview_id(), r->id)) { /* the answer is another book's: not this row's parts */
        bf_preview_fail(PN_CANCELLED);
        return;
    }
    if (!r || bf.pn <= 0) {
        bf_preview_fail(PN_NOBOOK);
        return;
    }
    bf.pid[0] = bf.ptitle[0] = bf.pauthor[0] = 0;
    bk_cat(bf.pid, sizeof bf.pid, r->id);
    bk_cat(bf.ptitle, sizeof bf.ptitle, r->title);
    bk_cat(bf.pauthor, sizeof bf.pauthor, r->author);
    bf.loading = 0;
    bf_retext(a);
    bf.lv_off = bk_off();
    bf.from = bk.level; /* (Back returns to the level it was opened from, at this offset) */
    bk.level = BL_PRE;
    bk.press = bk.pbtn = bk.down = 0;
    grid_drop(&bk.hg);
    grid_placeholder(&bk.hg);
    grid_drop(&bk.pt);
    bf_field_show(0);
    bf.has_open = bd_find(bf.pid, bf.pdir, sizeof bf.pdir);
    bf.on_card = bf.on_total = 0;
    if (bf.has_open) { /* a folder with parts still to come also says how many are there */
        bd_book_t *b = bd_open(bf.pdir);
        unsigned missing = 0, bytes;
        if (b) {
            bd_counts(b, &bf.on_card, &missing, &bytes);
            bf.on_total = missing ? bf.on_card + missing : 0;
            bd_free(b);
        }
    }
    bk_header(bf.ptitle, (bf.pauthor[0] ? 1 : 0) + (bf.on_total ? 1 : 0));
    bf.y_tot = bk.y_sub - (bf.on_total ? BK_SUB_H : 0);
    bf.y_auth = bf.y_tot - BK_SUB_H;
    bk.collapsed = 0;
    bk_set_title(bf.ptitle);
    bk_title_show();
    bk_show(bk.big, 0);
    bk_show(bk.view, 1);
    bk_show(bk.status, 0);
    bk_size();
    widget_set_prop_int(bk.sv, "yoffset", 0);
    bk_fade();
    bk_redraw();
    bk_kick();
}

/* The 1 s tick of the levels (lit screen only): a job that waits, an answer or a thumbnail that came, the preview that is ready. */
void bf_sync(void) {
    if (!pn_job_busy()) bf.mine = 0;
    if (bf_list()) {
        if (bf.pend) bf_pump();
        if (!bf.pend && !bf.code && !bf.loading &&
            (bk.level == BL_LV || bf.sq[0])) { /* (the empty search level asks for nothing) */
            int st = bn_catalog_state();
            if (st == BN_S_IDLE ||
                (st == BN_S_DONE && (bn_catalog_code() == PN_CANCELLED || bn_catalog_search() != bf.want)))
                bf_ask(bf.want ? bf.sq : "");
        }
        if (bf.loading && !bf.pend && !pn_job_busy()) {
            int st = bn_preview_state();
            if (st == 2) {
                if (bn_preview_code() == PN_OK)
                    bf_open_pre();
                else
                    bf_preview_fail(bn_preview_code());
            } else if (st == 0)
                bf_preview_fail(PN_CANCELLED);
        }
        if (bf_list() && !bf.loading && bn_preview_id()[0])
            bn_preview_drop(); /* an answer nobody waits for (a search was made meanwhile): let go once its worker ended */
        if (bf_list() && bn_gen() != bf.gen) bf_apply();
    }
}

/* ---------------------------------------------------------------------------
 * Levels
 */
/* Leaving the levels for another (the Library, a book): what waits or runs is told to stop, the field goes, the preview is let go. */
void bf_leave_cancel(void) {
    bf.pend = BF_P_NONE;
    bf.loading = bf.sdone = 0;
    if (bf.mine) pn_cancel(PN_K_BOOKS);
    bf.mine = 0;
    m1_timer_stop(&bf.spin_t);
    bf_field_show(0);
    if (bn_preview_id()[0]) bn_preview_drop();
}

static void bf_edit(void);

/* The LibriVox level (the Podcasts Discover level's look: the large title, the grey line, Popular and its rows) or the search level, at scroll offset off, after the level was set: the field, the titles and the
 * buttons follow the level. */
static void bf_level_shown(int off) {
    int disc = bk.level == BL_LV;
    bk.press = bk.pbtn = bk.down = 0;
    if (disc) widget_set_text_utf8(bk.big, TR("LibriVox")); /* (the Library's large heading says Audiobooks) */
    bk_show(bk.big, disc);
    bk_show(bk.view, 1);
    bk_show(bk.status, 0);
    bf_field_show(!disc);
    bk_set_title(TR("LibriVox"));
    widget_set_prop_int(bk.sv, "yoffset", off);
    bk_level_title(); /* (after the offset: the small title and the magnifier are right at once) */
}

/* The LibriVox level from the Library: the popular list, at the top. */
void bf_enter(void) {
    if (!bf.ok) return;
    bk.lib_off = bk_off();
    bk.level = BL_LV;
    bf.sq[0] = 0, bf.want = 0, bf.sel = 0, bf.sig = -1;
    bf.loading = bf.sdone = 0;
    grid_drop(&bk.hg);
    grid_drop(&bk.pt);
    bf_level_shown(0);
    bf_ask("");
    bk_fade();
    bk_redraw();
    bk_kick();
}

/* The magnifier (the Podcasts Discover level's): the search level, an empty field and the keyboard on it (Podcasts: entering with nothing typed opens the keyboard). What the LibriVox level was fetching is
 * stopped; Back returns to it at the offset it was left at. Nothing while a row's preview is being fetched. */
void bf_search(void) {
    if (!bf.ok || bk.level != BL_LV || bf.loading) return;
    bf.disc_off = bk_off();
    bf.pend = BF_P_NONE;
    if (bf.mine) pn_cancel(PN_K_BOOKS);
    bf.mine = 0;
    bn_preview_drop();
    bk.level = BL_SRCH;
    bf.sq[0] = 0, bf.want = 0, bf.sel = 0, bf.sig = -1, bf.code = 0;
    bf.loading = bf.sdone = 0;
    grid_drop(&bk.hg);
    grid_drop(&bk.pt);
    bf_level_shown(0);
    bf_apply();
    bk_fade();
    bk_redraw();
    bk_kick();
    bf_edit();
}

/* Back from the search level: the LibriVox level again, at its offset (the popular list is held: no request unless its pictures were cut). */
static void bf_search_close(void) {
    bf.pend = BF_P_NONE;
    if (bf.mine) pn_cancel(PN_K_BOOKS);
    bf.mine = 0;
    bn_preview_drop();
    bk.level = BL_LV;
    bf.sq[0] = 0, bf.sel = 0, bf.sig = -1;
    bf.loading = bf.sdone = 0;
    grid_drop(&bk.hg);
    grid_drop(&bk.pt);
    bf_level_shown(bf.disc_off);
    bf_ask("");
    bk_fade();
    bk_redraw();
    bk_kick();
}

/* Back from the preview: the level it was opened from (LibriVox or the search level) again, where it was. */
static void bf_back_to_list(void) {
    bn_preview_drop();
    grid_drop(&bk.hg);
    grid_drop(&bk.pt);
    bk.level = bf.from;
    bf_level_shown(bf.lv_off);
    if (bf_untried() &&
        !bf.code) { /* the thumbnails the preview's Cancel cut: only they are fetched, the rows and the offset stay */
        int r = bn_thumbs();
        if (r == PN_BUSY)
            bf.pend = BF_P_THUMB;
        else if (!r)
            bf.mine = 1;
    }
    bf_apply(); /* (it keeps the offset in range and the small title with it) */
    bk_fade();
    bk_redraw();
    bk_kick();
}

int bf_back(void) {
    if (bk.level == BL_PRE)
        bf_back_to_list();
    else if (bk.level == BL_SRCH)
        bf_search_close();
    else
        return 0;
    return 1;
}

void bf_fg(void) {
    if (!bf_list()) return;
    bf_field_texts();
    if (bf.sdone && bk.level == BL_SRCH) {
        bf.sdone = 0;
        if (bf.sp[0]) {
            bf.sq[0] = 0;
            bk_cat(bf.sq, sizeof bf.sq, bf.sp);
            widget_set_prop_int(bk.sv, "yoffset", 0);
            bf_ask(bf.sq);
        }
    }
    bf_spin_arm();
    bk_redraw();
}

void bf_bg(void) { m1_timer_stop(&bf.spin_t); }

/* The page closes. */
void bf_free(void) {
    bf_leave_cancel();
    if (!pn_job_busy()) bn_catalog_clean();
    memset(&bf, 0, sizeof bf);
}

/* ---------------------------------------------------------------------------
 * The keyboard
 */
static void bf_done(const char *text) {
    bf.sp[0] = 0;
    bk_cat(bf.sp, sizeof bf.sp, text);
    bf.sdone = 1;
    if (bk.win && bk.fg) bf_fg();
}

static void bf_edit(void) {
    if (bk.level != BL_SRCH) return;
    keyboard_open(TR("LibriVox"), TR("Search LibriVox"), bf.sq, bf_done, (kb_cancel_fn)0, 0);
}

/* The field's clear button: the text and the rows go (the empty search level, as Podcasts'), what runs is stopped and a preview that was asked for is let go, the keyboard opens on the empty field. */
static void bf_clear(void) {
    int a = bf.sel - 1;
    bf.sq[0] = 0, bf.want = 0, bf.code = 0, bf.pend = BF_P_NONE;
    bf.loading = bf.sel = 0;
    bf_retext(a);
    bn_preview_drop();
    if (bf.mine) pn_cancel(PN_K_BOOKS);
    bf.mine = 0;
    widget_set_prop_int(bk.sv, "yoffset", 0);
    bf_apply();
    bf_edit();
}

/* ---------------------------------------------------------------------------
 * Download
 */
/* Download: the folder and its manifest, the job, the Book level of the new folder. Open: the Book level of the folder that holds the book. A refusal after the folder was made (the Wi-Fi is off, another
 * worker runs) still opens the Book level: the book is on the card and resumable. */
static void bf_download(void) {
    char dir[BK_FILE];
    int r;
    if (bd_find(bf.pid, dir, sizeof dir)) {
        bk_open_dir(dir);
        return;
    }
    r = bd_create(bf.pid, bf.ptitle, bf.pauthor, dir, sizeof dir);
    if (r != PN_OK) {
        pod_toast(bf_word(r));
        return;
    }
    r = bd_start(dir);
    bk_open_dir(dir);
    if (r) pod_toast(bf_word(r));
}

/* ---------------------------------------------------------------------------
 * Painting
 */
static void bf_paint_hint(void *canvas, int off) {
    int busy;
    const char *key = bf_status(&busy);
    grid_hint_paint(
        canvas, &bk.hg, bk.st[BS_HINT], key, busy, bk.level == BL_SRCH ? PQ_TOP : BK_LV_POP_Y, GRID_VIEW_H,
        off); /* (the Podcasts search level's status line: centred under the field; on the LibriVox level under its grey line) */
}

static void bf_span(int top, int n, int *r0, int *r1) {
    int s = bk_off() - top;
    *r0 = s < 0 ? 0 : s / PC_ROW_H;
    *r1 = (s + GRID_VIEW_H - 1) / PC_ROW_H;
    if (*r1 > n - 1) *r1 = n - 1;
}

static void bf_paint_lv(void *canvas) {
    int off = bk_off(), n = bf_count(), r0, r1, r;
    if (bk.level ==
        BL_LV) /* the grey line under the large title (the Shows level's refresh line: BS_META at PP_LINE_X, PP_LINE_Y) */
        bk_text_utf8(canvas, bk.st[BS_META], TR("Public domain audiobooks"), PP_LINE_X, BK_LV_LINE_Y - off,
                     BK_W - 2 * PP_LINE_X, PP_LINE_H);
    if (n) {
        if (bk.level == BL_LV)
            bk_text_utf8(canvas, bk.st[BS_SECH], TR("Popular"), PP_SHOWS_X, BK_LV_POP_Y - off, BK_W - 2 * PP_SHOWS_X,
                         PP_HEAD_H); /* (a section header, as Books on the Library) */
        bf_span(bf_top(), n, &r0, &r1);
        if (r1 >= r0) {
            grid_list_paint(canvas, &bk.g, bk.st_title, bk.st_sub, r0, r1, off - bf_top(), GRID_VIEW_H, bk.press, 0, 1,
                            bf_tile_of, (void *)0);
            for (r = r0; r <= r1; ++r)
                if (bf_dim_row(r))
                    az_fill(canvas, 0, bf_top() + r * PC_ROW_H - off, bf_top() + (r + 1) * PC_ROW_H - 1 - off, BK_W,
                            PQ_DIM);
        }
    }
    bf_paint_hint(canvas, off);
}

static int bf_play_x(void) { return (BK_W - BK_PLAY_W) / 2; }

static void bf_paint_pre(void *canvas) {
    int off = bk_off(), r0, r1, r, k, pass, px = bf_play_x(), by = bk.y_btn - off;
    if (off < bk.y_list && bk.hg.tiles) {
        char line[96], label[48];
        unsigned parts, secs, bytes, w[48];
        int more, n;
        grid_blit(canvas, &bk.hg, &bk.hg.tiles[0], PS_ART_X, BK_ART_Y - off, GRID_VIEW_H);
        bk_capsule(canvas, px, by, BK_PLAY_W, BK_BTN_H, bk.pbtn == BP_PLAY ? 0xffc8c8c8u : 0xffffffffu);
        widget_prepare_text_style(bk.st[BS_TITLE], canvas);
        for (k = 0; k < bk.nn; ++k)
            bk_text(canvas, bk.name + bk.nl[k].start, bk.nl[k].len, BK_NAME_X, bk.y_name + k * BK_NAME_PITCH - off,
                    BK_NAME_W, BK_NAME_PITCH);
        if (bf.pauthor[0])
            bk_text_utf8(canvas, bk.st[BS_SUB], bf.pauthor, BK_NAME_X, bf.y_auth - off, BK_NAME_W, BK_SUB_H);
        bn_preview_totals(&parts, &secs, &bytes, &more);
        bf_line(line, sizeof line, parts, secs, bytes);
        bk_text_utf8(canvas, bk.st[BS_SUB], line, BK_NAME_X, bf.y_tot - off, BK_NAME_W, BK_SUB_H);
        if (bf.on_total) {
            line[0] = 0;
            pc_fmt2(line, sizeof line, TR("%d of %d parts downloaded"), bf.on_card, bf.on_total);
            bk_text_utf8(canvas, bk.st[BS_SUB], line, BK_NAME_X, bk.y_sub - off, BK_NAME_W, BK_SUB_H);
        }
        label[0] = 0;
        bk_cat(label, sizeof label, bf.has_open ? TR("Open Book") : TR("Download"));
        n = bk_wide(w, 48, label);
        widget_prepare_text_style(bk.st[BS_BTN], canvas);
        bk_text(canvas, w, n, px + 8, by, BK_PLAY_W - 16, BK_BTN_H);
    }
    bf_span(bk.y_list, bf.pn, &r0, &r1);
    for (r = r0; r <= r1; ++r) {
        int y = bk.y_list + r * PC_ROW_H - off;
        az_fill(canvas, BK_PART_X, y + PC_ROW_H - 1, y + PC_ROW_H, LIST_HAIR_END - BK_PART_X, LIST_HAIR);
    }
    for (pass = 0; pass < 2; ++pass) { /* the titles, then the grey lines */
        widget_prepare_text_style(pass ? bk.st_sub : bk.st_title, canvas);
        for (r = r0; r <= r1; ++r)
            grid_text(canvas, bf_ptile(r), pass, BK_PART_X,
                      bk.y_list + r * PC_ROW_H - off + (pass ? LIST_SUB_Y : LIST_TITLE_Y), BK_PART_W,
                      pass ? LIST_SUB_H : LIST_TITLE_H, GRID_VIEW_H);
    }
}

void bf_paint(void *canvas) {
    if (bk.level == BL_PRE)
        bf_paint_pre(canvas);
    else
        bf_paint_lv(canvas);
}

/* ---------------------------------------------------------------------------
 * Touch
 */
/* What a touch hit: the search field or its clear button (part), a row that may open, or the preview's capsule; -1 for none. */
int bf_hit(void *e, int *part) {
    int pt[2], y;
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(bk.view, pt);
    *part = BP_BODY;
    if (bk.level == BL_PRE) {
        if (pt[1] >= bk.y_btn && pt[1] < bk.y_btn + BK_BTN_H && pt[0] >= bf_play_x() && pt[0] < bf_play_x() + BK_PLAY_W)
            return *part = BP_PLAY, 0;
        return -1;
    }
    if (bk.level == BL_SRCH && pt[0] >= PQ_FIELD_X && pt[0] < PQ_FIELD_X + PQ_FIELD_W && pt[1] >= PQ_FIELD_Y &&
        pt[1] < PQ_FIELD_Y + PQ_FIELD_H)
        return *part = bf.sq[0] && pt[0] >= PQ_FIELD_X + PQ_CLEAR_X ? BP_CLEAR : BP_FIELD, 0;
    y = pt[1] - bf_top();
    if (y < 0) return -1;
    y /= PC_ROW_H;
    return y < bf_count() && !bf_dim_row(y) ? y : -1;
}

void bf_tap(int a, int part) {
    if (bk.level == BL_PRE) {
        if (part == BP_PLAY) bf_download();
    } else if (part == BP_CLEAR)
        bf_clear();
    else if (part == BP_FIELD)
        bf_edit();
    else
        bf_row_tap(a);
}

/* ---------------------------------------------------------------------------
 * The thumbnails and the preview's cover: one a tick
 */
static int bf_next_thumb(void) {
    int r0, r1, a, n = bf_count();
    char path[160];
    if (!bf_list() || n <= 0) return -1;
    bf_span(bf_top(), n, &r0, &r1);
    for (a = r0; a <= r1; ++a) {
        grid_tile_t *t = grid_find(&bk.g, a);
        if ((!t || !t->art) && bn_thumb(a, path, sizeof path)) return a;
    }
    for (a = 0; a < n; ++a) {
        grid_tile_t *t = grid_find(&bk.g, a);
        if ((!t || !t->art) && bn_thumb(a, path, sizeof path)) return a;
    }
    return -1;
}

int bf_load_pending(void) {
    if (bk.level == BL_PRE) return bk.hg.tiles && !bk.hg.tiles[0].art;
    return bf_next_thumb() >= 0;
}

/* grid_art_url of the picture at path (the placeholder when it is none, or one the stock decoder would refuse). */
static void bf_art(grid_t *g, grid_tile_t *t, int have, const char *path) {
    char url[180];
    if (have && pc_cover_ok(path)) {
        url[0] = 0;
        bk_cat(url, sizeof url, "file://");
        bk_cat(url, sizeof url, path);
        grid_art_url(g, t, url);
    } else
        grid_art_url(g, t, (const char *)0);
}

void bf_load(void) {
    char path[160];
    if (bk.level == BL_PRE) {
        if (bk.hg.tiles && !bk.hg.tiles[0].art) {
            bf_art(&bk.hg, &bk.hg.tiles[0], bn_preview_cover(path, sizeof path), path);
            bk_redraw();
        }
        return;
    }
    {
        int a = bf_next_thumb();
        if (a >= 0) {
            grid_tile_t *t = bf_tile(a);
            bf_art(&bk.g, t, bn_thumb(a, path, sizeof path), path);
            bk_redraw();
        }
    }
}
