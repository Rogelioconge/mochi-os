/* M1+ Music parametric EQ, the player's filter: hciplayer's equalizer, replaced (docs/modules/peq.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * After q2-pod's patch/peq_player.c (Copyright (c) 2026 Diamond Bond, MIT licence): the filter's control, play and uninit,
 * the DSD pass-through and the reload on stock's gain command are its.
 *
 * hciplayer is MPlayer 1.3.0 modified. tools/mod_player.py points the equalizer's af_info open slot (0x89381c, stock
 * 0x44fd14) at peq_open, so every instance the player makes of "equalizer" is this filter. Stock adds it (mcl-seteq,
 * then the playback loop's 0x4291cc, again at each file) while its Equalizer switch is on, and deletes it when the switch
 * goes off; peq_seteq_flag keeps it in the chain with the switch off (eq_off). 0x4291cc then sends GAIN SET (0x40001d00) for channels 0..7
 * with stock's ten gains (0xb10df4, dB): channel 0 rereads the state record (PEQ_STATE) and plays its curve, the file's
 * preset or the 10-Band EQ's gains and preamp (the record's, not stock's) as peaking bands, through the engine's 20 ms ramp. Control runs on the playback loop, never
 * in the PCM callback. The kill switch (PEQ_KILL, read at each open) passes everything through.
 *
 * Filter memory across a gapless join (the idea and the guards are q2-pod's, issue #137; the trigger is this player's):
 * every file gets a new instance (the old one's uninit, from uninit_player's acodec step, runs before the next one's open,
 * on the playback thread), and a cascade that starts from zero memory under a continuous signal clicks. An instance that
 * played to its demuxer's end leaves its settled memory in carry; the next instance adopts it on its first block when the
 * rate, the channel count and the whole curve match and the join is under CARRY_MS old. Anything else starts from zero.
 * The stereo stage is carried beside it under the same join guards, whatever the curve (its ramps go on in the next file).
 *
 * Mono Audio and Crossfeed (patch/stereo.c, docs/modules/stereo.md): Mono Audio runs before the cascade, Crossfeed after it,
 * as the record STEREO_FILE says (read at each REINIT and channel-0 gain command). With the switch off the filter
 * stays in the chain and, with both off, passes the native format and every block through (stock's bits).
 *
 * VU Meter Mode's level tap (patch/vu.c, docs/modules/vu.md): while demo's page wants it (VU_FILE exists), play measures each
 * block it sends on, after the stages in the float path and as it arrives in the native pass-through, and publishes the levels
 * with the time they are audible (now plus the audio output's delay). It only reads: no sample is written.
 */
#include "peq.h"
#include "stereo.h"
#include "vu.h"
#include "xfade.h"
#include "xfsrc.h"

_Static_assert(sizeof(af_data) == 24, "audio ABI");
_Static_assert(__builtin_offsetof(af_instance, setup) == 16, "setup ABI");
_Static_assert(__builtin_offsetof(af_instance, data) == 20, "data ABI");
_Static_assert(__builtin_offsetof(af_instance, mul) == 40, "multiplier ABI");

#define AF_CONTROL_REINIT 0x10000100
#define AF_CONTROL_COMMAND_LINE 0x20000300
#define AF_CONTROL_RESAMPLE_RATE_SET 0x40000100 /* arg: int * the rate the chain must end at; AF_OK takes it */
#define AF_CONTROL_EQ_GAIN_SET 0x40001d00
#define AF_CONTROL_EQ_GAIN_GET 0x40001d01
#define AF_OK 1
#define AF_FALSE 0
#define AF_UNKNOWN -1
#define AF_ERROR -2
#define AF_FORMAT_FLOAT 0x1d /* AF_FORMAT_FLOAT_NE: what the engine filters */

