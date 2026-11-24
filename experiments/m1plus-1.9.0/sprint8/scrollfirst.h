/* Mochi OS: choose when a first MOVE can use the original AWTK handler twice.
 * This file makes no changes to the scroll_view and never touches the filesystem.
 * Only enable this for a known, live scroll_view target (Albums, sprint 8).
 */
#ifndef MOX_SCROLLFIRST_H
#define MOX_SCROLLFIRST_H
static inline unsigned mox_diff_unsigned(int a, int b) {
    /* Exact absolute distance even for INT_MIN/INT_MAX, without signed overflow. */
    return a >= b ? (unsigned)a - (unsigned)b : (unsigned)b - (unsigned)a;
}
static inline int mox_first_move_candidate(int pressed, int dragged, int snap, int xslide, int yslide,
                                            int start_x, int start_y, int x, int y, unsigned threshold) {
    if (!pressed || dragged || snap || (!xslide && !yslide) || !threshold) return 0;
    return (xslide && mox_diff_unsigned(x, start_x) >= threshold) ||
           (yslide && mox_diff_unsigned(y, start_y) >= threshold);
}
#endif
