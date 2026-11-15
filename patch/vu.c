/* M1+ Music VU Meter Mode, the player's level tap (docs/modules/vu.md): measures a block without writing it and publishes
 * the levels as a ring of timed entries in VU_FILE.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Built with PEQ_PLAYER into hciplayer's payload (no .bss: the ring is in .data, one writer, the playback thread).
 */
#include "vu.h"

#define MERGE_US 10000 /* blocks shorter than this join the entry before them */
#define JOIN_US 20000 /* ... when they follow it within this much of its end */
#define AF_FORMAT_FLOAT 0x1d

static vu_record rec __attribute__((section(".data")));
static int fresh __attribute__((section(".data"))); /* a stream just started: its first block opens an entry */

static long long now_us(void) {
    struct {
        int sec, nsec;
    } ts;
    return clock_gettime(1, &ts) ? 0 : (long long)ts.sec * 1000000 + ts.nsec / 1000;
}

void *vu_open(void) {
    void *f = fopen(VU_FILE, "r+b");
    char magic[8];
    if (!f) return 0;
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, VU_MAGIC, 8)) {
        fclose(f);
        return 0;
    }
    return f;
}

enum { K_NONE, K_FLOAT, K_S16, K_S24, K_S32, K_U8 };

/* MPlayer's af format: bit 0 little endian, bit 1 unsigned, bit 2 float, bits 3..5 the width (8 << n), bit 6 and up special. */
static int kind(int format, int bps) {
    if (format == AF_FORMAT_FLOAT) return bps == 4 ? K_FLOAT : K_NONE;
    if ((format & ~63) || !(format & 1) || (format & 4) || bps * 8 != (((format >> 3) & 7) + 1) * 8) return K_NONE;
    if (format & 2) return bps == 1 ? K_U8 : K_NONE;
    return bps == 2 ? K_S16 : bps == 3 ? K_S24 : bps == 4 ? K_S32 : K_NONE;
}

int vu_supported(int format, int bps) { return kind(format, bps) != K_NONE; }

static void publish(void *f) {
    rec.seq++;
    rec.seq_end = rec.seq;
    rec.now_us = now_us();
    memcpy(rec.magic, VU_MAGIC, 8);
    if (!fseek(f, 0, 0)) fwrite(&rec, 1, sizeof rec, f);
    fclose(f);
}

void vu_note(int rate, int channels) {
    void *f = vu_open();
    if (!f) return;
    rec.rate = rate;
    rec.channels = channels > 1 ? 2 : 1;
    if (!rate) rec.channels = 0;
    fresh = 1;
    publish(f);
}

/* Peak and sum of squares of one channel, in the format's own units. */
#define SCAN(T, LOAD) \
    for (unsigned i = 0; i < frames; ++i) { \
        const T *s = (const T *)((const char *)audio + (unsigned)(i * nch + c) * sizeof(T)); \
        double v = LOAD; \
        double a = v < 0 ? -v : v; \
        if (a > pk) pk = a; \
        sq += v * v; \
    }

static void channel(const void *audio, int k, int nch, unsigned frames, int c, float *peak, float *sumsq) {
    double pk = 0, sq = 0, scale = 1;
    if (k == K_FLOAT) {
        for (unsigned i = 0; i < frames; ++i) {
            float x = ((const float *)audio)[i * nch + c];
            float a = x < 0 ? -x : x;
            if (!(a <= 3.0e38f)) continue; /* a NaN or infinity counts as silence */
            if (a > pk) pk = a;
            sq += (double)a * a;
        }
    } else if (k == K_S16) {
        scale = 1.0 / 32768;
        SCAN(short, *s)
    } else if (k == K_S32) {
        scale = 1.0 / 2147483648.0;
        SCAN(int, *s)
    } else if (k == K_U8) {
        scale = 1.0 / 128;
        SCAN(unsigned char, (int)*s - 128)
    } else {
        scale = 1.0 / 8388608;
        for (unsigned i = 0; i < frames; ++i) {
            const unsigned char *b = (const unsigned char *)audio + (unsigned)(i * nch + c) * 3;
            double v = (int)(b[0] | b[1] << 8 | (int)(signed char)b[2] << 16);
            double a = v < 0 ? -v : v;
            if (a > pk) pk = a;
            sq += v * v;
        }
    }
    *peak = (float)(pk * scale);
    *sumsq = (float)(sq * scale * scale);
}

void vu_block(void *f, const void *audio, int format, int bps, int nch, int rate, unsigned frames, int delay_us) {
    int k = kind(format, bps);
    if (k == K_NONE || nch < 1 || rate < 1 || !frames) {
        fclose(f);
        return;
    }
    vu_entry e;
    memset(&e, 0, sizeof e);
    for (int c = 0; c < 2; ++c) channel(audio, k, nch, frames, nch > 1 ? c : 0, &e.peak[c], &e.sumsq[c]);
    e.due_us = now_us() + delay_us;
    e.frames = (int)frames;
    e.dur_us = (int)((double)frames * 1000000.0 / rate);
    vu_entry *h = &rec.ring[rec.head];
    long long end = h->due_us + h->dur_us, gap = e.due_us - end;
    if (!fresh && rec.count && h->dur_us < MERGE_US && gap > -JOIN_US && gap < JOIN_US) {
        for (int c = 0; c < 2; ++c) {
            if (e.peak[c] > h->peak[c]) h->peak[c] = e.peak[c];
            h->sumsq[c] += e.sumsq[c];
        }
        h->frames += e.frames;
        h->dur_us += e.dur_us;
    } else {
        rec.head = rec.count ? (rec.head + 1) % VU_RING : 0;
        rec.ring[rec.head] = e;
        if (rec.count < VU_RING) rec.count++;
        fresh = 0;
    }
    rec.rate = rate;
    rec.channels = nch > 1 ? 2 : 1;
    publish(f);
}
