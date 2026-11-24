/* Mochi OS / Sprint 9: opt-in, bounded, low-overhead UI timing counters.
 * Only writes to microSD when the page is destroyed. No persistent mutations
 * unless /mnt/mmc/mochi-perf-enable is present. No logging in paint/gesture paths.
 * This header uses the stock C runtime imports already available in the payload.
 */
#ifndef MOX_PERF_H
#define MOX_PERF_H
#define MOX_PERF_ENABLE "/mnt/mmc/mochi-perf-enable"
#define MOX_PERF_OUTPUT "/mnt/mmc/mochi-performance.csv"

typedef struct {
    unsigned count, over16, over33, max_us;
    unsigned long long sum_us;
} mox_perf_stat_t;

typedef struct {
    unsigned enabled;
    mox_perf_stat_t total, database, index, paint, cover, scroll;
} mox_perf_page_t;

static inline unsigned long long mox_perf_now_us(void) {
    struct { int sec, nsec; } ts;
    return clock_gettime(1, &ts) ? 0 : (unsigned long long)(unsigned)ts.sec * 1000000ull + (unsigned)ts.nsec / 1000u;
}

static inline void mox_perf_begin_page(mox_perf_page_t *p) {
    /* All prior state is zeroed with its owning page. Avoid open() and stat()
     * in event callbacks: check opt-in once per page life. */
    p->enabled = access(MOX_PERF_ENABLE, F_OK) == 0;
}
static inline unsigned long long mox_perf_start(const mox_perf_page_t *p) {
    return p->enabled ? mox_perf_now_us() : 0;
}
static inline void mox_perf_end(mox_perf_page_t *p, mox_perf_stat_t *s, unsigned long long start) {
    unsigned long long end, delta;
    unsigned us;
    if (!p->enabled || !start) return;
    end = mox_perf_now_us();
    if (!end || end < start) return;
    delta = end - start;
    us = delta > 0xffffffffull ? 0xffffffffu : (unsigned)delta;
    if (s->count != 0xffffffffu) ++s->count;
    if (s->sum_us <= ~0ull - us) s->sum_us += us;
    if (us > s->max_us) s->max_us = us;
    if (us > 16000u && s->over16 != 0xffffffffu) ++s->over16;
    if (us > 33000u && s->over33 != 0xffffffffu) ++s->over33;
}

static inline void mox_perf_dump(const mox_perf_page_t *p, const char *page, unsigned entries) {
    static const char *const labels[6] = {"total", "database", "index", "paint", "cover", "scroll"};
    const mox_perf_stat_t *const stats[6] = {&p->total, &p->database, &p->index, &p->paint, &p->cover, &p->scroll};
    char b[192];
    int fd, i, n;
    if (!p->enabled) return;
    /* One open on page destruction; no writes while the user scrolls. */
    fd = open(MOX_PERF_OUTPUT, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return;
    for (i = 0; i < 6; ++i) {
        const mox_perf_stat_t *s = stats[i];
        n = snprintf(b, sizeof b, "mox1,%s,%u,%s,%u,%llu,%u,%u,%u\n", page, entries, labels[i],
                     s->count, s->sum_us, s->max_us, s->over16, s->over33);
        if (n > 0 && n < (int)sizeof b) {
            int off = 0, wrote;
            while (off < n && (wrote = write(fd, b + off, (unsigned)(n - off))) > 0) off += wrote;
        }
    }
    close(fd);
}
#endif
