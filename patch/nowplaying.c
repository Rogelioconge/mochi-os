/* M1+ Music Now Playing: the stock playing_page (ui/playing_page.bin, tools/mod_nowplaying.py) gets a cover-tinted
 * background, rounded cover corners that match it, and a remaining-time label that the assets cannot give it.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One hook, playing_page_init (0x53d1e4): the page's init, run when Now Playing is built, never at boot or in the
 * main loop. It runs the stock function to completion and then
 * starts a page-scoped 500 ms timer (np_tick) and registers EVT_DESTROY on the window, which removes the timer. It also binds a click handler on the queue
 * button (np_on_queue: our Queue page, patch/queuepage.c; the stock drawer opens when it answers RET_OK).
 * The timer does three things and nothing else:
 *   - the tint: demo writes the track's cover to /tmp/coverpic.jpg or /tmp/externpic.jpg (parseplaycover_thd,
 *     source type word 0x97cad8: 2 and 3/5; 1 while it works); when the file changes (a hash of its bytes) the
 *     picture is decoded by the stock loader, box-averaged to one colour (patch/covercache.c) and np_tone turns that
 *     into a dark, a little desaturated tone that is set as the window's bg_color (widget_set_style); a static
 *     gradient image over it (ui/playing_page.bin, np_tint.png) fades it to black towards the bottom. No cover, or a
 *     source that is not a JPEG file: the neutral dark tone.
 *   - the times: label_playtime and label_playlen carry stock's elapsed and total (stock rewrites both on every tick);
 *     np_elapsed and np_remaining, labels of the asset, show "m:ss" and "-m:ss" from get_playtimeandlength while that
 *     call gives a length, and stock's two show again whenever it does not.
 *   - the info page's lines (np_info): rewritten as "Label: value" with spaced units, only when stock wrote them anew;
 *     the quality line is shown by np_quality, a label of ours, because stock rewrites label_info on every tick.
 * EXPERIMENTAL, the status bar: while the page is in front its bg_color is the page's colour on the first row (np_bar_color),
 * set from np_set_color; EVT_WINDOW_TO_BACKGROUND, the destroy, a replaced page and the tick's top-window check put the stock
 * black back (np_bar_black). Nothing is done unless both window events are registered.
 * The cover is square (AWTK cannot clip an image); its four corners are painted over in the colour the window has
 * there (the tone under the gradient), anti-aliased, from the cover widget's own EVT_AFTER_PAINT: 4 x 12 x 12 pixels
 * of a table np_corner_init computes once, a few dozen canvas_fill_rect calls, and only when the cover repaints.
 * Every failure (a widget of the asset missing, no timer, an unreadable file, an undecodable picture)
 * leaves the stock page as it is, square corners included. docs/modules/nowplaying.md.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "home.h"
#include "i18n.h"
#include "common.h"
#include "lyrics.h"
#include "sbsrc.h" /* sba_now_cover, sba_rec_track, sba_rec_size, sba_url, sba_gen; lib_nd and ls_favorite for the star */
#include "entries.h"
#define NP_ONCE_MS 30 /* the one-shot decode after a track change seen by the cover's paint */
#define NP_SB_WAIT \
    10 /* ticks (5 s) a server track with no cover file yet keeps the previous track's cover on the art before stock's picture shows */

/* The queue button (btn_queue, stock handler 0x53b14c: navigator_to("dialog/playqueue_dialog")) opens our Queue page instead. Bound after the stock init, so it runs before the stock
 * handler: RET_STOP keeps the drawer from opening once our page is up, RET_OK lets it open (a stream, a window that will not open). docs/modules/queue.md. */
static int np_on_queue(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    return queue_open() == 0 ? RET_STOP : RET_OK;
}
#include "podcasts.h"
#include "minibar.h" /* mb_art_t: the header cover of the info page */
#include "fnv.h"

/* Our labels of the page: the cover view, title, artist, album, the two badge pictures, then per quality item (value, unit),
 * the three dividers, and per row (label, value). Names in the asset (tools/mod_nowplaying.py). */
enum {
    NI_ART,
    NI_TITLE,
    NI_ARTIST,
    NI_ALBUM,
    NI_HIRES,
    NI_DSD,
    NI_QV,
    NI_QU = NI_QV + 4,
    NI_QD = NI_QU + 4,
    NI_KEY = NI_QD + 3,
    NI_VAL = NI_KEY + NPI_ROWS,
    NI_N = NI_VAL + NPI_ROWS
};
static const char *const np_iw_names[NI_N] = {
    "np_i_art", "np_i_title", "np_i_artist", "np_i_album", "np_i_badge_hires", "np_i_badge_dsd", "np_i_qv0",
    "np_i_qv1", "np_i_qv2",   "np_i_qv3",    "np_i_qu0",   "np_i_qu1",         "np_i_qu2",       "np_i_qu3",
    "np_i_qd1", "np_i_qd2",   "np_i_qd3",    "np_i_k0",    "np_i_k1",          "np_i_k2",        "np_i_k3",
    "np_i_v0",  "np_i_v1",    "np_i_v2",     "np_i_v3"};

