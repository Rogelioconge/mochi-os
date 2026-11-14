/* LibriVox on the card: the book folder, its manifest and the download job (patch/bkdl.c, docs/modules/audiobooks.md "LibriVox").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * A downloaded book is Audiobooks/<title>/ with cover.jpg|png, the parts NNN <title>.mp3 and the manifest .librivox (a dot file: the model never lists it). The manifest is the state of a half-downloaded
 * book: the parts it names that have no file are the ones still to fetch. Everything here runs on the UI thread except the job's worker, which writes only the record the page reads (bd_progress).
 * Statuses are pcnet.h's PN_* codes.
 */
#pragma once

#include "books.h"
#include "bknet.h"

#define BD_MAGIC "M1PLUS-LIBRIVOX 1" /* the manifest's first line */
#define BD_MANIFEST ".librivox"
#define BD_MAN_CAP \
    131072u /* a manifest is read (and written) up to this; a larger file is refused (300 parts are about 70 KB) */
#define BD_BASE_MAX 72 /* bytes of a folder's title; ' (99)' follows on a collision */
#define BD_DEFAULT_TITLE "Audiobook" /* the folder of a title with nothing usable in it */

typedef struct {
    char file[BK_FILE]; /* the local name in the book folder: NNN <title>.mp3 */
    char name[BK_FILE]; /* the archive's file name (the address's last component, percent-encoded when asked) */
    char title[BK_TITLE]; /* "" = none */
    unsigned secs, bytes; /* 0 = unknown */
} bd_part_t;

typedef struct {
    char root[BK_FILE + 20]; /* "/mnt/mmc/<Audiobooks as the card spells it>" */
    char dir[BK_FILE]; /* the book's folder name */
    char id[BN_ID];
    char title[BK_TITLE];
    char author[BN_AUTHOR];
    int n; /* parts */
    bd_part_t parts[BK_MAX_PARTS];
} bd_book_t; /* about 108 KB: a heap record (bd_open / bd_free) */

/* ---- Names */
/* in made safe for a FAT file name, UTF-8 kept: \ / : * ? " < > | and every control byte a space, a byte sequence that is not UTF-8 dropped, spaces collapsed, no leading space or dot, no trailing space or dot,
 * cut at max bytes on a character boundary. out has max + 1 bytes. Returns the length ("" is possible). */
unsigned bd_fat(const char *in, unsigned max, char *out);

/* ---- The manifest and the folder */
/* The books's manifest in the folder dir of the Audiobooks folder: a heap record (bd_free), or NULL when there is none, it is over BD_MAN_CAP, or it is malformed: the first line is not BD_MAGIC, no i= (bn_id_ok),
 * a part line without exactly 5 fields (file, seconds, bytes, name, title), a number that is not digits (or is over 2^32 - 1), a file or name that is empty, has '/', '\' or a control byte, is BK_FILE bytes or more, or
 * starts with '.' (the local file), the same local file twice, over BK_MAX_PARTS parts, a text line that is no key=value. Unknown keys are ignored; CR before LF is ignored; t= and a= are cut to fit. */
bd_book_t *bd_open(const char *dir);
void bd_free(bd_book_t *b);
/* Part i's file is on the card (it is renamed from .part only when complete). */
int bd_present(const bd_book_t *b, int i);
/* b's parts: *present, *missing, *bytes (the sizes of the missing ones; saturates; unknown sizes count 0). */
void bd_counts(const bd_book_t *b, unsigned *present, unsigned *missing, unsigned *bytes);
/* The folder whose manifest (its header: first line and i=) names the identifier, into dir (size bytes): 1, else 0. At most BK_MAX_BOOKS folders are looked at. */
int bd_find(const char *id, char *dir, unsigned size);
/* The book folder of the held preview (bn_preview_id() = id, parts held) made on the card, or the one that already names id (reused as it is). Audiobooks/ is made when the card has none. Folder:
 * <title made safe by bd_fat, BD_BASE_MAX bytes>, then ' (2)' ... ' (99)' while a folder of that name exists that is not this identifier's; cover.jpg|png (a copy of the preview's picture when it arrived);
 * the manifest (written last, atomically, so a folder with a manifest is always whole). Local part files are NNN <title>.mp3, the number zero-padded to the part count's width (1, 2 or 3 digits), the title
 * bd_fat'd, the archive name's stem when the title is empty, 'Part N' when that too; cut so that the name is under BK_FILE bytes and the full path with '.part' within PN_DL_PATH_MAX. dir (size bytes) gets
 * the folder's name. PN_OK; PN_NOBOOK (id is not the held preview's, or no parts are held); PN_STORAGE (no card, no room to make the folder or write the manifest, no folder name free); PN_MEM. It needs
 * no network and no thread, so it also works while another book downloads (bd_start then queues the book). */
int bd_create(const char *id, const char *title, const char *author, char *dir, unsigned size);

/* ---- The download: a queue of books and a thread of its own that fetches them one at a time, in the order they were asked. It runs beside a job of pcnet.c's slot (a search, a refresh, ...) and beside the
 * episode queue's thread, and never gives way to either (docs/modules/network.md). */
enum { BD_R_NONE = 0, BD_R_DONE = 1, BD_R_PAUSED = 2, BD_R_FAILED = 3 };
enum { BD_S_NONE = 0, BD_S_RUN = 1, BD_S_WAIT = 2 };
/* Download the missing parts of the book in folder dir, in order, to the end: it runs at once when no book downloads, else it joins the end of the queue (BD_QMAX = 16 books wait behind the running one) and the
 * thread takes it when the books before it have ended. 0: the thread runs, the book runs or waits already (nothing is added twice), or nothing was missing (the result is DONE, no thread). PN_QFULL for a full
 * queue; PN_NOBOOK for a folder with no readable manifest; PN_MEM; else the guard's PN_* (card, Wi-Fi, clock, CA bundle). */
int bd_start(const char *dir);
/* The book of key (as bd_active gives it) stops: the running one at once, keeping its .part (the result is PAUSED; the thread goes on with the next book), a waiting one leaves the queue (PAUSED). Nothing
 * else changes for a key that neither runs nor waits. */
void bd_pause(unsigned key);
/* BD_S_RUN while the book of key is the one being fetched, BD_S_WAIT while it is in the queue, else BD_S_NONE. */
int bd_state(unsigned key);
/* The running book's key (pc_hash("audiobooks/" + dir), bk_book_t.hash), 0 when no book runs (also in the moment between one book and the next). */
unsigned bd_active(void);
/* While a book runs (1): *part the index of the part being fetched (0 based), *parts the book's, *got and *total the bytes of it (total 0 unknown), and *wait 1 while the worker waits to retry. */
int bd_progress(unsigned *part, unsigned *parts, unsigned *got, unsigned *total, int *wait);
unsigned bd_gen(
    void); /* moves on every progress step, every part, every wait, every change of the queue, the start and the end of a book; it only grows, across jobs too */
/* The last result of a book in this session (key as bd_active gives): BD_R_*; for BD_R_FAILED *code is the PN_* (PN_GONE a part the archive no longer has, PN_NOTAUDIO, PN_CARDFULL, PN_NET, ...). A book that
 * leaves the queue (paused, or because a failure every book would meet stopped the queue) is PAUSED. Asking for a book again clears it. At most 16 books are remembered. */
int bd_result(unsigned key, int *code);
