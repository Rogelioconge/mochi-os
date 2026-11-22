/* M1+ Music Crossfade: the sticky output format and its continuous sample-rate conversion (docs/modules/crossfade.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Built into hciplayer's payload (PEQ_PLAYER). hciplayer statically links libswresample; its functions are called at their
 * pinned addresses (tools/mod_player.py PINS). One xf_src is one swr context plus the converted frames not yet used; it moves
 * whole from the instance that converts Track B during the overlap to Track B's own filter instance, and across a gapless join
 * between tracks of one input format.
 */
#pragma once
#include "player.h"

/* swr's filter quality in one place: the polyphase filter's length (CPU grows with it) and linear interpolation between
 * phases (0 = off). */
#define XF_SRC_FILTER_SIZE 16
#define XF_SRC_LINEAR 0
#define XF_SRC_CHUNK 32 /* input frames per refill when frames are pulled one at a time (the overlap) */

typedef struct {
    void *swr; /* SwrContext *, float interleaved in and out */
    int in_rate, out_rate, nch; /* nch 1 or 2 */
    int cap; /* frames the fifo holds */
    int head, count; /* converted frames waiting: fifo[head .. head + count) */
    float *fifo;
} xf_src;

xf_src *xfsrc_new(int in_rate, int out_rate, int nch); /* NULL: unsupported or out of memory */
void xfsrc_free(xf_src *s); /* NULL is fine */
/* Converts n_in frames into the fifo (the fifo must be empty); returns the frames now waiting. */
int xfsrc_fill(xf_src *s, const float *in, int n_in);
/* Plays the waiting frames, then the conversion of n_in frames, into out (cap frames); returns the frames written. */
int xfsrc_run(xf_src *s, const float *in, int n_in, float *out, int cap);

/* The kept output: ALSA stays open across an automatic track change while Crossfade is on (xf_uninit_player), so the
 * format Track A played in stays, and Track B's chain converts to it (peq_player.c). */
int xf_out_rate(int in_rate); /* the kept output's rate when this track must be converted to it, else 0 */
int xf_sticky(void); /* 1 while the open output is not Track B's native format */
void xf_note_fade(int on); /* xfade.c: a crossfade has started (1) or was abandoned (0) in the current track */
void xf_uninit_player(unsigned mask); /* stock's uninit_player (0x42def4) at the end-of-track cleanup */
void xf_reinit_chain(void); /* stock's reinit_audio_chain (0x42e680) after the gapless swap */
void xf_ao_pause(void); /* ao_alsa's pause slot: in a sticky session, plays out what is queued first */
void xf_ao_resume(void); /* ao_alsa's resume slot: after that pause, reopens in the track's own format */
int xf_ao_init(int rate, int channels, int format,
               int flags); /* ao_alsa's init slot: any real reopen is native again */