/* mpctx (0xaf9e30, as the rate gates read it: lw -0x61d0 from lui 0xb0), its sh_audio (+0x2c), the codec (+4) and
 * the codec's name (+0x3d0) and driver (+0x3e0), as "Selected audio codec" prints them (0x47ed70). The ten gains
 * mcl-seteq parses (0xb10df4) are no longer read (the 10-Band EQ plays the record's gains). Pinned by tools/mod_player.py. */
#define MPCTX (*(char *volatile *)0xaf9e30u)
#define AO_OFFSET \
    8 /* mpctx->audio_out: the ao driver's table (playing_audio_pts at 0x4300f4 reads it from here, 0x42686c) */
#define AO_GET_DELAY 0x1c /* its get_delay: float seconds queued in the output (0x430148, called at 0x430170) */
#define REMOVE_FILTER 0x42929cu /* stock's flag-0 removal of "equalizer" from the chain at mpctx + 0x40 */

typedef struct {
    peq_dsp dsp;
    stereo_dsp st;
    xfade_dsp xf;
    peq_preset preset;
    int off; /* the kill switch was there at the open: pass everything through */
    int fresh; /* REINIT done, no block yet: the first one may adopt the carried memory */
    int played; /* this instance has filtered a block */
    int ramp_in; /* it replaces a pass-through instance mid-track: Mono Audio and Crossfeed ramp in */
    int vu_native; /* the native pass-through blocks of this instance can be measured */
    int xf_native; /* the native pass-through blocks of this instance may crossfade */
    int in_rate, orate; /* the rate that arrives and the rate this instance sends on (the sticky output's) */
    int src_ok; /* it may take the chain's rate request (float path, 1 or 2 channels) */
    int want; /* the rate the chain asked for (AF_CONTROL_RESAMPLE_RATE_SET, accepted) */
    xf_src *src; /* converts in_rate to orate; created at the first block or adopted from the last file */
    float *obuf; /* the converted block */
    int ocap; /* its capacity in frames */
} player_state;

/* The memory of the instance that just ended, in the payload's .data (no .bss here; one writer: the playback thread). */
#define CARRY_MS 3000 /* older than this (a stop, a pause, the album's end) would only ring into an unrelated start */
static struct {
    double z[PEQ_CHANNELS][PEQ_BANDS][2];
    peq_preset preset;
    stereo_carry st_mem;
    xfade_carry xf_mem;
    xf_src *src; /* the converter that went on from the last file (Track B's, or the last file's own) */
    long long at; /* ms, CLOCK_MONOTONIC, when it was left */
    int rate, channels, valid;
    int eq, st,
        xf; /* which of the three was left: the cascade's memory, the stereo stage, a partial crossfade fade-in */
} carry __attribute__((section(".data")));

static long long now_ms(void) {
    struct {
        int sec, nsec;
    } ts;
    return clock_gettime(1, &ts) ? -1 : (long long)ts.sec * 1000 + ts.nsec / 1000000;
}

/* mpctx->d_audio (+0x34)->eof (+0x1c): the demuxer reached the file's end (MPlayer's ds->eof), not a skip or a stop. */
static int track_ended(void) {
    char *mp = MPCTX, *ds = mp ? *(char **)(mp + 0x34) : 0;
    return ds && *(volatile int *)(ds + 0x1c);
}

/* Nothing carries: the converter goes too. */
static void carry_drop(void) {
    xfsrc_free(carry.src);
    carry.src = 0;
    carry.valid = 0;
    carry.eq = carry.st = carry.xf = 0;
}

/* An instance that filtered at least one block is going away: keep its memory if it played its track out, in a settled
 * curve, with finite state; otherwise drop what an earlier one left (the stream has moved on). */
