/* MOX OS: conservative album tap guard, portable to the MIPS32 payload.
 * Pure state logic. No allocations, clocks, syscalls, AWTK calls or globals.
 * This does not change the stock scroll physics or touch dispatch.
 */
#ifndef MOX_TOUCHGUARD_H
#define MOX_TOUCHGUARD_H

typedef struct {
    int x, y, offset;
    unsigned char cancelled;
} mox_touch_t;

static inline void mox_touch_cancel(mox_touch_t *t) { t->cancelled = 1; }

static inline void mox_touch_begin(mox_touch_t *t, int x, int y, int offset, int scrolling) {
    t->x = x;
    t->y = y;
    t->offset = offset;
    t->cancelled = scrolling != 0;
}

/* Compare without signed overflow if touch coordinates are unexpected.
 * Comparisons are monotonic: once cancelled, moving back never re-arms. */
static inline void mox_touch_move(mox_touch_t *t, int x, int y, int offset, unsigned threshold) {
    if (t->cancelled) return;
    long long dx = (long long)x - (long long)t->x;
    long long dy = (long long)y - (long long)t->y;
    if (threshold == 0 || offset != t->offset || dx >= (long long)threshold || dx <= -(long long)threshold ||
        dy >= (long long)threshold || dy <= -(long long)threshold)
        t->cancelled = 1;
}

static inline int mox_touch_end(mox_touch_t *t, int x, int y, int offset, int scrolling, unsigned threshold) {
    mox_touch_move(t, x, y, offset, threshold);
    if (scrolling) t->cancelled = 1;
    return !t->cancelled;
}
#endif
