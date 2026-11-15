/* M1+ Music Mono Audio and Crossfeed, the player's stereo stage (docs/modules/stereo.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The crossfeed is Boris Mikhaylov's bs2b (libbs2b 3.1.0, Copyright (c) 2005 Boris Mikhaylov, MIT licence): each channel
 * gets the other channel low-passed and attenuated, its own highs boosted, the sum scaled back; the one-pole designs, the
 * level arithmetic and the three settings (his "jmeier", "cmoy" and default) are his. Here it works on float blocks in
 * double, with weights that move in 20 ms so a change does not click. No exp or log10 is imported: exp(x) is pow(e, x),
 * and 2^(-20 log10(G) / 12) is G^(-20 log10(2) / 12).
 *
 * Built with PEQ_PLAYER into hciplayer's payload (no .bss: patch/peq_player.c keeps the state in player_state).
 */
#include "stereo.h"

#define E 2.718281828459045
#define TWO_PI 6.283185307179586
#define MIN_RATE 8000
#define MAX_RATE 384000

/* bs2b's Fc_lo (Hz) and feed level (tenths of dB) per setting: Low jmeier 650 / 9.5, Medium cmoy 700 / 6.0, High default 700 / 4.5 */
static const int fcut[STEREO_LEVELS] = {0, 650, 700, 700}, feed[STEREO_LEVELS] = {0, 95, 60, 45};

int stereo_load(stereo_record *r) {
    stereo_record f;
    char extra;
    memset(r, 0, sizeof(*r));
    void *h = fopen(STEREO_FILE, "rb");
    if (!h) return 0;
    memset(&f, 0, sizeof(f));
    int ok = fread(&f, 1, sizeof(f), h) == sizeof(f) && fread(&extra, 1, 1, h) == 0;
    if (fclose(h)) ok = 0;
    for (unsigned i = 0; i < 8; ++i) ok = ok && f.magic[i] == STEREO_MAGIC[i];
    if (!ok || (f.mono != 0 && f.mono != 1) || f.crossfeed < STEREO_OFF || f.crossfeed >= STEREO_LEVELS) return 0;
    *r = f;
    return 1;
}

int stereo_on(const stereo_record *r) { return r->mono || r->crossfeed; }

/* libbs2b init(): the low-pass (gain G_lo, corner Fc), the high boost (corner Fc_hi) and the output gain. */
static void design(sx_coef *c, int level, int rate) {
    double lvl = feed[level] / 10.0, GB_lo = lvl * -5.0 / 6.0 - 3.0, GB_hi = lvl / 6.0 - 3.0;
    double G_lo = pow(10, GB_lo / 20.0), G_hi = 1.0 - pow(10, GB_hi / 20.0);
    double Fc_hi = fcut[level] * pow(2.0, GB_lo / 12.0) * pow(G_hi, -0.50171665943996);
    double x = pow(E, -TWO_PI * fcut[level] / rate);
    c->b1lo = x;
    c->a0lo = G_lo * (1.0 - x);
    x = pow(E, -TWO_PI * Fc_hi / rate);
    c->b1hi = x;
    c->a0hi = 1.0 - G_hi * (1.0 - x);
    c->a1hi = -x;
    c->gain = 1.0 / (1.0 - G_hi + G_lo);
}

static void put(stereo_dsp *s, int k, int level, double w) {
    sx_slot *q = &s->slot[k];
    memset(q, 0, sizeof(*q));
    q->level = level;
    q->w = w;
    design(&q->c, level, s->rate);
}

void stereo_reset(stereo_dsp *s, int rate, int channels, const stereo_record *r, int ramp) {
    memset(s, 0, sizeof(*s));
    s->rate = rate;
    s->active = channels == 2 && rate >= MIN_RATE && rate <= MAX_RATE;
    s->step = 50.0 / rate; /* 20 ms */
    s->mono_to = s->active ? r->mono : 0; /* one channel or more than two: nothing */
    s->level_to = s->active ? r->crossfeed : 0;
    s->mono_w = ramp ? 0 : s->mono_to;
    if (s->level_to) put(s, 0, s->level_to, ramp ? 0 : 1);
}

void stereo_update(stereo_dsp *s, const stereo_record *r) {
    s->mono_to = s->active ? r->mono : 0;
    s->level_to = s->active ? r->crossfeed : 0;
}

static double toward(double w, double to, double step) {
    return w < to ? (w + step < to ? w + step : to) : (w - step > to ? w - step : to);
}