static void leave(player_state *s) {
    if (!s->played) return;
    carry_drop();
    long long t = now_ms();
    if (s->off || t < 0 || !track_ended()) return;
    carry.xf = xfade_carry_out(&s->xf, &carry.xf_mem);
    carry.src = xfade_take_src(&s->xf); /* Track B's: the join's own converter */
    if (!carry.src) {
        carry.src = s->src;
        s->src = 0;
    }
    if (s->dsp.channels) {
        carry.eq = !s->dsp.current.bypass && !s->dsp.ramp && !s->dsp.waiting;
        for (int ch = 0; ch < PEQ_CHANNELS; ++ch)
            for (int b = 0; b < PEQ_BANDS; ++b)
                for (int k = 0; k < 2; ++k)
                    if (!__builtin_isfinite(s->dsp.current.z[ch][b][k])) carry.eq = 0;
        if (carry.eq) {
            memcpy(carry.z, s->dsp.current.z, sizeof carry.z);
            carry.preset = s->preset;
        }
        carry.st = stereo_carry_out(&s->st, &carry.st_mem);
        carry.rate = s->dsp.rate;
        carry.channels = s->dsp.channels;
    } else {
        carry.rate = 0;
        carry.channels = 0;
    }
    carry.at = t;
    carry.valid = carry.eq || carry.st || carry.xf || carry.src;
    if (carry.src) {
    }
}

/* The join guards: what was left is this stream's, a moment ago. */
static int joins(int rate, int channels) {
    long long t = now_ms();
    return carry.valid && t >= carry.at && t - carry.at < CARRY_MS && carry.rate == rate && carry.channels == channels;
}

/* The first block of a new instance: one try, and the memory is gone either way. The cascade's needs the same curve;
 * the stereo stage's does not; a partial crossfade fade-in carries across rate/channel changes too. */
static void adopt(player_state *s) {
    long long t = now_ms();
    int recent = carry.valid && t >= carry.at && t - carry.at < CARRY_MS;
    int same = recent && s->dsp.channels && carry.rate == s->dsp.rate && carry.channels == s->dsp.channels;
    xf_src *src = carry.src;
    carry.src = 0;
    carry.valid = 0;
    /* The converter goes on only into a track that arrives in the same format and ends in the same rate. */
    if (src && recent && s->orate != s->in_rate && !s->src && src->in_rate == s->in_rate && src->out_rate == s->orate &&
        src->nch == s->dsp.channels) {
        s->src = src;
    } else
        xfsrc_free(src);
    if (!recent) return;
    if (carry.xf) xfade_carry_in(&s->xf, &carry.xf_mem);
    if (!same) return;
    if (carry.eq && !s->dsp.current.bypass && !s->dsp.waiting &&
        !memcmp(&carry.preset, &s->preset, sizeof carry.preset))
        memcpy(s->dsp.current.z, carry.z, sizeof carry.z);
    if (carry.st) stereo_carry_in(&s->st, &carry.st_mem);
}

/* Stock's Equalizer switch, as the last mcl-seteq said (peq_seteq_flag): 1 off. */
static int eq_off __attribute__((section(".data")));
/* The live instance passes the native format through because the switch is off and no stereo option is on. */
static int pass_native __attribute__((section(".data")));
/* peq_seteq_flag removed that instance while the music plays: the one the loop adds next starts its stereo stage from the
 * untouched signal (peq_open takes this). */
static int replaced __attribute__((section(".data")));

/* DSD (the vendor's dsdiff driver: dsf, dff, SACD iso; or FFmpeg's ffdsd*) reaches the chain as integer PCM,
 * possibly DoP, whose bits must arrive unchanged: pass it through. */
static int dsd(void) {
    char *mp = MPCTX, *sh = mp ? *(char **)(mp + 0x2c) : 0, *codec = sh ? *(char **)(sh + 4) : 0;
    if (!codec) return 0;
    const char *name = *(char **)(codec + 0x3d0), *drv = *(char **)(codec + 0x3e0);
    return (drv && !strcmp(drv, "dsdiff")) || (name && strlen(name) >= 5 && !memcmp(name, "ffdsd", 5));
}

