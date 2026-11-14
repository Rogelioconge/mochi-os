/* The Audiobooks page's state and the helpers its two source files share (patch/bkpage.c: the Library and Book levels, the window; patch/bkfind.c: the LibriVox and Preview levels).
 * docs/modules/audiobooks.md "The page" and "LibriVox".
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "pcwrap.h"
#include "books.h"

enum {
    BL_LIB = 0,
    BL_BOOK = 1,
    BL_LV = 2,
    BL_PRE = 3,
    BL_SRCH = 4
}; /* the levels: the Library, a book, LibriVox (the Discover level: Popular), a LibriVox book's preview, the search level (the field and its rows); LibriVox, Preview and search are bkfind.c's (level >= BL_LV) */
enum {
    BS_TITLE = 0,
    BS_SUB,
    BS_BTN,
    BS_DIM,
    BS_META,
    BS_HINT,
    BS_SECH,
    BS_STITLE,
    BS_SLEFT,
    BS_CTITLE,
    BS_N
}; /* the page's text styles (tools/pod_ui.py BK_STYLES, in that order) */
enum {
    BP_BODY = 0,
    BP_PLAY = 1,
    BP_LV = 2,
    BP_FIELD = 3,
    BP_CLEAR = 4,
    BP_CONT = 5,
    BP_ALL = 6
}; /* what a touch hit: a row, the header's capsule, the Library's LibriVox row, the search field, the field's clear button, the Continue Listening item, the See All row */

typedef struct { /* a book's progress as the Library shows it */
    unsigned char have, state;
    unsigned short permille, cur;
    unsigned short total; /* the parts its .librivox manifest names, 0 for a book with none */
    unsigned short
        rank; /* the place of its most recently played part in the resume ring (0 the latest), 0xffff for none: Continue Listening is the in-progress book with the smallest */
} bk_st_t;

typedef struct
{ /* a part a LibriVox manifest names, on the card or not: its row on the Book level (the manifest's order) */
    char title[BK_TITLE]; /* the local file's name without its extension: what the part's row says on the card too */
    unsigned secs, bytes; /* 0 = unknown */
    short part; /* its place in bk.parts (the files on the card), -1 when it is not on the card */
} bk_mrow_t;

typedef struct {
    void *win, *view, *sv, *status, *title, *fade, *big;
    void *st_title, *st_sub, *st[BS_N]; /* hidden labels whose styles the rows and the header use */
    char root[BK_FILE + 20];
    bk_book_t *books;
    int nbooks;
    bk_part_t *parts; /* the open book's parts; the Library level borrows it to read each book's progress */
    int nparts;
    bk_st_t *bst; /* per book */
    int level, sel, fg;
    unsigned sel_hash; /* the open book's key: found again when the folders are read again */
    int lib_off, all_off; /* the Library's offset to come back to; the See All page's */
    int cur, state; /* the open book: the part to resume, BK_* state */
    unsigned permille;
    unsigned rev; /* pc_rev() the rows were made at */
    unsigned sig; /* bk_sig() the Library's tiles were made for */
    int g_lv; /* the cover grid holds the LibriVox level's thumbnails: the Library makes its tiles again */
    unsigned timer, load_timer;
    int press, pbtn, down, down_part, down_x,
        down_y; /* the row under the finger + 1; the header button pressed (BP_*); the row a press began on + 1 and what of it */
    int collapsed;
    grid_t g; /* the Library's covers, the LibriVox level's thumbnails */
    grid_t hg; /* the header's cover (one tile; its spinner frames) */
    grid_t pt; /* the parts' texts (no covers) */
    grid_t sg; /* Continue Listening's cover (one tile, PP_SHELF_ART px) */
    void *atlas; /* pc_atlas decoded with its alpha (the play disc on that cover), made on first use */
    int cont, all; /* Continue Listening: the book (-1 for none); the Library shows every book (the See All page) */
    int l_shelf, l_hbooks, l_list, l_n, l_all, l_hdisc,
        l_lv; /* the Library's blocks (content y): the shelf, the Books header (0: no book), the books' first row, the rows shown, the See All row, the Discover header, the LibriVox row */
    void *find; /* the navbar's magnifier (the Podcasts Discover level's btn_search): on the LibriVox level only */
    unsigned cont_hash; /* the book the shelf's cover was made for */
    unsigned ctitle[BK_TITLE_MAX]; /* its title cut to PP_SHELF_W, ctn chars */
    int ctn;
    void *chev, *ltile; /* the shared chevron; the LibriVox row's tile (pod_ic_discovertile) */
    unsigned name[BK_TITLE_MAX]; /* the header's title, wrapped */
    pw_line_t nl[BK_NAME_LINES];
    int nn, y_name, y_sub, y_btn, y_list, collapse;
    unsigned bgen, bsig; /* bd_gen() and bk_dl_sig() the page last looked at */
    unsigned awake; /* the keep-awake timer: while a download runs the device does not go to standby */
    int mrows; /* the Book level lists every part the manifest names (bk.mp, nm of them), those not on the card too: the manifest names parts that are not on the card */
    bk_mrow_t *mp; /* the manifest's parts in order, while mrows */
    int nm;
    unsigned dl_missing; /* the manifest's parts not on the card */
    int pl_row; /* the Book level's row the player is on (-1 none): it has the playing wave before its grey line */
    void *wave; /* the playing marker (ah_wave, the album page's: grid_wave_make) */
    int has_man; /* the open book has a readable LibriVox manifest (the "..." and its sheet are there) */
    unsigned man_parts, man_secs, man_bytes; /* the manifest's totals: parts, running time, size */
    void *np, *more; /* the navbar's Now Playing and "..." buttons */
    void *sh_scrim, *sh_card, *sh_row[4], *sh_tx[4], *sh_hr[4],
        *sh_vl; /* the "..." sheet's widgets (tools/pod_ui.py BK_SHEET_ROWS; sh_vl: the speed row's grey value) */
    int sheet; /* the sheet is open */
    unsigned del_hash; /* Delete Book waits for this book's download thread to let go (0: none) */
    char del_dir[BK_FILE]; /* ... and its folder */
} bk_t;
extern bk_t bk;
#define BK_FIND (bk.level >= BL_LV) /* a level of patch/bkfind.c: LibriVox, Preview, the search level */

