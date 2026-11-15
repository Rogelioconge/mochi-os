/* Artist split: one artist field naming several artists ("A feat. B", "A; B") listed under each name (docs/modules/artists.md "Separators" and "Split index").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Off by default (the file below absent or "0"): then nothing here is called and every page runs the stock queries as before. On, the Artists page's rows are built from the library's songs
 * (as_rows), and an artist row it made (as_is_row) is answered from the songs instead of the stock queries keyed on the whole field: its albums (as_albums), its songs (as_fill, as_load),
 * an album's tap (as_open_album) and its play (patch/songops.c so_play_own).
 */
#pragma once

#define AS_FILE \
    "/mnt/data/m1plus/library-artist-split" /* "0" or missing: off; "1": on with M1_SPLIT_DEFAULT; "m<decimal>": on with that M1_SPLIT_* mask (0: splits nothing); "o<decimal>": off, keeping that mask */
#define AS_EXCEPTIONS \
    "/mnt/mmc/artist-exceptions.txt" /* the card's own never-split names, one a line (blank lines and lines starting with # skipped), added to the built-in list */
#define AS_MARK 0x41535031 /* REC_CLASS of a row as_rows made ("ASP1"): stock rows leave it 0 */

#define AS_SEPS 10 /* the separators the page lists: M1_SPLIT_* bits 0 .. 9 */
#define AS_ALL ((1u << AS_SEPS) - 1)

/* The separators the setting asks for (M1_SPLIT_* bits), 0 when it is off. */
unsigned as_mask(void);
/* Settings > Library > Split Artists: the switch (1 on), its toggle, separator k's state and its toggle (the new state, -1: not saved, unchanged). */
int as_setting(void);
int as_toggle(void);
int as_sep(int k);
int as_sep_toggle(int k);
/* The Artists page's rows (a deque of stSongInfo the caller destroys, one per distinct name, the "Unknown Artist" row, id -1, last), or NULL when there are no songs or no memory. */
void *as_rows(void);
/* The Home artist photo pass (patch/homecover.c): as_session(1) reads the options once (1 when the setting is on), as_session(0) ends it; as_lead gives, while a session is open, the first name of an
 * artist field (1 when it did). The pass keys an album by that name instead of the whole field. */
int as_session(int open);
int as_lead(const char *field, char *out, unsigned n);
/* A one-row deque (the caller destroys it) holding the row of the first name in an artist field, or NULL when the setting is off or the field has no name. */
void *as_first_row(const char *field);
/* 1 when the record is a row as_rows made. */
int as_is_row(void *rec);
/* The row's name and whether it is the Unknown Artist row. */
const char *as_row_name(void *row, int *unknown);
/* The artist's songs into *pdeq_showlist (replacing what it held) the way a stock class query leaves them; returns the count (0: none, the list is then empty). The browsing record is untouched. */
int as_fill(const char *name, int unknown);
/* as_fill after the stock queries that set the browsing record to the artist's songs (songs_artist_list's contract): the list is in *pdeq_showlist, good until the next query; NULL when none. */
void *as_load(void *row);
/* The artist's albums for coverflow_artist_albums: library album rows (cc_albums order) holding at least one of the songs, then the All songs record always last (counted when keep_card and two or more albums, or none; else kept past the count as the stock list does); keys by cc_album_key. */
int as_albums(void *row, int keep_card, void **albums, unsigned **keys);
/* The album page on album `index` of as_albums: the library album's own page (cc_open_album on the Albums list). -1 when it is not there. */
int as_open_album(void *row, int index);