/* The audio output's delay in us: what is queued ahead of the block being filtered (0 when the output is not reachable). */
static int ao_delay_us(void) {
    char *mp = MPCTX, *ao = mp ? *(char **)(mp + AO_OFFSET) : 0;
    float (*get_delay)(void) = ao ? *(float (**)(void))(ao + AO_GET_DELAY) : 0;
    if (!get_delay) return 0;
    float d = get_delay();
    return d > 0 && d < 10 ? (int)(d * 1000000) : 0; /* a NaN or a wild value is none */
}

/* The level tap: one open per block, and only when wanted do the delay and the measuring cost anything. */
static void tap(const af_data *d) {
    void *f = vu_open();
    if (f)
        vu_block(f, d->audio, d->format, d->bps, d->nch, d->rate, (unsigned)d->len / (unsigned)(d->bps * d->nch),
                 ao_delay_us());
}

/* What plays: the record's preset (PEQ_FILE), or the 10-Band EQ's ten gains and preamp (none readable: Flat, Auto). */
static void effective(peq_preset *p) {
    peq_state s;
    if (peq_state_load(&s) && s.mode == PEQ_FILE)
        *p = s.preset;
    else
        peq_tenband(p, s.gain, s.preamp);
    if (eq_off) p->bypass = 1; /* stock's switch is off: no curve (the engine ramps in and out of bypass) */
}

static int control(af_instance *af, int command, void *arg) {
    player_state *s = af->setup;
    if (command == AF_CONTROL_REINIT) {
        af_data *in = arg;
        if (!in || in->nch < 1 || in->nch > PEQ_CHANNELS) return AF_ERROR;
        int irate = in->rate;
        xfsrc_free(s->src);
        s->src = 0;
        xfade_release(&s->xf);
        *af->data = *in;
        pass_native = 0;
        s->vu_native = 0;
        s->xf_native = 0;
        memset(&s->xf, 0, sizeof s->xf);
        s->in_rate = s->orate = irate;
        s->src_ok = 0;
        af->mul = 1;
        if (s->off || in->rate < 8000 || in->rate > 384000 || (in->format & ~63) || dsd()) {
            s->dsp.channels = 0; /* play leaves every block alone */
            carry_drop(); /* nothing carries through a pass-through track */
            if (!s->off) vu_note(0, 0); /* no levels: DSD, a special format, a rate out of range */
            return AF_OK;
        }
        /* The sticky output (patch/xfsrc.c): when the chain asked for the open output's rate and this instance took it
         * (control below), the conversion is this filter's, and everything after it runs at the output rate. */
        s->src_ok = in->nch <= 2;
        /* A request taken while the output was kept is over with the session (pause, patch/xfsrc.c). */
        if (!xf_sticky()) s->want = 0;
        int kept = s->src_ok ? xf_out_rate(irate) : 0;
        int orate = kept ? kept : s->want && s->want != irate && s->src_ok ? s->want : irate;
        s->orate = af->data->rate = orate;
        af->mul = (double)orate / (double)irate;
        stereo_record rec;
        stereo_load(&rec);
        /* Switch off and no stereo option: the filter only sits in the chain and stock's bits go through. Not while the
         * last file's stage would still be heard (an option switched off just before its end): this file filters, to
         * finish that fade, and then leaves every sample alone. */
        int fading = joins(orate, in->nch) && carry.st && stereo_carry_live(&carry.st_mem, orate);
        if (eq_off && !(in->nch == 2 && stereo_on(&rec)) && !fading && orate == irate) {
            s->dsp.channels = 0;
            if (!carry.xf) carry_drop();
            pass_native = 1;
            s->vu_native = vu_supported(in->format, in->bps) && in->rate > 0;
            s->xf_native = s->vu_native && in->nch <= 2;
            if (s->xf_native) xfade_reset(&s->xf, in->rate, in->nch, in->format, in->bps);
            s->fresh = 1;
            vu_note(s->vu_native ? in->rate : 0, in->nch);
            return AF_OK;
        }
        effective(&s->preset);
        peq_reset(&s->dsp, orate, in->nch, &s->preset);
        stereo_reset(&s->st, orate, in->nch, &rec, s->ramp_in && !s->played);
        xfade_reset(&s->xf, orate, in->nch, AF_FORMAT_FLOAT, 4);
        s->fresh = 1;
        af->data->format = AF_FORMAT_FLOAT;
        af->data->bps = 4;
        vu_note(orate, in->nch);
        if (in->format != AF_FORMAT_FLOAT || in->bps != 4) {
            *in = *af->data; /* ask the chain for float, at the rate that arrives */
            in->rate = irate;
            return AF_FALSE;
        }
        return AF_OK;
    }
    if (command == AF_CONTROL_EQ_GAIN_SET || command == AF_CONTROL_EQ_GAIN_GET) {
        struct {
            float *gain;
            int channel;
        } *ext = arg;
        if (!ext || !ext->gain || ext->channel < 0 || ext->channel >= PEQ_CHANNELS) return AF_ERROR;
        if (command == AF_CONTROL_EQ_GAIN_GET) {
            memset(ext->gain, 0, PEQ_TENBAND * sizeof(float));
        } else if (!ext->channel && !s->off && s->dsp.channels) {
            peq_preset p;
            effective(&p);
            if (memcmp(&p, &s->preset, sizeof(p)) && peq_update(&s->dsp, &p)) s->preset = p;
            stereo_record rec;
            stereo_load(&rec);
            stereo_update(&s->st, &rec);
        }
        return AF_OK;
    }
    if (command == AF_CONTROL_COMMAND_LINE) return AF_OK;
    if (command == AF_CONTROL_RESAMPLE_RATE_SET) {
        /* hciplayer's rate negotiation (0x44c710) asks the chain's filters, last to first, before it inserts a resampler.
         * Only while the kept output format differs from the track's: otherwise stock's own conversion. */
        int rate = arg ? *(int *)arg : 0;
        int ok = xf_sticky() && s->src_ok && rate >= 8000 && rate <= 384000 && rate != s->in_rate;
        if (!ok) return AF_UNKNOWN;
        s->want = rate;
        return AF_OK;
    }
    return AF_UNKNOWN;
}