static struct {
    void *fav; /* btn_fav (stock's star button): wears the bookmark styles while an episode plays */
    int favrec, favv; /* a server track's star: the REC_ID favv (1 starred) was read for, 0 none yet */
    unsigned favgen; /* sba_gen() at that read: the cache changed since when it differs */
    void *win, *rem, *tot; /* the window, np_remaining (ours), label_playlen (stock) */
    void *el, *pt; /* np_elapsed (ours), label_playtime (stock's elapsed time); both 0 if the page lacks either */
    unsigned timer; /* the repeating np_tick timer */
    unsigned interval; /* interval last accepted by timer_modify */
    unsigned key; /* what the colour was last made from: 0 nothing yet, NP_KEY_NEUTRAL, or a file's hash */
    unsigned sig; /* np_cover_sig at the last full hash: while it is unchanged the file is not hashed again */
    unsigned color; /* the window's bg_color as 0x00BBGGRR (what the corners are painted from) */
    int shown; /* the seconds np_remaining shows, -1 none */
    int eshown; /* the seconds np_elapsed shows, -1 none */
    int own; /* 1: our times are the visible labels, 0: stock's are */
    int fg; /* 1 from the page's start and EVT_WINDOW_TO_FOREGROUND, 0 after EVT_WINDOW_TO_BACKGROUND */
    int barok; /* 1: both window events are registered, so the status bar may be tinted (else it never is) */
    int bar; /* 1: the status bar's bg_color is ours (np_bar_color) and must go back to black */
    void *iw[NI_N]; /* the info page's own widgets (np_iw_names), 0 for one the asset lacks */
    int ihead, iq, irow; /* 1: the asset has the whole header / quality line / four rows, so ours show them */
    unsigned qdone; /* the hash of the quality text laid out, 0 none yet */
    int qown; /* 1: our items are the visible quality line and label_info is hidden */
    unsigned rown; /* bit r: row r shows ours (the stock label of it is hidden) */
    int relay; /* ticks left that lay the page out again whatever the text */
    unsigned ikey; /* mb_track_key of the track the header shows, 0 none */
    unsigned rkey; /* mb_track_key of the track the rows were laid out for (a stream's size comes from its record) */
    int ibadge; /* the badge shown: 0 none, 1 HI-RES, 2 DSD */
    mb_art_t ia; /* the header's cover (patch/minibar.c), NPI_ART px with NPI_ART_R px corners */
    void *info[NP_INFO_N]; /* the info page's stock labels (np_info_names), the data: 0 for one the page lacks */
    unsigned
        done[NP_INFO_N]; /* the hash of the text each label held after our last look: stock's text, or what we wrote */
    unsigned char corner[NP_ART_R * NP_ART_R]; /* the top left corner's coverage outside the arc, 0..255 */
    void *art,
        *sbmp; /* img_playcover, and the NP_ART x NP_ART RGBA bitmap of a server track's cover (made on first use, freed with the page) */
    unsigned sbkey; /* np_hash of the cover file sbmp holds */
    int sbrec, sbshow; /* the REC_ID of the track sbmp is for; 1: sbmp is drawn over stock's picture */
    int sbseen; /* the REC_ID np_server_art last looked at */
    int sbwait; /* ticks the playing server track has had no cover file while sbmp (the previous track's) is kept on show */
    int pfrec; /* the REC_ID of the queue record whose cover was last asked for ahead */
    unsigned once; /* the one-shot np_art_once timer, 0 none */
} np __attribute__((section(".scratch")));

/* A dark, a little desaturated tone of the cover's average colour (r, g, b bytes), as a color_t word
 * (0xAABBGGRR, alpha ff). Value: NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255 for the brightest channel v; every
 * channel keeps NP_SAT_NUM / NP_SAT_DEN of its distance from v (a grey stays grey). A black cover is the neutral
 * tone. With NP_V_MAX 192 the white title and the #AAAAAA lines keep 4.5:1 over the gradient (test/pod/nowplaying.py). */
__attribute__((noinline)) unsigned np_tone(unsigned r, unsigned g, unsigned b) {
    return m1_tone(r, g, b); /* patch/common.c, shared with the album page's tint */
}

/* A clock without a leading zero, as Apple Music prints it: "m:ss", or "h:mm:ss" from an hour on; neg puts a "-" first. */
__attribute__((noinline)) void np_format_clock(char *out, unsigned size, int secs, int neg) {
    const char *sign = neg ? "-" : "";
    if (secs < 0) secs = 0;
    if (secs >= 3600)
        snprintf(out, size, "%s%d:%02d:%02d", sign, secs / 3600, secs / 60 % 60, secs % 60);
    else
        snprintf(out, size, "%s%d:%02d", sign, secs / 60, secs % 60);
}

/* "-m:ss", or "-h:mm:ss" from an hour on: the seconds left. A position past the end shows -0:00. */
__attribute__((noinline)) void np_format_remaining(char *out, unsigned size, int pos, int len) {
    np_format_clock(out, size, len - pos, 1);
}

/* The coverage of the area outside a quarter circle of radius NP_ART_R in the corner square of NP_ART_R pixels
 * (the circle's centre at the square's inner corner), 0..255: each pixel is sampled 8 x 8 times. The same numbers
 * as the PNG mask of the earlier builds (test/pod/nowplaying.py). */
__attribute__((noinline)) void np_corner_init(void) { m1_corner_fill(np.corner, NP_ART_R); }

static int np_art_once(const void *timer);

/* The cover widget's EVT_AFTER_PAINT: the four corners, in widget coordinates (the stock paint only translates). */
static int np_on_art_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    (void)ctx;
    if (!canvas || !np.win) return RET_OK;
    if (np.art) { /* a server track's cover (stock draws nothing for a stream; its placeholder must not show between two tracks): sbmp stays up while a server track is playing, until
                   * the new cover is decoded (np_art_once, a moment after the change is seen here, or the tick); a local track draws stock's picture */
        void *t = cc_playing();
        int rec = t ? *(int *)((char *)t + REC_ID) : 0;
        if (rec <= -2) {
            int r[4] = {0, 0, NP_ART, NP_ART};
            if (np.sbshow && np.sbmp) canvas_draw_image(canvas, np.sbmp, r, r);
            if (rec != np.sbseen && !np.once) np.once = timer_add(np_art_once, (void *)0, NP_ONCE_MS);
        }
    }
    m1_corners(canvas, np.corner, NP_ART_R, NP_ART, np.color, NP_ART_Y, NP_ALPHA_TOP, NP_ALPHA_BOTTOM, NP_WIN_H);
    return RET_OK;
}

/* FNV-1a over the file's bytes (at most NP_HASH_MAX of them) and its length, never 0; 0 when it cannot be read or is
 * empty. */
__attribute__((noinline)) unsigned np_file_key(const char *path) {
    unsigned char buf[512];
    unsigned h = FNV_SEED, total = 0, n, i;
    void *f = fopen(path, "rb");
    if (!f) return 0;
    while (total < NP_HASH_MAX && (n = fread(buf, 1, sizeof buf, f)) > 0) {
        for (i = 0; i < n; ++i) h = (h ^ buf[i]) * FNV_PRIME;
        total += n;
    }
    fclose(f);
    h = (h ^ total) * FNV_PRIME;
    return total ? h | !h : 0;
}

/* EXPERIMENTAL: the status bar takes the colour the page has on its first row, so the bar and the page read as one surface
 * (m1_bar_tint / m1_bar_black, patch/common.c, shared with the album page). np_bar_color is the colour (0x..BBGGRR) under the black gradient on the first row (np_tint.png: black, NP_ALPHA_TOP at the first row to NP_ALPHA_BOTTOM at the last), darkened
 * until the bar's white glyphs keep 4.5:1 (m1_bar_color). */
__attribute__((noinline)) unsigned np_bar_color(unsigned color) {
    return m1_bar_color(m1_shade(color, 0, NP_ALPHA_TOP, NP_ALPHA_BOTTOM, NP_WIN_H));
}

/* The bar in the page's colour, while the page is in front and its events are registered. */
static void np_bar_apply(void) {
    if (np.barok && np.fg && m1_bar_tint(np.win, np_bar_color(np.color)))
        np.bar = 1; /* a failed call keeps what the bar has (and owes) */
}

