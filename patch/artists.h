/* The Artists page (patch/artists.c; docs/modules/artists.md). Copyright (c) 2026 Xin. MIT licence (see LICENSE). */
#pragma once
#include "libsrc.h"

int artists_open(int home); /* 0 Artists, HOME_GENRE, HOME_COMPOSER; 0 once up, -1 if it could not open */
/* The artist `name` as the Artists page lists it (the first name of the field with the artist split on, else the row of the stock Artists / Album Artists list, ASCII case aside; the Unknown Artist row never) as a deque of one
 * stSongInfo the caller destroys; NULL when there is none. Loads the stock list: never from a paint or a tick. */
void *artists_find(const char *name);
int artists_open_src(
    const lib_src_t *src); /* the Artists page fed by src->list(LS_ARTISTS); NULL or &lib_stock = artists_open(0) */
