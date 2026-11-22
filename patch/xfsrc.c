/* M1+ Music Crossfade: sample-rate conversion on hciplayer's libswresample, and the sticky output format
 * (docs/modules/crossfade.md, patch/xfsrc.h).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "xfsrc.h"
#include "xfade.h"

/* libswresample as hciplayer links it (tools/mod_player.py PINS checks each prologue). */
#define SWR_ALLOC_SET_OPTS \
    0x7235bcu /* (s, i64 out_layout, out_fmt, out_rate, i64 in_layout, in_fmt, in_rate, log_off, log_ctx) */
#define SWR_INIT 0x41e32cu /* int (s) */
#define SWR_CONVERT 0x724b40u /* int (s, uint8_t **out, out_count, const uint8_t **in, in_count) */
#define SWR_FREE 0x41e2d0u /* void (SwrContext **) */
#define AV_OPT_SET_INT 0x6f9770u /* int (obj, name, i64 value, flags) */
#define AV_SAMPLE_FMT_FLT 3
#define AV_CH_LAYOUT_MONO 4LL
#define AV_CH_LAYOUT_STEREO 3LL

typedef long long i64;

static void opt_int(void *swr, const char *name, int v) {
    ((int (*)(void *, const char *, i64, int))AV_OPT_SET_INT)(swr, name, v, 0);
}

static void swr_drop(void *swr) { ((void (*)(void **))SWR_FREE)(&swr); }

xf_src *xfsrc_new(int in_rate, int out_rate, int nch) {
    if (nch < 1 || nch > 2 || in_rate < 8000 || in_rate > 384000 || out_rate < 8000 || out_rate > 384000) return 0;
    i64 layout = nch == 1 ? AV_CH_LAYOUT_MONO : AV_CH_LAYOUT_STEREO;
    void *swr = ((void *(*)(void *, i64, int, int, i64, int, int, int, void *))SWR_ALLOC_SET_OPTS)(
        0, layout, AV_SAMPLE_FMT_FLT, out_rate, layout, AV_SAMPLE_FMT_FLT, in_rate, 0, 0);
    int ok = 0;
    if (swr) {
        opt_int(swr, "filter_size", XF_SRC_FILTER_SIZE);
        opt_int(swr, "linear_interp", XF_SRC_LINEAR);
        ok = ((int (*)(void *))SWR_INIT)(swr) >= 0;
    }
    xf_src *s = ok ? calloc(1, sizeof *s) : 0;
    if (s) {
        s->cap = (int)((double)XF_SRC_CHUNK * out_rate / in_rate) + XF_SRC_CHUNK + 8;
        s->fifo = calloc((unsigned)(s->cap * nch), sizeof(float));
        s->swr = swr;
        s->in_rate = in_rate;
        s->out_rate = out_rate;
        s->nch = nch;
        if (!s->fifo) {
            free(s);
            s = 0;
        }
    }
    if (!s && swr) swr_drop(swr);
    return s;
}

void xfsrc_free(xf_src *s) {
    if (!s) return;
    swr_drop(s->swr);
    free(s->fifo);
    free(s);
}

int xfsrc_fill(xf_src *s, const float *in, int n_in) {
    s->head = s->count = 0;
    const unsigned char *ip[1] = {(const unsigned char *)in};
    unsigned char *op[1] = {(unsigned char *)s->fifo};
    int r = ((int (*)(void *, unsigned char **, int, const unsigned char **, int))SWR_CONVERT)(s->swr, op, s->cap, ip,
                                                                                               n_in);
    s->count = r > 0 ? r : 0;
    return s->count;
}

int xfsrc_run(xf_src *s, const float *in, int n_in, float *out, int cap) {
    int n = s->count < cap ? s->count : cap, nch = s->nch;
    for (int i = 0; i < n * nch; ++i) out[i] = s->fifo[s->head * nch + i];
    s->head += n;
    s->count -= n;
    if (!s->count) s->head = 0;
    if (n_in > 0 && cap > n) {
        const unsigned char *ip[1] = {(const unsigned char *)in};
        unsigned char *op[1] = {(unsigned char *)(out + n * nch)};
        int r = ((int (*)(void *, unsigned char **, int, const unsigned char **, int))SWR_CONVERT)(s->swr, op, cap - n,
                                                                                                   ip, n_in);
        if (r > 0) n += r;
    }
    return n;
}