/* The stock black, if the bar is ours. Called on every way out: background, destroy, a window above, a replaced page. A page
 * that took the bar over since (the album page on Back) keeps it: only the owner restores. */
static void np_bar_black(void) {
    if (!np.bar) return;
    np.bar = 0;
    m1_bar_black(np.win);
}

/* The timer's check, for what the events missed: the bar is ours only while the page is the top normal window. A dialog
 * (the pull-down) is not a normal window; its EVT_WINDOW_TO_BACKGROUND has cleared np.fg. */
static int np_bar_sync(void) {
    int top = m1_is_top(np.win);
    if (np.bar && !top)
        np_bar_black();
    else if (!np.bar && top)
        np_bar_apply();
    return top;
}

/* The cover's tone as the page shows it: in Light Mode the page is neutral (pal_tone: the dark chromatic tone cannot flip, and the page's white text does). np_tone_raw is
 * the tone as chosen, so np_relight can put the page right when the mode changes while it is open. */
static unsigned np_tone_raw __attribute__((section(".scratch")));

static void np_set_color(unsigned tone) {
    unsigned v[4], color = pal_tone(tone); /* value_t: type at 0, the uint32 at 8 */
    np_tone_raw = tone;
    memset(v, 0, sizeof v);
    value_set_uint32(v, color);
    if (widget_set_style(np.win, "normal:bg_color", v) != RET_OK) return;
    np.color = color & 0xffffff;
    widget_invalidate_force(np.win, (void *)0);
    np_bar_apply();
}

void np_relight(void) {
    if (np.win && np_tone_raw) np_set_color(np_tone_raw); /* (patch/palette.c pal_apply) */
}

/* The cover file of the source type, or NULL for a source with no JPEG file; busy is set while demo is still making it. */
const char *np_cover_file(int *busy) { /* also the mini player bar's (patch/minibar.c) */
    int src = *(volatile int *)COVER_SRC;
    const char *server_cover = sba_now_cover(cc_playing());
    *busy = src == COVER_SRC_BUSY;
    if (server_cover) return server_cover;
    if (src == COVER_SRC_EMBEDDED) return "/tmp/coverpic.jpg";
    if (src == COVER_SRC_FOLDER || src == COVER_SRC_CACHE) return "/tmp/externpic.jpg";
    return (const char *)0;
}

/* The cheap look at the cover (no byte of it is read): a hash of the source type, the file's length (fseek/ftell) and the
 * playing track's path. demo writes a new cover for every track change (and passes through the busy state first), so while
 * all three are as at the last full hash the file is taken as unchanged; any difference sends it to np_file_key. 0: the
 * file cannot be opened (a full look, which tries again too). */
unsigned np_hash(const char *s);
__attribute__((noinline)) unsigned np_cover_sig(const char *path, int src) {
    void *f = fopen(path, "rb");
    void *track;
    long size;
    unsigned h;
    if (!f) return 0;
    size = !fseek(f, 0, 2) ? ftell(f) : -1;
    fclose(f);
    if (size <= 0) return 0;
    track = cc_playing();
    h = np_hash(track ? cc_str(track, REC_PATH) : "");
    h = (h ^ (unsigned)size) * FNV_PRIME;
    h = (h ^ (unsigned)src) * FNV_PRIME;
    return h | !h;
}

/* The cover of the queue record after the playing one, asked for once while a server track plays (sba_now_cover asks when the file is not cached and the ask has not failed), so
 * it is usually there when the track starts. */
static void np_prefetch(int rec) {
    void *q = *(void **)PLAY_QUEUE, *next;
    int pos = mclGetPlayPos(), nrec;
    if (!q || pos < 0 || (unsigned)pos + 1 >= deque_size(q)) return;
    next = deque_at(q, (unsigned)pos + 1);
    nrec = next ? *(int *)((char *)next + REC_ID) : 0;
    if (nrec <= -2 && nrec != rec && nrec != np.pfrec) np.pfrec = nrec, (void)sba_now_cover(next);
}

/* A playing server track's cover file is the big art: stock draws /tmp/coverpic.jpg, which it never writes for a stream. The picture is decoded once into a bitmap of ours
 * and drawn over stock's by np_on_art_paint; a track with no cached cover (sba_now_cover asks for it) shows stock's, and so does every local track. */
static void np_server_art(void) {
    void *t = cc_playing();
    int rec = t ? *(int *)((char *)t + REC_ID) : 0;
    const char *path;
    unsigned key, *px;
    char url[160]; /* "file://" and a cover file's path */
    if (!np.art) return;
    np.sbseen = rec;
    if (rec > -2) { /* a local track (or none): stock's picture */
        if (np.sbshow) np.sbshow = 0, widget_invalidate_force(np.art, (void *)0);
        np.sbwait = 0;
        return;
    }
    np_prefetch(rec);
    path = sba_now_cover(t);
    if (!path) { /* not cached yet (sba_now_cover has asked), or the track has none: the previous cover stays for NP_SB_WAIT ticks, then stock's */
        if (np.sbshow && ++np.sbwait > NP_SB_WAIT)
            np.sbshow = 0, np.sbwait = 0, widget_invalidate_force(np.art, (void *)0);
        return;
    }
    np.sbwait = 0;
    key = np_hash(path);
    if (np.sbshow &&
        key == np.sbkey) { /* the picture is already up (the next track of the album): only the record changes */
        np.sbrec = rec;
        return;
    }
    if (!np.sbmp) np.sbmp = bitmap_create_ex(NP_ART, NP_ART, NP_ART * 4, BITMAP_RGBA8888);
    px = np.sbmp ? (unsigned *)bitmap_lock_buffer_for_write(np.sbmp) : (unsigned *)0;
    if (!px) return;
    snprintf(url, sizeof url, "file://%s", path);
    np.sbshow = cc_decode(np.win, url, 1, NP_ART, 1, px);
    bitmap_unlock_buffer(np.sbmp);
    np.sbkey = key, np.sbrec = rec;
    widget_invalidate_force(np.art, (void *)0);
}

/* The one-shot timer of np_on_art_paint: decodes the new track's cover at once, outside the paint. Returning RET_OK ends the timer. */
static int np_art_once(const void *timer) {
    (void)timer;
    np.once = 0;
    if (np.win) np_server_art();
    return RET_OK;
}

