/* M1+ Music VU Meter Mode: the level record the player's tap publishes and the page reads (docs/modules/vu.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Built into hciplayer's payload (PEQ_PLAYER: player.h, which tools/mod_player.py writes; patch/vu.c measures and
 * publishes); demo (stock.h) only includes the file's path and layout, to read it.
 */
#pragma once

#ifdef PEQ_PLAYER
#include "player.h"
#else
#include "stock.h"
#endif

/* The "wanted" mark and the record are one file on tmpfs: the player measures only while VU_FILE exists and starts with
 * VU_MAGIC (demo creates it with just the magic, 8 bytes, when the page opens, and unlinks it when the page closes). The
 * player rewrites it whole, in place, at each block, never fsynced; the page reads it whole and keeps the read when
 * `seq == seq_end` (a torn read differs). */
#define VU_FILE "/tmp/m1plus-vu"
#define VU_MAGIC "M1VU001" /* 8 bytes with its NUL */
#define VU_RING 64

/* A stretch of the stream of at least 10 ms (short blocks are merged), the audible time and the levels of its first two
 * channels (a one-channel stream: both the same), normalised to full scale 1.0 (above 1.0: over). */
typedef struct {
    long long
        due_us; /* CLOCK_MONOTONIC us when its first frame is audible: the time the block was filtered plus the audio output's delay then */
    int dur_us; /* its length */
    int frames;
    float peak[2]; /* max |x| */
    float sumsq[2]; /* sum of x * x over the frames: rms = sqrt(sumsq / frames) */
} vu_entry;
_Static_assert(sizeof(vu_entry) == 32, "entry layout");

typedef struct {
    char magic[8];
    int seq; /* +1 at every write: new data; a seq that stops changing is a player with no new blocks (paused, stopped, no stream) */
    int rate; /* Hz of the stream now playing; 0: no levels (DSD, a special format, the kill switch, no stream yet) */
    int channels; /* 1 or 2: the stream has one channel (both meters show it) or two or more (the first two) */
    int count; /* entries in use, 0 .. VU_RING */
    int head; /* index of the newest entry; the older ones lie before it, wrapping */
    int pad;
    long long now_us; /* CLOCK_MONOTONIC us when this write was made */
    vu_entry ring[VU_RING];
    int seq_end; /* = seq */
    int pad2;
} vu_record;
_Static_assert(sizeof(vu_record) == 40 + 32 * VU_RING + 8, "record layout");
_Static_assert(__builtin_offsetof(vu_record, ring) == 40, "ring offset");

#ifdef PEQ_PLAYER
/* The player's side (patch/vu.c). */
void *vu_open(void); /* the file when it is wanted (opened r+b), else 0: the one check a block costs */
int vu_supported(
    int format,
    int bps); /* 1: blocks of this af format can be measured (float, signed 16/24/32-bit and 8-bit unsigned PCM, little endian) */
void vu_note(int rate, int channels); /* a stream starts: rate 0 for no levels */
/* Measure a block (read-only) and publish it; closes f. delay_us: the audio output's delay when it was filtered. */
void vu_block(void *f, const void *audio, int format, int bps, int nch, int rate, unsigned frames, int delay_us);
#endif
