/* What patch/pcnet.c lends the other network sources (the LibriVox catalog, patch/bknet.c, and the book download, patch/bkdl.c; docs/modules/audiobooks.md "LibriVox"). Internal: the pages never include this.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Two things. The job slot (docs/modules/network.md "Whose job it is"): a source asks pnw_spawn on the UI thread (the thread starts with pn.busy and its kind set, PN_KIND_BOOKS / PN_KIND_BOOKPREV), its thread
 * reads pnw_cancelled() between requests and ends with pnw_end(); the page cancels with pn_cancel(PN_K_BOOKS). And the episode download's way of fetching one file (pnw_download), for a thread of the caller's
 * own: it takes no slot and no place in the episode queue. The requests are pcnet.c's (pn_req over patch/net.h).
 */
#pragma once

int pnw_busy(void); /* a job of any kind is running */
/* UI thread: curl initialised, pn.busy and pn.kind set, then a detached thread running fn. PN_OK, or PN_MEM when there is no thread (nothing is busy then). */
int pnw_spawn(void *(*fn)(void *), int kind);
int pnw_cancelled(void); /* the page asked the running worker to stop (pn_cancel) */
void pnw_end(void); /* the worker's last call: not busy, the generation moved */
/* The answer at url into buf (PN_JSON_CAP + 1 bytes), *got bytes of it; PN_OK also for one cut at the cap. A 404 or 410 is PN_HTTP. */
int pnw_json(const char *url, char *buf, unsigned *got);
/* The answer at url into the file path, at most cap bytes: PN_OK, or the PN_* why (PN_NOTFEED: longer than cap); no file is left after a failure. */
int pnw_file(const char *url, const char *path, unsigned cap);

/* A download of the caller's (pnw_download). The caller zeroes it before the job; the worker writes got / total / step / gen / wait, the UI thread reads them and writes stop. */
typedef struct {
    volatile unsigned got, total, step,
        gen; /* bytes of the file on the card and in the buffer, its size (0 unknown), the progress step, the generation that moves with a step and with a wait to retry */
    volatile int wait,
        stop; /* wait: the thread sleeps before a retry; stop: non-zero ends the transfer at once (0 runs) */
} pnw_dl_t;
/* The file at path from url, to the end, the way an episode is downloaded (pn_dl_core: Range resume of path.part with If-Range, 512 KB chunks, the card's reserve, the stall limit, retries after 10, 20 and 40 s,
 * a text answer refused as PN_NOTAUDIO, the 2 GiB cap, the rename and the folder's sync). expect: the size the caller knows (0 = unknown; the server's length replaces it). PN_OK (also when path exists: a
 * leftover .part goes), PN_CANCELLED for w->stop (the .part stays), PN_GONE for an address that is not http(s), PN_STORAGE for a path over PN_DL_PATH_MAX with ".part", else the failure (PN_GONE, PN_NOTAUDIO,
 * PN_CARDFULL, PN_STORAGE, PN_NET, ...). Runs on the caller's thread (net_init was called on the UI thread before it was made). */
int pnw_download(pnw_dl_t *w, const char *url, const char *path, unsigned expect);