static void np_cover(void) {
    int busy;
    const char *path = np_cover_file(&busy);
    unsigned key, sig, px, album, tone;
    char url[80]; /* cc_url's size */
    void *track;
    if (busy) return; /* the file is being replaced: keep the colour */
    if (!path) { /* no picture file: the neutral tone, once */
        if (np.key != NP_KEY_NEUTRAL) np.key = NP_KEY_NEUTRAL, np_set_color(NP_NEUTRAL);
        return;
    }
    sig = np_cover_sig(path, *(volatile int *)COVER_SRC);
    if (sig && sig == np.sig && np.key && np.key != NP_KEY_NEUTRAL)
        return; /* same source, length and track as at the last look */
    track =
        cc_playing(); /* the track's album: its tone may be known (the album page's, an earlier play); an untagged one has no key */
    album = track && *cc_str(track, REC_ALBUM) ? cc_album_key(track) : 0;
    if (sig && album && m1_tone_get(album, &tone)) { /* known: no hash of the file (up to NP_HASH_MAX bytes) */
        np.sig = sig, np.key = NP_KEY_TONE; /* a key no hash is compared equal to: the next full look colours again */
        np_set_color(tone);
        return;
    }
    key = np_file_key(path);
    if (!key) return; /* unreadable: try again next tick */
    if (*(volatile int *)COVER_SRC == COVER_SRC_BUSY) return; /* demo started over while we read */
    np.sig = sig;
    if (key == np.key) return; /* unchanged: nothing to do */
    np.key = key;
    /* the tone cache is RAM only: after a boot the album's Cover Flow cache file (168 px, the album page's source) is a far
     * cheaper decode than the embedded picture (often 600-1400 px); no such file: the playing cover's own file */
    if (album && cc_url(url, album) && cc_decode(np.win, url, 1, 1, 1, &px)) {
        tone = np_tone(px & 255, px >> 8 & 255, px >> 16 & 255);
        np_set_color(tone);
        m1_tone_put(album, tone);
        return;
    }
    snprintf(url, sizeof url, "file://%s", path);
    if (cc_decode(np.win, url, 1, 1, 1, &px)) {
        tone = np_tone(px & 255, px >> 8 & 255, px >> 16 & 255);
        np_set_color(tone);
        m1_tone_put(album, tone);
    }
}

/* The idle lyrics page's (patch/idlelyrics.c) view of this page: its window, 0 when it has none (the page then does not open), and the colour the window has (a color_t word) once the cover's tone has been looked
 * at again: this page's own tick does not run while another window covers it, so the idle page asks. np_cover compares the cheap signature and does no work for a track it has seen. */
void *np_window(void) { return np.win; }

unsigned np_idle_color(void) {
    if (!np.win) return NP_NEUTRAL | 0xff000000u;
    np_cover();
    return np.color | 0xff000000u;
}

/* np_elapsed and np_remaining are the visible labels while the player gives a length, label_playtime and label_playlen
 * (stock's) otherwise. Stock rewrites its two on its own tick ("01:27"), so ours are separate labels and not rewrites of
 * stock's text, which a paint between the two timers would show. */
static void np_label(int own) {
    if (own == np.own) return;
    np.own = own;
    widget_set_visible(np.rem, own, 0); /* all four are insensitive in the asset, so hidden is also untouchable */
    widget_set_visible(np.tot, !own, 0);
    if (np.el) {
        widget_set_visible(np.el, own, 0);
        widget_set_visible(np.pt, !own, 0);
    }
}

static void np_time(void) {
    int pos = 0, len = 0;
    char text[16];
    if (!np.rem || !np.tot) return;
    if (get_playtimeandlength(&pos, &len) != 1 || len <= 0) {
        np_label(0);
        return;
    }
    if (pos < 0) pos = 0;
    if (pos > len) pos = len;
    if (np.shown != len - pos) {
        np_format_remaining(text, sizeof text, pos, len);
        widget_set_text_utf8(np.rem, text);
        np.shown = len - pos;
    }
    if (np.el && np.eshown != pos) {
        np_format_clock(text, sizeof text, pos, 0);
        widget_set_text_utf8(np.el, text);
        np.eshown = pos;
    }
    np_label(1);
}

/* The info page (page 3). Stock writes its lines when the track changes (show_player_face 0x53bab4 -> the fill 0x539c40, only
 * while its "changed" flags are set; the page timer calls it every tick but it fills only then): "%s:%s" for album, genre, year,
 * location, "%s:%.2fMB" for the size, "%s|%.1fkHz|%dbit|%dkbps" (the quality line, label_info), the label and the "Unknown" of a
 * missing value in the app's language (getFormatString: player_unknown, player_location ...). Those six labels are the data
 * source and stay (hidden and insensitive once ours show); the page itself is ours (docs/modules/nowplaying.md "Information page"):
 *   - the header (np_header): cover, title, artist, album of the playing record, the HI-RES / DSD badge (tape_badge, the cassette
 *     theme's rule);
 *   - the quality line (np_quality): label_info's four items, each a value label and a unit label laid out by measured width;
 *   - the rows (np_row): Genre, Year, File Size, Location, a label and a right aligned value; the Location keeps its end.
 * A label of ours is placed with widget_move / widget_resize from the measured text, never painted. The Genre, Year and File Size
 * labels are our keys, the Location label stock's. np.done remembers the hash of each stock text after our last look, so a line is
 * laid out only when stock has written it again (or for NP_RELAY ticks after the page starts: a label measures in its own style only
 * once the window is open). Anything that does not look as expected gives the line back to stock's label. */
static const char *const np_info_names[NP_INFO_N] = {"label_info", "label_album", "label_genre",
                                                     "label_year", "label_size",  "label_location"};

typedef struct {
    char *p, *end;
} np_out;

static void np_put(np_out *o, char c) {
    if (o->p < o->end) *o->p++ = c;
}
static void np_puts(np_out *o, const char *s) {
    while (*s) np_put(o, *s++);
}
static int np_starts(const char *s, const char *w) {
    while (*w)
        if (*s++ != *w++) return 0;
    return 1;
}
static int np_digit(char c) { return c >= '0' && c <= '9'; }

__attribute__((noinline)) unsigned np_hash(const char *s) {
    unsigned h = m1_fnv(FNV_SEED, s);
    return h | !h;
}

/* s into out (size bytes, NUL terminated), cut at a character boundary. */
static void np_cut(char *out, unsigned size, const char *s) {
    unsigned n = 0;
    while (s[n] && n + 1 < size) ++n;
    while (n && s[n] && ((unsigned char)s[n] & 0xc0) == 0x80) --n;
    memcpy(out, s, n);
    out[n] = 0;
}

