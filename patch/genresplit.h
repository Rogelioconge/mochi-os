/* Genre split: one genre field naming several genres ("Rock; Pop") listed under each name (docs/modules/artists.md "Split Genres").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Off by default (the file below absent or "0"): then nothing here is called and the Genres page runs the stock query as before. On, the Genres page's rows are built from the stock genre list
 * (gs_rows, one row per distinct tag), and a row it made (gs_is_row) is answered with the songs of every tag that names it (gs_fill) instead of the stock query keyed on the whole field.
 */
#pragma once

#include "common.h"

#define GS_FILE \
    "/mnt/data/m1plus/library-genre-split" /* "0" or missing: off; "1": on with GS_DEFAULT; "m<decimal>": on with that M1_SPLIT_* mask (0: splits nothing); "o<decimal>": off, keeping that mask */
#define GS_EXCEPTIONS \
    "/mnt/mmc/genre-exceptions.txt" /* the card's own never-split names, one a line (blank lines and lines starting with # skipped) */
#define GS_MARK 0x47535031 /* REC_CLASS of a row gs_rows made ("GSP1"): stock rows leave it 0 */

/* The separators a genre field may be split on, and the settings page lists: the punctuation ones. The splitter's words (feat., vs., x, with, and) join artists, never genres, and "and" would
 * cut "Drum and Bass" and "Rock and Roll", so the setting has no bit for them. */
#define GS_ALL (M1_SPLIT_SEMICOLON | M1_SPLIT_SLASH | M1_SPLIT_AMPERSAND | M1_SPLIT_COMMA | M1_SPLIT_PLUS)
/* The default mask is semicolon alone: a genre field is not an artist field. "R&B" and "Folk, World, & Country" are single genres, so & and , are off until the user asks for them, and a slash
 * is off because "Rock/Pop" and "Pop/Rock" are single names in the wild. */
#define GS_DEFAULT M1_SPLIT_SEMICOLON

/* The separators the setting asks for (M1_SPLIT_* bits), 0 when it is off. */
unsigned gs_mask(void);
/* Settings > Library > Split Genres: the switch (1 on), its toggle, separator k's state (M1_SPLIT_* bit k, one of GS_ALL) and its toggle (the new state, -1: not saved, unchanged). */
int gs_setting(void);
int gs_toggle(void);
int gs_sep(int k);
int gs_sep_toggle(int k);
/* The Genres page's rows (a deque of stSongInfo the caller destroys, one per distinct name, the "Unknown Genre" row, id -1, last; empty when every tag is left out), or NULL when the stock genre list is empty or there is no memory.
 * *pdeq_showlist is left empty (the stock list's records change owner, as the page's own lists do). */
void *gs_rows(void);
/* 1 when the record is a row gs_rows made. */
int gs_is_row(void *rec);
/* The genre's songs into *pdeq_showlist (replacing what it held) the way a stock class query leaves them; returns the count (0: none, the list is then empty). Every tag the name comes from is
 * asked with the stock genre query, so the rows are stock's own; the browsing record is left as the stock query left it (songs_genre_record). */
int gs_fill(const char *name, int unknown);