/* ---- the sticky output format ---------------------------------------------------------------------------------------
 * hciplayer's end-of-track cleanup (0x4217d8) calls uninit_player(0xff7a ...): the mask includes 0x2, the audio output,
 * so ALSA is closed and reopened at the next track's native format (about 16 ms when it is the same, 180-530 ms when the
 * rate or the format changes). While Crossfade is on, an automatic change drops that bit and keeps ALSA open. */
#define PLAYER_FLAGS (*(volatile unsigned *)0xb10e70u) /* 0x2: the audio output is initialized */
#define GAPLESS_SW (*(volatile int *)0xb10e40u) /* 1: stock's gapless swap runs at the loop head */
#define NEXT_STATE (*(volatile int *)0xb10dd0u)
#define NEXT_MPCTX ((char *)0xaf9b90u)
#define MPCTX (*(char *volatile *)0xaf9e30u)
#define AO_RATE (*(volatile int *)0xafa1a0u)
#define AO_CH (*(volatile int *)0xafa1a4u)
#define AO_FMT (*(volatile int *)0xafa1a8u)
#define UNINIT_PLAYER 0x42def4u
#define REINIT_AUDIO_CHAIN 0x42e680u
#define SH_AFILTER 0x84 /* sh_audio->afilter (af_stream_t *) */
#define PF_AO 2u
#define MP_EOF 0x14 /* mpctx->eof: 1 = the track ended (an automatic change), 4 = skipped */
#define MP_AUDIO_OUT 8 /* mpctx->audio_out: the swap copies next_mpctx over mpctx, so next_mpctx carries it */
#define SH_A_OUT 0x78 /* sh_audio->a_out_buffer: filtered audio not yet written to the output */
#define SH_A_OUT_LEN 0x7c
#define AO_PLAY 6 /* ao_functions_t slot (+0x18): int play(void *data, int len, int flags) */
#define AOPLAY_FINAL_CHUNK 1
#define AO_GET_SPACE 5 /* ao_functions_t slot (+0x14): int get_space(void), bytes free in the output's buffer */
#define AO_BUFFERSIZE (*(volatile int *)0xafa1b4u) /* ao_data.buffersize: get_space's value when nothing is queued */
#define AO_PAUSE 0x438224u /* ao_alsa's pause and resume (void (void)) */
#define AO_RESUME 0x4384acu
#define AO_INIT 0x438648u /* stock ao_alsa init */
#define USEC_SLEEP 0x4a4730u /* stock's usec_sleep(int) */

static struct {
    int sticky, faded, unstick;
} xfs __attribute__((section(".data")));

int xf_sticky(void) { return xfs.sticky; }

/* For demo's info page (XFOUT_FILE): the rate the output is kept at, 0 when it is a track's own again. The file is
 * made by the first sticky session; without one this is a single open that finds nothing. */
static void tell_out(int rate) {
    void *f = fopen(XFOUT_FILE, "r+b");
    if (!f && rate) f = fopen(XFOUT_FILE, "wb");
    if (!f) return;
    xfout_record r = {XFOUT_MAGIC, rate};
    fwrite(&r, 1, sizeof r, f);
    fclose(f);
}

void xf_note_fade(int on) { xfs.faded = on; }

enum { R_STOCK, R_NO_SWAP, R_OFF, R_NATIVE, R_SAME, R_STICKY, R_FADED, R_NO_AO, R_RAW };

/* DSD (the filter's own test, patch/peq_player.c): its output mode is not PCM's, so the output is never kept across it. */
static int is_dsd(const char *sh) {
    const char *codec = sh ? *(char **)(sh + 4) : 0;
    if (!codec) return 0;
    const char *name = *(char **)(codec + 0x3d0), *drv = *(char **)(codec + 0x3e0);
    return (drv && !strcmp(drv, "dsdiff")) || (name && strlen(name) >= 5 && !memcmp(name, "ffdsd", 5));
}