/* The text after the first colon (leading spaces dropped) of a stock line "Label:value"; NULL without a colon or with a label of no length. */
static const char *np_after_colon(const char *s) {
    const char *c = s;
    while (*c && *c != ':') ++c;
    if (!*c || c == s) return (const char *)0;
    for (++c; *c == ' '; ++c) {
    }
    return c;
}

/* v with a space between a digit and "MB" ("35.92MB" -> "35.92 MB"), into out. */
static void np_size_text(const char *v, char *out, unsigned size) {
    np_out o;
    const char *p;
    o.p = out, o.end = out + size - 1;
    for (p = v; *p; ++p) {
        if (p > v && np_digit(p[-1]) && np_starts(p, "MB"))
            np_puts(&o, " MB"), p += 1;
        else
            np_put(&o, *p);
    }
    *o.p = 0;
}

/* The size and location lines of a playing server stream: stock's come from the queue record, whose path is the stream address (the token and salt are in it) and whose file does not exist. The
 * label is stock's (its text up to the colon), the size is the server's (sba_rec_size, "N.NN MB"; "Unknown" when the server gave none), the location is the server's address without
 * credentials, path or query. 0 for any other line or track (a local file, and a downloaded track, which plays from its own path, are stock's). */
__attribute__((noinline)) int np_stream_text(int i, const char *s, char *out, unsigned size) {
    void *t = cc_playing();
    const char *path, *colon = s, *u, *e, *at;
    int rec;
    np_out o;
    if ((i != 4 && i != 5) || !t) return 0;
    rec = *(int *)((char *)t + REC_ID);
    path = cc_str(t, REC_PATH);
    if (rec > -2 || !np_starts(path, "http") || !sba_rec_track(rec)[0]) return 0;
    o.p = out, o.end = out + size - 1;
    while (*colon && *colon != ':') ++colon;
    if (*colon && colon != s) {
        for (u = s; u < colon; ++u) np_put(&o, *u);
        np_puts(&o, ": ");
    }
    if (i == 4) {
        unsigned bytes = sba_rec_size(rec), mb = bytes >> 20,
                 hundredths = (((bytes & 0xfffffu) * 100u) + 524288u) >> 20;
        char num[24];
        if (hundredths >= 100) ++mb, hundredths -= 100;
        if (bytes) {
            snprintf(num, sizeof num, "%u.%02d MB", mb, (int)hundredths);
            np_puts(&o, num);
        } else {
            np_puts(&o, TR("Unknown"));
        }
    } else {
        const char *auth, *host;
        u = sba_url();
        auth = u;
        while (*auth && !(auth[0] == ':' && auth[1] == '/' && auth[2] == '/')) ++auth;
        auth = *auth ? auth + 3 : u;
        for (e = auth; *e && *e != '/'; ++e) {
        }
        for (host = at = auth; at < e; ++at)
            if (*at == '@') host = at + 1; /* userinfo is not shown */
        if (host == e) {
            np_puts(&o, TR("Unknown"));
        } else {
            for (at = u; at < auth; ++at) np_put(&o, *at);
            for (at = host; at < e; ++at) np_put(&o, *at);
        }
    }
    if (o.p >= o.end) return 0;
    *o.p = 0;
    return 1;
}

/* The width of w's text in its own font (0: no text, or it cannot be measured). */
static int np_tw(void *w) {
    const unsigned *t = widget_get_text(w);
    return t && *t ? m1_text_w(w, t) : 0;
}

/* w at x, y, ww wide and as high as a px line plus NPI_PAD above and below; y is the text's top. */
static void np_place(void *w, int x, int y, int ww, int px) {
    widget_move(w, x, y - NPI_PAD);
    widget_resize(w, ww, px + 2 * NPI_PAD);
}

static void np_vis(void *w, int on) {
    if (w) widget_set_visible(w, on, 0); /* all of ours are insensitive in the asset */
}

/* The cover bitmap of the header view: resident, drawn here (never decoded in the paint). */
static int np_on_info_art(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    (void)ctx;
    if (np.win) mb_art_paint_at(&np.ia, canvas, 0, 0);
    return RET_OK;
}

/* The header: the playing record's title, artist and album, its cover, and the badge of a Hi-Res or DSD track (the cassette theme's rule: tape_badge). A title is
 * as wide as the badge leaves it. New text and cover only when the track changed (mb_track_key) or the layout is redone. */
static unsigned np_header(int force) {
    void *t = cc_playing();
    const char *title;
    char b[200];
    unsigned key = t ? mb_track_key(t) : 0;
    int badge = t ? tape_badge(t) : 0, bw = badge == 2 ? NPI_BADGE_DSD_W : badge == 1 ? NPI_BADGE_HIRES_W : 0;
    if (!np.ihead) return key;
    if (key == np.ikey && badge == np.ibadge && !force) {
        if (t && np.ia.settle > 0 && mb_art_settle(&np.ia, np.win, t))
            widget_invalidate_force(np.iw[NI_ART], (void *)0);
        return key;
    }
    title = t ? cc_str(t, REC_TITLE) : "";
    if (t && !*title) title = cc_str(t, REC_NAME);
    np_cut(b, sizeof b, title);
    widget_set_text_utf8(np.iw[NI_TITLE], b);
    np_cut(b, sizeof b, t ? cc_str(t, REC_ARTIST) : "");
    widget_set_text_utf8(np.iw[NI_ARTIST], b);
    np_cut(b, sizeof b, t ? cc_str(t, REC_ALBUM) : "");
    widget_set_text_utf8(np.iw[NI_ALBUM], b);
    np_place(np.iw[NI_TITLE], NPI_TEXT_X, NPI_TITLE_Y, NPI_TEXT_W - (bw ? bw + NPI_BADGE_GAP : 0), NPI_TITLE_PX);
    np_place(np.iw[NI_ARTIST], NPI_TEXT_X, NPI_ARTIST_Y, NPI_TEXT_W, NPI_META_PX);
    np_place(np.iw[NI_ALBUM], NPI_TEXT_X, NPI_ALBUM_Y, NPI_TEXT_W, NPI_META_PX);
    np_vis(np.iw[NI_TITLE], 1);
    np_vis(np.iw[NI_ARTIST], 1);
    np_vis(np.iw[NI_ALBUM], 1);
    np_vis(np.iw[NI_HIRES], badge == 1);
    np_vis(np.iw[NI_DSD], badge == 2);
    if (bw) {
        void *img = np.iw[badge == 2 ? NI_DSD : NI_HIRES];
        widget_move(img, NPI_R - bw, NPI_BADGE_Y);
        widget_resize(img, bw, NPI_BADGE_H);
    }
    if (key != np.ikey || !np.ia.bmp) {
        if (t)
            mb_art_cover(&np.ia, np.win, t, 1);
        else
            mb_art_free(&np.ia);
    }
    np.ikey = key, np.ibadge = badge;
    widget_invalidate_force(np.iw[NI_ART], (void *)0);
    return key;
}

