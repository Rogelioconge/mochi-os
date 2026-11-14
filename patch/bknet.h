/* LibriVox on the Internet Archive: the catalog (patch/bknet.c, docs/modules/audiobooks.md "LibriVox"). Popular and searched books, a book's parts, the pictures.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The pure parts (the query, the docs parser, the files scanner) have no state. The jobs run in patch/pcnet.c's one worker slot (patch/pcnetw.h): never beside a refresh or another job (a book download is a thread of its own and runs beside them). All the
 * bn_* calls below run on the UI thread; a worker only writes the record they read, and no widget is touched. Statuses are pcnet.h's PN_* codes (PN_NOBOOK is new).
 */
#pragma once

#include "books.h"

#define BN_ROWS 25 /* books a search or the popular list gives (rows=25) */
#define BN_ID 80 /* an identifier with its NUL; a longer one is skipped, never cut (it goes into addresses and paths) */
#define BN_AUTHOR 64 /* an author, UTF-8 bytes with the NUL (cut before a continuation byte) */
#define BN_TERM 96 /* the cleaned search term, with the NUL */
#define BN_URL 1200 /* the longest request address */
#define BN_FILES_CAP 2097152u /* the files answer is refused above this (2 MiB; 300 parts are about 300 KB) */
#define BN_OBJ 4096 /* the largest object of the files answer the scanner holds; a larger one is skipped */
#define BN_DIR \
    "/mnt/mmc/.m1plus/audiobooks/search" /* scratch: the thumbnails p<i>.jpg|png (popular) and s<i>.jpg|png (search), preview.jpg|png, files.json while it is scanned */
#define BN_FILES_PATH BN_DIR "/files.json"
#define BN_HOST "https://archive.org"
#define BN_FORMAT "64Kbps MP3" /* the format of a part: every LibriVox item has one 64 kbit/s MP3 a section */

typedef struct {
    char id[BN_ID]; /* the item's identifier, [A-Za-z0-9._-] only */
    char title[BK_TITLE];
    char author[BN_AUTHOR]; /* "" when the answer gave none */
    unsigned secs; /* the whole book's running time in seconds, 0 = unknown */
} bn_row_t;

typedef struct {
    char name[BK_FILE]; /* the file's name in the item, no '/' and no control byte */
    char title[BK_TITLE]; /* the file's title, else its name without the extension */
    unsigned secs; /* 0 = unknown */
    unsigned bytes; /* 0 = unknown */
} bn_part_t;

/* ---- Pure parts */

/* The search term for a Lucene query: UTF-8 kept, every control byte and Lucene special character (+ - & | ! ( ) { } [ ] ^ " ~ * ? : \ /) a word break, the breaks collapsed and trimmed, a word that is exactly AND, OR
 * or NOT lower-cased (an operator otherwise), cut at size - 1 bytes on a character boundary, a byte sequence that is not UTF-8 dropped. Returns its length (0: nothing left, out is ""). */
int bn_clean_term(const char *term, char *out, unsigned size);
/* The request of the popular list (term empty, or nothing left of it after bn_clean_term: returns 0) or of a search (returns 1) into out (size bytes, BN_URL fits any term); -1 when it does not fit. */
int bn_query_url(const char *term, char *out, unsigned size);
/* The length of the well formed UTF-8 sequence at s (1 to 4), 0 when there is none there (a stray continuation byte, a lead byte without its continuations, a byte that is no lead; overlongs and surrogates are not told apart). Reads at most 4 bytes, none past a NUL. */
unsigned bn_seq(const unsigned char *s);
/* The identifier is non empty, shorter than BN_ID and only [A-Za-z0-9._-] (and not "." or ".."). */
int bn_id_ok(const char *id);
/* "H:MM:SS", "MM:SS", "SS" or "SS.fraction" as whole seconds; 0 for anything else (and for none). A group is at most 999999. */
unsigned bn_secs(const char *text);
/* The books of an advancedsearch answer (response.docs[]): up to max, in order. A doc with no title or an identifier bn_id_ok refuses is skipped; creator is a string, the first of an array, or absent; runtime is
 * bn_secs' text, or absent. Fields too long for their place are cut on a character boundary. An object cut short by the end of the text is not kept. Returns how many (0: an empty list), -1: no response.docs array. */
