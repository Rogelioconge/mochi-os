/* Isolated, host-tested rehydration probe. Never linked into demo.
 * This only specifies a correct fail-closed state machine and V2.1 flag=1.
 * It does NOT guarantee stock MIPS builder can be re-entered after init.
 */
#include "mox_grid_rebuild.h"

mox_rebuild_result mox_rebuild_stock_grid_probe(
    void *home, mox_rebuild_state *state, const mox_rebuild_ops *ops) {
    int pages;
    if (!home || !state || !ops || !ops->root_present ||
        !ops->slide_view_present || !ops->page_count ||
        !ops->pages_valid || !ops->build_pages)
        return MOX_REBUILD_BLOCKED;
    if (!ops->root_present(home) || !ops->slide_view_present(home))
        return MOX_REBUILD_BLOCKED;
    pages = ops->page_count(home);
    if (pages < 0 || pages > 8) return MOX_REBUILD_BLOCKED;
    if (pages > 0) {
        /* Existing pages are never rebuilt; avoid double registrations. */
        return ops->pages_valid(home) ? MOX_REBUILD_ALREADY_READY : MOX_REBUILD_BLOCKED;
    }
    if (state->attempted) return MOX_REBUILD_BLOCKED;
    /* The only call allowed on an empty, structurally valid stock Home.
     * The V2.1 caller uses $a1=1 (slide indicator enabled).
     * Latch before calling, so failures and reentrancy cannot retry. */
    state->attempted = 1;
    if (ops->build_pages(home, 1) != 0) return MOX_REBUILD_BLOCKED;
    pages = ops->page_count(home);
    if (pages < 1 || pages > 8 || !ops->pages_valid(home))
        return MOX_REBUILD_BLOCKED;
    return MOX_REBUILD_RECONSTRUCTED;
}