void stereo_pre(stereo_dsp *s, float *audio, unsigned frames) {
    if (!audio || !s->active || (!s->mono_to && !s->mono_w)) return; /* off: the block is not touched */
    for (unsigned i = 0; i < frames; ++i, audio += 2) {
        s->mono_w = toward(s->mono_w, s->mono_to, s->step);
        double l = audio[0], r = audio[1], m;
        if (!__builtin_isfinite(l)) l = 0;
        if (!__builtin_isfinite(r)) r = 0;
        m = (l + r) * 0.5;
        if (s->mono_w >= 1) {
            audio[0] = audio[1] = (float)m;
        } else {
            audio[0] = (float)(l + (m - l) * s->mono_w);
            audio[1] = (float)(r + (m - r) * s->mono_w);
        }
    }
}

/* bs2b's cross_feed_d: the low-passed other channel and the channel's own highs. */
static void feed_in(sx_slot *q, double l, double r, double *ol, double *or_) {
    const sx_coef *c = &q->c;
    sx_mem *m = &q->m;
    /* + 1e-18 - 1e-18 flushes decaying tails before they reach denormals, which MIPS FPUs trap on (as the EQ does) */
    m->lo[0] = c->a0lo * l + c->b1lo * m->lo[0] + 1e-18 - 1e-18;
    m->lo[1] = c->a0lo * r + c->b1lo * m->lo[1] + 1e-18 - 1e-18;
    m->hi[0] = c->a0hi * l + c->a1hi * m->asis[0] + c->b1hi * m->hi[0] + 1e-18 - 1e-18;
    m->hi[1] = c->a0hi * r + c->a1hi * m->asis[1] + c->b1hi * m->hi[1] + 1e-18 - 1e-18;
    m->asis[0] = l;
    m->asis[1] = r;
    *ol = (m->hi[0] + m->lo[1]) * c->gain;
    *or_ = (m->hi[1] + m->lo[0]) * c->gain;
}

/* The wanted level has no slot: give it a free one (a slot that has faded out), starting from the other's memory. */
static void assign(stereo_dsp *s) {
    int want = s->level_to;
    if (!want || s->slot[0].level == want || s->slot[1].level == want) return;
    for (int k = 0; k < 2; ++k) {
        if (s->slot[k].level && s->slot[k].w > 0) continue;
        sx_mem m = s->slot[1 - k].m;
        int live = s->slot[1 - k].level;
        put(s, k, want, 0);
        if (live) s->slot[k].m = m;
        return;
    }
}

void stereo_post(stereo_dsp *s, float *audio, unsigned frames) {
    if (!audio || !s->active || (!s->level_to && !s->slot[0].level && !s->slot[1].level)) return; /* off: untouched */
    for (unsigned i = 0; i < frames; ++i, audio += 2) {
        double l = audio[0], r = audio[1], wl = 0, wr = 0, sw = 0;
        if (!__builtin_isfinite(l)) l = 0;
        if (!__builtin_isfinite(r)) r = 0;
        assign(s);
        for (int k = 0; k < 2; ++k) {
            sx_slot *q = &s->slot[k];
            if (!q->level) continue;
            int on = q->level == s->level_to;
            q->w = toward(q->w, on, s->step);
            if (!on && !q->w) { /* faded out: free */
                memset(q, 0, sizeof(*q));
                continue;
            }
            double ol, or_;
            feed_in(q, l, r, &ol, &or_);
            wl += q->w * ol;
            wr += q->w * or_;
            sw += q->w;
        }
        double dry = sw < 1 ? 1 - sw : 0;
        audio[0] = (float)(l * dry + wl);
        audio[1] = (float)(r * dry + wr);
    }
}

int stereo_carry_out(const stereo_dsp *s, stereo_carry *c) {
    memset(c, 0, sizeof(*c));
    if (!s->active) return 1; /* nothing to hand on, and nothing wrong */
    if (!__builtin_isfinite(s->mono_w)) return 0;
    for (int k = 0; k < 2; ++k) {
        const sx_slot *q = &s->slot[k];
        if (!q->level) continue;
        if (!__builtin_isfinite(q->w)) return 0;
        for (int j = 0; j < 2; ++j)
            if (!__builtin_isfinite(q->m.lo[j]) || !__builtin_isfinite(q->m.hi[j]) || !__builtin_isfinite(q->m.asis[j]))
                return 0;
    }
    c->rate = s->rate;
    c->mono_w = s->mono_w;
    memcpy(c->slot, s->slot, sizeof c->slot);
    return 1;
}

int stereo_carry_live(const stereo_carry *c, int rate) {
    if (!c->rate || c->rate != rate) return 0;
    return c->mono_w > 0 || (c->slot[0].level && c->slot[0].w > 0) || (c->slot[1].level && c->slot[1].w > 0);
}

/* The weights and the filters go on from where the last instance left them; what the record asks now (mono_to, level_to)
 * stays, so a ramp that was cut short finishes and a setting changed at the join ramps. */
void stereo_carry_in(stereo_dsp *s, const stereo_carry *c) {
    if (!s->active || c->rate != s->rate) return;
    s->mono_w = c->mono_w;
    memcpy(s->slot, c->slot, sizeof s->slot);
}