typedef struct {
    char v[24], u[5]; /* the value, and its unit (kHz, bit, kbps; none for the format) */
} np_qi;

/* The items of stock's quality line "FLAC|44.1kHz|16bit|1021kbps" (the first four fields): the unit taken off its value, and a field with no value (or a zero one, bit depth
 * or rate the player did not know) dropped. Returns the count. */
static int np_qparse(const char *s, np_qi *it) {
    static const char *const unit[4] = {"", "kHz", "bit", "kbps"};
    int n = 0, f, last = 0;
    const char *p = s;
    for (f = 0; f < 4 && !last; ++f) {
        const char *b = p, *e = p;
        unsigned ul = f == 3 ? 4 : f ? 3 : 0, len, nz = 0, k;
        while (*e && *e != '|') ++e;
        last = !*e;
        p = last ? e : e + 1;
        while (b < e && *b == ' ') ++b;
        while (e > b && e[-1] == ' ') --e;
        it[n].u[0] = 0;
        if (ul && (unsigned)(e - b) >= ul && np_starts(e - ul, unit[f])) {
            e -= ul;
            np_cut(it[n].u, sizeof it[n].u, unit[f]);
            while (e > b && (e[-1] == ' ' || e[-1] == '-')) --e;
        }
        len = (unsigned)(e - b);
        for (k = 0; k < len; ++k)
            if (b[k] != '0' && b[k] != '.') nz = 1;
        if (!len || (f && !nz)) continue;
        if (len > sizeof it[n].v - 1) len = sizeof it[n].v - 1;
        memcpy(it[n].v, b, len);
        it[n].v[len] = 0;
        ++n;
    }
    return n;
}

/* The items in a row across NPI_Q_W: each as wide as its value, the unit NPI_Q_UGAP after it, the same gap between items (half of it at both ends), a divider on each gap's middle. */
static void np_qlayout(const np_qi *it, int n) {
    int w[4], vw[4], uw[4], sum = 0, i, x = 0, room;
    for (i = 0; i < 4; ++i) {
        int on = i < n;
        np_vis(np.iw[NI_QV + i], on);
        np_vis(np.iw[NI_QU + i], on && it[i].u[0]);
        if (i && i < 4) np_vis(np.iw[NI_QD + i - 1], i < n);
        if (!on) continue;
        widget_set_text_utf8(np.iw[NI_QV + i], it[i].v);
        vw[i] = np_tw(np.iw[NI_QV + i]);
        uw[i] = 0;
        if (it[i].u[0]) {
            widget_set_text_utf8(np.iw[NI_QU + i], it[i].u);
            uw[i] = np_tw(np.iw[NI_QU + i]) + NPI_Q_UGAP;
        }
        w[i] = vw[i] + uw[i];
        sum += w[i];
    }
    room = NPI_Q_W - sum;
    if (room < 0) room = 0;
    for (i = 0; i < n; ++i) {
        int left = NPI_X + room * (2 * i + 1) / (2 * n) + x;
        np_place(np.iw[NI_QV + i], left, NPI_Q_Y, vw[i] + 4, NPI_Q_VPX);
        if (it[i].u[0])
            np_place(np.iw[NI_QU + i], left + vw[i] + NPI_Q_UGAP, NPI_Q_UY, uw[i] - NPI_Q_UGAP + 4, NPI_Q_UPX);
        if (i) {
            widget_move(np.iw[NI_QD + i - 1], NPI_X + room * i / n + x, NPI_Q_DIV_Y);
            widget_resize(np.iw[NI_QD + i - 1], 1, NPI_Q_DIV_H);
        }
        x += w[i];
    }
}

/* The quality line. Stock rewrites label_info with the compact text on every page tick, so it stays the data source: hidden and insensitive while the items of ours show, laid out
 * when its text changes. A page without them, an unreadable text or one with no item gives the line back to label_info (never a stale line). */
static void np_quality(int force) {
    char s[NP_INFO_BUF];
    np_qi it[4];
    unsigned h;
    int need, n, i;
    if (!np.iq || !np.info[0]) return;
    need = m1_text_utf8(np.info[0], s, sizeof s);
    if (need > 0 && (unsigned)need < sizeof s) { /* else none, empty or cut short */
        h = np_hash(s);
        if (h == np.qdone && np.qown && !force) return;
        n = np_qparse(s, it);
        if (n) {
            np_qlayout(it, n);
            np.qdone = h;
            if (!np.qown) {
                np.qown = 1;
                widget_set_visible(np.info[0], 0, 0);
                widget_set_sensitive(np.info[0], 0);
            }
            return;
        }
    }
    if (np.qown) {
        for (i = 0; i < 4; ++i) {
            np_vis(np.iw[NI_QV + i], 0);
            np_vis(np.iw[NI_QU + i], 0);
        }
        for (i = 0; i < 3; ++i) np_vis(np.iw[NI_QD + i], 0);
        widget_set_visible(np.info[0], 1, 0);
    }
    np.qown = 0;
    np.qdone = 0;
}

/* The row's value text with its start cut and "..." put there, as much of the end as fits room px in w's font (the label keeps its file name). */
static void np_head_fit(void *w, const char *v, int room) {
    char buf[NP_ROW_TAIL + 4];
    unsigned wide[NP_ROW_TAIL + 4];
    unsigned len = 0, lo, hi;
    int cut;
    while (v[len]) ++len;
    cut = len > NP_ROW_TAIL;
    if (cut) { /* the last NP_ROW_TAIL bytes from a character start */
        v += len - NP_ROW_TAIL;
        while (((unsigned char)*v & 0xc0) == 0x80) ++v;
        len = 0;
        while (v[len]) ++len;
    }
    buf[0] = buf[1] = buf[2] = '.';
    lo = 0, hi = len;
    if (!cut) {
        widget_set_text_utf8(w, v);
        if (np_tw(w) <= room) return;
    }
    while (lo < hi) { /* the first character start from which "..." and the rest fit */
        unsigned mid = (lo + hi) / 2;
        while (mid < len && ((unsigned char)v[mid] & 0xc0) == 0x80) ++mid;
        if (mid >= hi) { /* only the character start hi is left */
            lo = hi;
            break;
        }
        np_cut(buf + 3, sizeof buf - 3, v + mid);
        tk_utf8_to_utf16_ex(buf, 3 + len - mid, wide, NP_ROW_TAIL + 3);
        if (m1_text_w(w, wide) <= room)
            hi = mid;
        else
            lo = mid + 1;
    }
    np_cut(buf + 3, sizeof buf - 3, v + lo);
    widget_set_text_utf8(w, buf);
}