/* The conversion to the open output's rate (this instance's own, after the chain asked for it): the converter's waiting
 * frames, then this block's, in one buffer, sent on as the instance's output (a different frame count, as af_resample's).
 * Its delay (the filter's half length, 8 frames at XF_SRC_FILTER_SIZE 16) is under 1 ms: not reported. */
static af_data *convert(af_instance *af, player_state *s, af_data *data) {
    af_data *d = af->data;
    int nch = data->nch;
    if (!s->src) s->src = xfsrc_new(s->in_rate, s->orate, nch);
    d->len = 0;
    if (!s->src) return d; /* out of memory: this block is dropped */
    int n_in = data->len / (4 * nch);
    int need = (int)((double)n_in * s->orate / s->in_rate) + s->src->count + 64;
    if (need > s->ocap) {
        float *o = calloc((unsigned)(need * nch), sizeof(float));
        if (!o) return d;
        free(s->obuf);
        s->obuf = o;
        s->ocap = need;
    }
    int n = xfsrc_run(s->src, data->audio, n_in, s->obuf, s->ocap);
    /* Every field, every block: the filters after this one (af_format) rewrite the af_data they are handed, which is
     * this instance's own; a format left at their S32 would make the next block's floats pass as integers (static). */
    d->audio = s->obuf;
    d->len = n * 4 * nch;
    d->rate = s->orate;
    d->nch = nch;
    d->format = AF_FORMAT_FLOAT;
    d->bps = 4;
    return d;
}

