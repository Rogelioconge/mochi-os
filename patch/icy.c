/* M1+ Music Radio, the player's read-only ICY metadata tap (docs/modules/radio.md): intercepts MPlayer's native HTTP
 * ICY log call (0x4be4d0 -> mp_msg) and FFmpeg lavf's HTTPS ICY store call (0x5020cc -> av_opt_set), copies the raw
 * packet into ICY_FILE when demo has marked it wanted, and always forwards to the stock function unchanged.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Built with PEQ_PLAYER into hciplayer's payload (stateless: no .data or .bss).
 */
#include "icy.h"
#include "peq.h"

#define STOCK_MP_MSG 0x445cecu /* mp_msg(int mod, int lev, const char *fmt, ...) */
#define STOCK_AV_OPT_SET 0x6f86f0u /* av_opt_set(void *obj, const char *name, const char *val, int flags) */

static void icy_tap(const char *raw) {
    struct {
        char magic[8];
        int seq, gen;
    } hdr;
    void *f, *kill;
    icy_record rec;
    unsigned n;
    int next;
    if (!raw || !raw[0]) return;
    f = fopen(ICY_FILE, "r+b");
    if (!f) return;
    if (fread(&hdr, 1, sizeof hdr, f) != sizeof hdr || memcmp(hdr.magic, ICY_MAGIC, 8)) {
        fclose(f);
        return;
    }
    kill = fopen(PEQ_KILL, "rb");
    if (kill) {
        fclose(kill);
        fclose(f);
        return;
    }
    memset(&rec, 0, sizeof rec);
    memcpy(rec.magic, ICY_MAGIC, 8);
    next = hdr.seq + 1;
    if (next <= 0) next = 1;
    rec.seq = next;
    rec.gen = hdr.gen;
    n = strlen(raw);
    if (n >= ICY_RAW_MAX) {
        n = ICY_RAW_MAX - 1;
        while (n && ((unsigned char)raw[n] & 0xc0) == 0x80) --n; /* keep whole UTF-8 characters */
    }
    memcpy(rec.raw, raw, n);
    rec.seq_end = next;
    if (!fseek(f, 0, 0)) fwrite(&rec, 1, sizeof rec, f);
    fclose(f);
}

/* MPlayer stream/http.c scast_streaming_read (0x4be4d0): mp_msg(MSGT_NETWORK, MSGL_INFO, "\nICY Info: %s\n", buf). */
void icy_mplayer_msg(int mod, int lev, const char *fmt, const char *info) {
    icy_tap(info);
    ((void (*)(int, int, const char *, const char *))STOCK_MP_MSG)(mod, lev, fmt, info);
}

/* FFmpeg libavformat/http.c store_icy (0x5020cc): av_opt_set(s, "icy_metadata_packet", data, 0). */
int icy_av_opt_set(void *obj, const char *name, const char *val, int flags) {
    icy_tap(val);
    return ((int (*)(void *, const char *, const char *, int))STOCK_AV_OPT_SET)(obj, name, val, flags);
}