/* Row r shows stock's label again (or ours): both are never visible. */
static void np_row_own(int r, int own) {
    void *s = np.info[2 + r];
    if (((np.rown >> r & 1) != 0) == own) return;
    np.rown ^= 1u << r;
    np_vis(np.iw[NI_KEY + r], own);
    np_vis(np.iw[NI_VAL + r], own);
    if (!s) return;
    widget_set_visible(s, !own, 0);
    if (own) widget_set_sensitive(s, 0);
}

/* Stock's line i (2 Genre, 3 Year, 4 File Size, 5 Location, "Label:value") as row i - 2: its label and value, the value right aligned in what the label leaves. 0 when the text is not "Label:value". */
static int np_row(int i, const char *s) {
    char out[NP_INFO_BUF + 64], key[64], val[NP_INFO_BUF + 8];
    const char *line = np_stream_text(i, s, out, sizeof out) ? out : s, *v = np_after_colon(line), *c;
    int r = i - 2, y = NPI_ROW_Y + r * NPI_ROW_PITCH + (NPI_ROW_PITCH - NPI_ROW_PX) / 2, kw, room;
    void *k = np.iw[NI_KEY + r], *w = np.iw[NI_VAL + r];
    if (!v) return 0;
    if (i == 5) {
        for (c = line; *c != ':'; ++c) {
        }
        memcpy(key, line, (unsigned)(c - line) < sizeof key - 1 ? (unsigned)(c - line) : sizeof key - 1);
        key[(unsigned)(c - line) < sizeof key - 1 ? (unsigned)(c - line) : sizeof key - 1] = 0;
    } else {
        np_cut(key, sizeof key, TR(i == 2 ? "Genre" : i == 3 ? "Year" : "File Size"));
    }
    if (!key[0]) return 0;
    widget_set_text_utf8(k, key);
    kw = np_tw(k);
    room = NPI_R - NPI_X - kw - NPI_KEY_GAP;
    if (room < 0) room = 0;
    np_place(k, NPI_X, y, kw + 4, NPI_ROW_PX);
    np_place(w, NPI_R - room, y, room, NPI_ROW_PX);
    if (i == 5) {
        np_head_fit(w, v, room);
    } else {
        if (i == 4)
            np_size_text(v, val, sizeof val);
        else
            np_cut(val, sizeof val, v);
        widget_set_text_utf8(w, val);
    }
    np_row_own(r, 1);
    return 1;
}

static void np_info(void) {
    char s[NP_INFO_BUF];
    unsigned i, h;
    int force = np.relay > 0;
    if (force) --np.relay;
    unsigned key = np_header(force);
    if (key != np.rkey)
        force = 1, np.rkey = key; /* a new track: its rows again (a stream's stock text is the same for every record) */
    np_quality(force);
    if (!np.irow) return;
    for (i = 2; i < NP_INFO_N; ++i) {
        int need = np.info[i] ? m1_text_utf8(np.info[i], s, sizeof s) : -1;
        /* none, empty, or too long for s (cut short): stock's label */
        if (need <= 0 || (unsigned)need >= sizeof s) {
            np_row_own((int)i - 2, 0);
            np.done[i] = 0;
            continue;
        }
        h = np_hash(s);
        if (h == np.done[i] && !force) continue; /* the text we last laid out */
        np.done[i] = h;
        if (!np_row((int)i, s)) np_row_own((int)i - 2, 0);
    }
}

/* The favourite button of an episode is a bookmark (docs/modules/podcasts.md "Saved"): stock's star toggles myfav and sets btn_imgfav_style / btn_imgunfav_style (its click handler at once, show_player_face on a
 * track change); while the playing path is an episode the button's style is mapped to btn_imgsave_style / btn_imgunsave_style (the same icons, a bookmark, in the page theme), and back for music. Stock sets its style
 * only when the name differs from the one it wants, so the swap lasts until stock's next fill; our click handler (run after stock's) and the tick put it back. */
static int np_is_server(void *rec) { return rec && sba_rec_track(*(int *)((char *)rec + REC_ID))[0] != 0; }

/* The playing server track's favourite (1 starred), read from the cache through the source (nd_row on the queue record: the album's cache file, or the Favorites list) when the track or sba_gen
 * differs from the last read, or fresh is set; else the last answer. A star moves the cache first and sba_gen when the server answers, so a refusal puts the star back by itself. */
static int np_server_fav(void *rec, int fresh) {
    int id = *(int *)((char *)rec + REC_ID);
    unsigned gen = sba_gen();
    if (fresh || np.favrec != id || np.favgen != gen) {
        ls_row_t x;
        lib_nd.row(&lib_nd, rec, &x);
        np.favrec = id, np.favgen = gen, np.favv = x.fav;
    }
    return np.favv;
}

static void np_fav_sync(void) {
    const char *cur, *want = (const char *)0;
    void *rec;
    int ep;
    if (!np.fav) return;
    cur = *(const char *const *)((char *)np.fav + WIDGET_STYLE);
    if (!cur) return;
    rec = cc_playing();
    if (np_is_server(
            rec)) { /* a server track (streamed or downloaded): the star shows the server's favourite, not stock's myfav (which has no row for it) */
        want = np_server_fav(rec, 0) ? "btn_imgfav_style" : "btn_imgunfav_style";
        if (strcmp(cur, want)) {
            widget_use_style(np.fav, want);
            widget_set_prop_str(np.fav, "style:pressed:icon", "np_unfav_down");
        }
        return;
    }
    ep = rec && pc_is_path(cc_str(rec, REC_PATH));
    if (ep) {
        if (!strcmp(cur, "btn_imgfav_style"))
            want = "btn_imgsave_style";
        else if (!strcmp(cur, "btn_imgunfav_style"))
            want = "btn_imgunsave_style";
    } else if (!strcmp(cur, "btn_imgsave_style"))
        want = "btn_imgfav_style";
    else if (!strcmp(cur, "btn_imgunsave_style"))
        want = "btn_imgunfav_style";
    if (want) {
        widget_use_style(np.fav, want);
        /* stock's inline pressed icon (the page sets np_unfav_down on the widget) is a star: the bookmark presses to its own outline */
        widget_set_prop_str(np.fav, "style:pressed:icon", ep ? "np_unsave_down" : "np_unfav_down");
    }
}

/* The star. A server track's goes to the server (ls_favorite: the row sheet's Favorite, with its toast) and RET_STOP keeps stock's handler away: it would write the stream record, whose address
 * carries the login token, into the local favourites table. Bound after the stock init, so it runs first. Every other track is stock's. */