/* Shared by the levels (patch/bkpage.c). */
void bk_show(void *w, int on);
int bk_off(void);
void bk_redraw(void);
void bk_kick(void);
void bk_size(void);
void bk_fade(void);
void bk_title_show(void);
void bk_level_title(
    void); /* a level was made at its scroll offset: the navbar's small title and buttons follow it at once (call after the offset is set) */
void bk_collapse(void);
int bk_wide(unsigned *dst, int cap, const char *utf8);
int bk_lines(void *st, unsigned *s, int n, int room, int maxl, pw_line_t *out);
void bk_cat(char *out, unsigned size, const char *s);
void bk_dot(char *out, unsigned size, const char *piece);
void bk_kb_text(char *out, unsigned size, unsigned kb);
/* A length of time: Podcasts' 19m (a book's totals and a part's grey line are in minutes too). */
void bk_mins(char *out, unsigned size, unsigned secs);
void bk_text(void *canvas, const unsigned *s, int n, int x, int y, int w, int h);
void bk_text_utf8(void *canvas, void *style, const char *utf8, int x, int y, int w, int h);
void bk_capsule(void *canvas, int x, int y, int w, int h, unsigned argb);
void bk_chevron(void *canvas, int x, int y);
void bk_load_library(int off);
void bk_set_title(const char *utf8); /* the navbar's small title */
void bk_open_dir(
    const char *dir); /* the books read again, the Book level of the folder dir (the Library when it is not there) */
const char *bf_word(int code); /* a PN_* code in the page's words (patch/bkfind.c) */
/* A book's grey line: "37 parts - 13 h 6 min - 380 MB", the pieces that are known (parts only above one); a part's: parts 0. */
void bf_line(char *out, unsigned size, unsigned parts, unsigned secs, unsigned bytes);
/* The header's title wrapped and the blocks' tops of a book or preview titled `title` (bk.name / nl / nn, y_name, collapse, y_sub, y_btn, y_list); extra: grey lines more than one above the capsule (a preview's author). */
void bk_header(const char *title, int extra);

/* The LibriVox and Preview levels (patch/bkfind.c). */
void bf_reset(void); /* the page opens or is destroyed: the state is zero */
void bf_setup(void *win); /* the page's widgets of the search field, the LibriVox row's tile */
void bf_free(void);
void bf_leave_cancel(
    void); /* another level takes over: what waits or runs is stopped, the field goes, the preview is let go */
void bf_enter(void); /* the LibriVox level from the Library: fresh (popular, at the top) */
void bf_search(void); /* the magnifier: the search level (an empty field, the keyboard opens) */
int bf_back(void); /* Back on a LibriVox or Preview level: 1 when it handled it */
int bf_count(void); /* rows of the level */
int bf_top(void); /* where the rows start (content y) */
int bf_content(void); /* the content's height */
void bf_paint(void *canvas);
int bf_hit(void *e, int *part);
void bf_tap(int a, int part);
void bf_sync(void); /* the 1 s tick */
int bf_load_pending(void);
void bf_load(void); /* one thumbnail or the cover */
void bf_fg(void); /* the page is in front again */
void bf_bg(void);