int bn_parse_docs(const char *json, unsigned n, bn_row_t *out, int max);
/* The parts of a metadata/<identifier>/files answer in the file at path, read in chunks and scanned object by object (an object over BN_OBJ bytes is skipped; the answer is never held whole; reading stops at
 * BN_FILES_CAP): the objects of the top-level "result" array whose "format" is BN_FORMAT, sorted by name with bk_natcmp, the first max (at most BK_MAX_PARTS) of them. A name with '/' or a control byte, or too long, is
 * skipped; title falls back to the name without its extension; length is bn_secs' text, size is digits. Returns the parts kept (0: none), -1 when the file cannot be read or the answer has no "result" array.
 * *complete: the array was closed (an answer cut short, or malformed past that, gives the parts whole before the break and *complete 0; a job takes that for a failed answer). *more: parts were left out
 * because max was reached. */
int bn_scan_files(const char *path, bn_part_t *out, int max, int *complete, int *more);

/* ---- The catalog job. The popular list and the last search are kept apart; the rows of the set asked for last are the current ones (bn_row). */
enum { BN_S_IDLE = 0, BN_S_QUERY = 1, BN_S_THUMBS = 2, BN_S_DONE = 3 };

/* Show the popular list (term empty or nothing left of it) or search for term (UTF-8). The held popular list (answered with rows) is fetched again by nobody: it becomes the current set and only the thumbnails that were
 * not tried are fetched (none: nothing starts, state BN_S_DONE, 0 returned, no guard asked). A search drops the old search rows and their thumbnails. Otherwise the guards, then one worker: the query, then the
 * thumbnail of each row one by one (https://archive.org/services/img/<id>). 0 when it ran or was not needed; PN_BUSY when a worker runs (the page waits and asks again); PN_MEM when the request does not fit; else
 * the guard's PN_*. */
int bn_catalog(const char *term);
int bn_thumbs(
    void); /* fetch the current rows' untried pictures, no query: 0 started or nothing held, PN_BUSY, or pn_guard's code */
int bn_catalog_state(
    void); /* BN_S_*: the query runs / its answer is in and the thumbnails follow / the worker has ended */
int bn_catalog_code(
    void); /* the query's result once the answer is in: PN_OK (with bn_catalog_count() 0: no books), PN_NET, PN_HTTP, ..., PN_CANCELLED */
int bn_catalog_search(void); /* the current set is a search (else the popular list) */
unsigned bn_gen(void); /* moves with every answer, thumbnail and the end of a job (the catalog's and the preview's) */
int bn_catalog_count(
    void); /* rows of the current set (valid once the state is past BN_S_QUERY with PN_OK; 0 before and after a failure) */
const bn_row_t *bn_row(int i); /* row i of the current set, NULL out of range */
int bn_thumb(int i, char *path, unsigned size); /* 1 and the path of row i's picture when it has arrived */
int bn_thumb_state(int i); /* 0 not yet, 1 the picture is there, 2 it could not be had (the placeholder stays) */
void bn_catalog_clean(
    void); /* the pictures go, the search is forgotten (the popular rows stay, their pictures untried again); no worker must run (the page does this when it closes) */

/* ---- The preview job: one book's parts. */
/* Fetch the files answer of the identifier to BN_FILES_PATH, scan it into the part list held in memory, fetch the picture to BN_DIR/preview.jpg|png, remove the answer file. The guards first. 0 when the worker runs;
 * PN_BUSY; PN_NOBOOK at once for an identifier bn_id_ok refuses; PN_MEM; else the guard's PN_*. The old preview is dropped when this starts. */
int bn_preview(const char *id);
int bn_preview_state(void); /* 0 none (or cancelled), 1 running, 2 done: bn_preview_code says how */
int bn_preview_code(
    void); /* PN_OK; PN_NOBOOK: the item has no BN_FORMAT part; PN_NOTFEED: the answer is cut or too large; PN_NET, PN_HTTP, PN_GONE, PN_CERT, ...; PN_CANCELLED */
const char *bn_preview_id(void); /* the identifier asked for ("" when none) */
int bn_preview_count(void); /* parts held (0 until the state is 2 with PN_OK) */
const bn_part_t *bn_part(int i); /* part i in reading order, NULL out of range */
/* The held parts' totals: *parts, *secs (the sum of the known running times), *bytes (the sum of the sizes; saturates), *more: parts beyond BK_MAX_PARTS were left out. 1 when a preview is held. */
int bn_preview_totals(unsigned *parts, unsigned *secs, unsigned *bytes, int *more);
int bn_preview_cover(char *path, unsigned size); /* 1 and the path of the picture file when it has arrived */
void bn_preview_drop(void); /* free the held parts, remove the picture (nothing while a worker runs) */