static int np_on_fav(void *ctx, void *e) {
    void *rec = cc_playing();
    (void)ctx;
    (void)e;
    if (np_is_server(rec)) {
        ls_favorite(&lib_nd, rec, np_server_fav(rec, 1));
        np_server_fav(rec, 1);
        np_fav_sync();
        return RET_STOP;
    }
    np_fav_sync();
    return RET_OK;
}

static void np_work(void) {
    recent_note(cc_playing()); /* No stock list query: the page underneath owns pdeq_showlist;
                               * the menu's foreground handler resolves the cover key. */
    if (!m1_screen_lit()) return;
    np_server_art();
    np_cover();
    np_time();
    np_info();
    ly_tick(); /* the lyrics page (patch/lyrics.c) */
    np_fav_sync();
}

static int np_tick(const void *timer) {
    unsigned want;
    (void)timer;
    if (!np.win) return RET_OK; /* not ours any more: a timer that returns RET_OK ends */
    want = m1_screen_lit() ? NP_TICK_MS : POD_DARK_MS;
    if (np.timer && np.interval != want && timer_modify(np.timer, want) == RET_OK) np.interval = want;
    /* another page on top: nothing of this one is seen, np_on_foreground catches up. A dialog (the pull-down) also clears np.fg
     * but leaves the page the top normal window and partly visible, so the work goes on under it. */
    if (!np_bar_sync() && np.barok && !np.fg) return RET_REPEAT;
    np_work();
    return RET_REPEAT;
}

/* The page is over (or replaced): the timer goes, the status bar is black again, the state is cleared. */
static void np_stop(void) {
    np_bar_black();
    ly_stop();
    m1_timer_stop(&np.timer);
    if (np.sbmp) bitmap_destroy(np.sbmp);
    mb_art_free(&np.ia);
    memset(&np, 0, sizeof np);
}

static int np_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != np.win) return RET_OK; /* an earlier page's end: the new one keeps its state */
    np_stop();
    return RET_OK;
}

/* Another window came over the page (a page, a dialog, the pull-down): the bar is black while it covers. */
static int np_on_background(void *ctx, void *e) {
    (void)e;
    if (!np.win || ctx != np.win) return RET_OK;
    np.fg = 0;
    np_bar_black();
    return RET_OK;
}

static int np_on_foreground(void *ctx, void *e) {
    (void)e;
    if (!np.win || ctx != np.win) return RET_OK;
    np.relay = NP_RELAY; /* the info page is laid out again (a language or font change meanwhile) */
    ly_refresh(); /* a lyrics text size changed in Settings is laid out now */
    np_work(); /* the page is current when it reappears (fg still 0: a new colour tints the bar once, below) */
    /* the mode button's picture follows the play mode: stock sets it only in its own click handler, so a mode set on the Queue page (or elsewhere) is shown now */
    stock_np_mode_button(ctx);
    np.fg = 1;
    np_bar_apply();
    return RET_OK;
}

static void np_start(void *win) {
    void *art;
    unsigned n;
    if (np.win) np_stop(); /* an earlier page that never said it was gone */
    np.win = win;
    np.rem = widget_lookup(win, "np_remaining", 1);
    np.tot = widget_lookup(win, "label_playlen", 1);
    np.el = widget_lookup(win, "np_elapsed", 1);
    np.pt = widget_lookup(win, "label_playtime", 1);
    np.fav = widget_lookup(win, "btn_fav", 1);
    if (np.fav) widget_on(np.fav, EVT_CLICK, np_on_fav, (void *)0);
    if (!np.el || !np.pt) np.el = np.pt = (void *)0; /* only the pair is swapped */
    np.shown = np.eshown = -1;
    for (n = 0; n < NP_INFO_N; ++n) np.info[n] = widget_lookup(win, np_info_names[n], 1);
    for (n = 0; n < NI_N; ++n) np.iw[n] = widget_lookup(win, np_iw_names[n], 1);
    np.ihead = np.iw[NI_ART] && np.iw[NI_TITLE] && np.iw[NI_ARTIST] && np.iw[NI_ALBUM];
    np.iq = np.iw[NI_QV] && np.iw[NI_QV + 1] && np.iw[NI_QV + 2] && np.iw[NI_QV + 3] && np.iw[NI_QU] &&
            np.iw[NI_QU + 1] && np.iw[NI_QU + 2] && np.iw[NI_QU + 3] && np.iw[NI_QD] && np.iw[NI_QD + 1] &&
            np.iw[NI_QD + 2];
    np.irow = 1;
    for (n = 0; n < NPI_ROWS; ++n)
        if (!np.iw[NI_KEY + n] || !np.iw[NI_VAL + n]) np.irow = 0;
    np.relay = NP_RELAY;
    np.color = NP_NEUTRAL & 0xffffff; /* the asset's window colour */
    if (!widget_on(win, EVT_DESTROY, np_on_destroy, win)) {
        memset(&np, 0, sizeof np);
        return;
    }
    np.timer = timer_add(np_tick, (void *)0, NP_TICK_MS);
    np.interval = NP_TICK_MS;
    if (!np.timer) { /* the page stays stock; the destroy handler finds no window of ours any more */
        memset(&np, 0, sizeof np);
        return;
    }
    art = widget_lookup(win, "img_playcover", 1);
    if (art) {
        np.art = art;
        np_corner_init();
        widget_on(art, EVT_AFTER_PAINT, np_on_art_paint, (void *)0);
    }
    m1_bind(win, "btn_queue", np_on_queue, (void *)0);
    ly_start(win);
    if (np.ihead) {
        mb_art_size(&np.ia, NPI_ART, NPI_ART_R);
        widget_on(np.iw[NI_ART], EVT_AFTER_PAINT, np_on_info_art, (void *)0);
        if (np.info[1]) { /* label_album: the header shows the record's album */
            widget_set_visible(np.info[1], 0, 0);
            widget_set_sensitive(np.info[1], 0);
        }
    }
    np.fg = 1;
    np.barok = widget_on(win, EVT_WINDOW_TO_BG, np_on_background, win) &&
               widget_on(win, EVT_WINDOW_TO_FG, np_on_foreground, win);
    np_bar_apply(); /* the asset's tone until the cover's is known */
    np_work();
}

/* The hook (tools/pod.py PLAYING_INIT): stock first, then ours. */
int m1plus_playing_init(void *win, void *ctx) {
    int ret = stock_playing_init_trampoline(win, ctx);
    if (ret == RET_OK && win) np_start(win);
    return ret;
}
