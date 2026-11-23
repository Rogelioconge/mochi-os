/* MOX OS: OFFLINE ONLY late-stock-grid reconstruction contract.
 * Not included in the device build, not called by boot or recovery.
 * A successful mock does not validate calling V2.1's MIPS builder on hardware.
 */
#ifndef MOX_GRID_REBUILD_H
#define MOX_GRID_REBUILD_H

typedef enum {
    MOX_REBUILD_BLOCKED = 0,
    MOX_REBUILD_ALREADY_READY = 1,
    MOX_REBUILD_RECONSTRUCTED = 2
} mox_rebuild_result;

typedef struct {
    unsigned attempted; /* sticky for the entire Home instance */
} mox_rebuild_state;

typedef struct {
    int (*root_present)(void *home);
    int (*slide_view_present)(void *home);
    int (*page_count)(void *home);     /* -1 on failure; 0 when empty */
    int (*pages_valid)(void *home);    /* fully checked, all 1..8 pages */
    int (*build_pages)(void *home, int with_indicator); /* 0 on success */
} mox_rebuild_ops;

mox_rebuild_result mox_rebuild_stock_grid_probe(
    void *home, mox_rebuild_state *state, const mox_rebuild_ops *ops);
#endif
