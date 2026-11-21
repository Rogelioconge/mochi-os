/* M1+ Music Radio: the ICY stream metadata record hciplayer's read-only tap publishes and demo reads
 * (docs/modules/radio.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Built into hciplayer's payload (PEQ_PLAYER: player.h, which tools/mod_player.py writes; patch/icy.c publishes on
 * every ICY metadata packet from MPlayer's HTTP and FFmpeg's HTTPS paths); demo (stock.h) only includes the file's
 * path and layout, to mark and read it.
 */
#pragma once

#ifdef PEQ_PLAYER
#include "player.h"
#else
#include "stock.h"
#endif

/* The "wanted" mark and the record are one file on tmpfs: demo creates ICY_FILE holding ICY_MAGIC, seq 0 and a fresh
 * session gen when a station starts, and unlinks it when the station stops or local playback takes over. hciplayer
 * publishes only while ICY_FILE exists and starts with ICY_MAGIC, keeping demo's gen and bumping seq (seq == seq_end
 * guards against a torn read). */
#define ICY_FILE "/tmp/m1plus-icy"
#define ICY_MAGIC "M1IC001" /* 8 bytes with its NUL */
#define ICY_RAW_MAX 512 /* raw ICY metadata packet kept, NUL-terminated */

typedef struct {
    char magic[8];
    int seq; /* 0: mark only (no packet yet); +1 at every packet written by hciplayer */
    int gen; /* demo's play-session counter: stale packets from an earlier station never match */
    char raw[ICY_RAW_MAX]; /* raw ICY string, e.g. "StreamTitle='Artist - Song';" */
    int seq_end; /* = seq */
    int pad;
} icy_record;
_Static_assert(sizeof(icy_record) == 16 + ICY_RAW_MAX + 8, "icy record layout");

#ifdef PEQ_PLAYER
void icy_mplayer_msg(int mod, int lev, const char *fmt, const char *info);
int icy_av_opt_set(void *obj, const char *name, const char *val, int flags);
#endif