static af_data *play(af_instance *af, af_data *data) {
    player_state *s = af->setup;
    if (s->orate != s->in_rate && data && data->len > 0 && data->format == AF_FORMAT_FLOAT && data->bps == 4 &&
        data->nch == s->dsp.channels && data->rate == s->in_rate && !(data->len % (4 * data->nch))) {
        if (s->fresh) {
            s->fresh = 0;
            adopt(s);
        }
        data = convert(af, s, data);
    }
    if (data && data->len > 0 && data->format == AF_FORMAT_FLOAT && data->bps == 4 && data->nch == s->dsp.channels &&
        data->rate == s->dsp.rate && !(data->len % (4 * data->nch))) {
        if (s->fresh) {
            s->fresh = 0;
            adopt(s);
        }
        s->played = 1;
        unsigned frames = (unsigned)data->len / (4 * data->nch);
        xfade_process_float(&s->xf, data->audio, frames);
        stereo_pre(&s->st, data->audio, frames);
        peq_process(&s->dsp, data->audio, frames);
        stereo_post(&s->st, data->audio, frames);
        tap(data);
    } else if ((s->vu_native || s->xf_native) && !s->dsp.channels && data && data->len > 0 &&
               data->format == af->data->format && data->bps == af->data->bps && data->nch == af->data->nch &&
               data->rate == af->data->rate && !(data->len % (data->bps * data->nch))) {
        if (s->fresh) {
            s->fresh = 0;
            adopt(s);
        }
        s->played = 1;
        unsigned frames = (unsigned)data->len / (unsigned)(data->bps * data->nch);
        if (s->xf_native) xfade_process_native(&s->xf, data->audio, frames);
        if (s->vu_native) tap(data); /* the native pass-through: read, never written (unless crossfade active) */
    }
    return data;
}

static void uninit(af_instance *af) {
    pass_native = 0;
    if (af->setup) {
        player_state *s = af->setup;
        leave(s);
        xfsrc_free(s->src);
        xfade_release(&s->xf);
        free(s->obuf);
    }
    free(af->data);
    free(af->setup);
    af->data = 0;
    af->setup = 0;
}

int peq_open(af_instance *af) {
    af->control = control;
    af->uninit = uninit;
    af->play = play;
    af->mul = 1;
    af->delay = 0;
    af->data = calloc(1, sizeof(af_data));
    af->setup = calloc(1, sizeof(player_state));
    if (!af->data || !af->setup) return AF_ERROR; /* af_create calls uninit on failure */
    ((player_state *)af->setup)->ramp_in = replaced;
    replaced = 0;
    void *kill = fopen(PEQ_KILL, "rb");
    if (kill) {
        ((player_state *)af->setup)->off = 1;
        fclose(kill);
    }
    return AF_OK;
}

/* mcl-seteq's flag, where hciplayer parses it (strtol at 0x42cd1c, tools/mod_player.py): the answer is the flag, except
 * that off (anything but 1 and 2) is answered as 2. Stock then takes its "on" path for it: the filter stays in the chain
 * and the playback loop adds it again at each file. The filter itself knows the switch is off (eq_off). Switching on while
 * the filter passes the native format through would leave it unable to filter until the next file, so that one instance
 * is removed (as stock's flag 0 removed it) and the loop adds a new one; so would Mono Audio or Crossfeed going on with the
 * switch off (demo writes the record, then sends mcl-seteq). The kill switch leaves stock's answer. */
int peq_seteq_flag(const char *text, char **end, int base) {
    int flag = (int)strtol(text, end, base), off = flag != 1 && flag != 2;
    int was = eq_off, passing = pass_native;
    eq_off = off;
    void *kill = fopen(PEQ_KILL, "rb");
    if (kill) {
        fclose(kill);
        return flag;
    }
    stereo_record rec;
    stereo_load(&rec);
    if (passing && (off ? stereo_on(&rec) : was)) {
        char *mp = MPCTX;
        if (mp) {
            replaced = 1;
            ((void (*)(void *))REMOVE_FILTER)(mp + 0x40);
        }
    }
    return off ? 2 : flag;
}