/* Track A's filtered audio that stock has not written yet. ao_alsa's play writes whole 4096-byte bursts and
 * fill_audio_out_buffers (0x42f6ec) keeps the rest in sh_audio->a_out_buffer for the next call; uninit_player frees it.
 * At a natural end stock drains it first (the final-chunk flag, 0x42f83c), but the crossfade ends Track A by setting
 * mpctx->eof itself, so a few milliseconds would be dropped. They are already Track B's audio, and B's own chain
 * continues right after them: with the output kept open the hole is a tick. Write them out as stock would. The
 * driver's write blocks until the output took everything; a short count (an interrupted or recovered write) is followed
 * by the rest, a few times at most, and an error ends it. */
static void flush_tail(char *mp) {
    char *sh = *(char **)(mp + 0x2c);
    void **ao = *(void ***)(mp + MP_AUDIO_OUT);
    char *buf = sh ? *(char **)(sh + SH_A_OUT) : 0;
    int left = buf ? *(int *)(sh + SH_A_OUT_LEN) : 0, done = 0, i;
    for (i = 0; i < 8 && done < left; ++i) {
        int r = ((int (*)(void *, int, int))ao[AO_PLAY])(buf + done, left - done, AOPLAY_FINAL_CHUNK);
        if (r <= 0 || r > left - done) break;
        done += r;
    }
    if (left > 0) *(int *)(sh + SH_A_OUT_LEN) = 0;
}

void xf_uninit_player(unsigned mask) {
    char *mp = MPCTX, *sh = *(char **)(NEXT_MPCTX + 0x2c);
    int eof = mp ? *(volatile int *)(mp + MP_EOF) : 0, faded = xfs.faded, why = R_STOCK;
    int brate = sh ? *(int *)(sh + 0x3c) : 0, bch = sh ? *(int *)(sh + 0x44) : 0, bfmt = sh ? *(int *)(sh + 0x38) : 0;
    unsigned out = mask;
    xfs.faded = 0;
    if (eof != 1) {
        why = R_STOCK; /* a skip, a stop or an error: stock reopens at the next file's native format */
    } else if (!(mask & PF_AO) || !(PLAYER_FLAGS & PF_AO) || !mp || *(void **)(mp + MP_AUDIO_OUT) == 0 ||
               AO_RATE <= 0) {
        why = R_NO_AO;
    } else if (NEXT_STATE != 2 || GAPLESS_SW != 1 || !sh) {
        why = R_NO_SWAP;
    } else {
        /* Crossfade has a part in this join: it faded, or was going to, or (in a session whose output is already kept in
         * another format) it is a join of two music tracks that stays gapless, a same-album one. The record's keep is 0
         * for everything crossfade stays out of (podcasts, audiobooks, streams, CUE tracks: patch/xfadeset.c). */
        xfade_record r;
        int rec = xfade_load(&r);
        int on = faded || (rec && (r.seconds > 0 || (r.keep && xfs.sticky)));
        int same = brate == AO_RATE && bch == AO_CH && bfmt == AO_FMT;
        /* Keeping another format needs Track B's filter to convert it: the cases its REINIT filters (peq_player.c). */
        int pcm = !is_dsd(*(char **)(mp + 0x2c)) && !is_dsd(sh);
        int conv = pcm && brate >= 8000 && brate <= 384000 && bch >= 1 && bch <= 2 && !(bfmt & ~63);
        if (!on)
            why = R_OFF;
        else if (same ? !pcm : !conv)
            why = R_RAW;
        else if (xfs.sticky)
            why = R_STICKY;
        else if (faded)
            why = R_FADED;
        else if (same)
            why = R_SAME;
        else
            why = R_NATIVE;
        if (why == R_STICKY || why == R_FADED || why == R_SAME) {
            out = mask & ~PF_AO;
            xfs.sticky = !same;
            tell_out(same ? 0 : AO_RATE);
            *(void **)(NEXT_MPCTX + MP_AUDIO_OUT) = *(void **)(mp + MP_AUDIO_OUT);
        }
    }
    if (out != mask) flush_tail(mp);
    ((void (*)(unsigned))UNINIT_PLAYER)(out);
}

/* The swap's reinit_audio_chain (0x421cec). With the output kept open, stock takes its open-output path, which sends
 * af_control_any_rev to sh_audio->afilter before init_audio_filters allocates one; a preloaded Track B has none yet
 * (stock never kept the output across a swap), so that path read address 4. Allocate the empty stream here exactly as
 * init_audio_filters would (calloc(0x40, 1), 0x47f098). */
void xf_reinit_chain(void) {
    char *mp = MPCTX, *sh = mp ? *(char **)(mp + 0x2c) : 0;
    int kept = sh && (PLAYER_FLAGS & PF_AO);
    if (kept && !*(void **)(sh + SH_AFILTER)) *(void **)(sh + SH_AFILTER) = calloc(0x40, 1);
    /* The chain is built before this filter is inserted, so it cannot answer the rate request then and stock would add
     * its own resampler (a fresh one: the join's converter and its waiting frames would be lost, a click). Build it at
     * the track's own rate instead; init_audio_filters writes the chain's format back into ao_data, so the open output's
     * is restored after, and this filter converts to it (xf_out_rate). */
    int rate = AO_RATE, ch = AO_CH, fmt = AO_FMT, own = sh ? *(int *)(sh + 0x3c) : 0;
    int native = kept && xfs.sticky && own > 0 && own != rate;
    if (native) AO_RATE = own;
    ((void (*)(void))REINIT_AUDIO_CHAIN)();
    if (native && (PLAYER_FLAGS & PF_AO)) {
        AO_RATE = rate;
        AO_CH = ch;
        AO_FMT = fmt;
        /* The chain's target (af_stream output.rate, +0x28) too: af_add's output check (0x44c37c) compares the last
         * filter's rate with it, and would drop this filter (which ends at the output's rate) as a mismatch. */
        char *af = *(char **)(sh + SH_AFILTER);
        if (af) *(int *)(af + 0x28) = rate;
    }
}

int xf_out_rate(int in_rate) {
    int r = AO_RATE;
    return xfs.sticky && (PLAYER_FLAGS & PF_AO) && r >= 8000 && r <= 384000 && r != in_rate ? r : 0;
}

/* Pause ends a sticky session: playback continues in the track's own format. The reopen drops what the output has
 * queued, so pause first lets that play out (the tail stock has not written yet, then up to the buffer's length: about
 * 0.2 s at 96 kHz, 0.4 s at 44.1 kHz); nothing is lost. Not while a crossfade is running: both tracks are being mixed in
 * the open format. */
void xf_ao_pause(void) {
    char *mp = MPCTX;
    xfs.unstick = 0;
    if (xfs.sticky && !xfs.faded && mp && *(void **)(mp + 0x2c) && *(void **)(mp + MP_AUDIO_OUT) &&
        (PLAYER_FLAGS & PF_AO)) {
        void **ao = *(void ***)(mp + MP_AUDIO_OUT);
        flush_tail(mp);
        int i = 0;
        while (i < 100 && ((int (*)(void))ao[AO_GET_SPACE])() < AO_BUFFERSIZE) {
            ((void (*)(int))USEC_SLEEP)(5000);
            ++i;
        }
        xfs.unstick = 1;
    }
    ((void (*)(void))AO_PAUSE)();
}

/* The resume after it: close the output and rebuild the chain, as stock's own pause loop does when the output device
 * changed while paused (0x430084: uninit_player(2), reinit_audio_chain, then the driver's resume). The output opens at
 * the track's format (xf_ao_init ends the session), and this filter stops converting (xf_out_rate). */
void xf_ao_resume(void) {
    char *mp = MPCTX;
    int go = xfs.unstick && xfs.sticky && mp && *(void **)(mp + 0x2c) && (PLAYER_FLAGS & PF_AO);
    xfs.unstick = 0;
    if (go) {
        xfs.sticky = 0;
        ((void (*)(unsigned))UNINIT_PLAYER)(PF_AO);
        ((void (*)(void))REINIT_AUDIO_CHAIN)();
        mp = MPCTX;
        if (!mp || !*(void **)(mp + MP_AUDIO_OUT)) return; /* the reopen failed: stock has torn the audio down */
    }
    ((void (*)(void))AO_RESUME)();
}

int xf_ao_init(int rate, int channels, int format, int flags) {
    xfs.sticky = 0;
    xfs.unstick = 0;
    tell_out(0);
    return ((int (*)(int, int, int, int))AO_INIT)(rate, channels, format, flags);
}
