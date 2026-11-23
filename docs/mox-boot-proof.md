# MOX OS — Sprint 6: verification before clearing the boot marker

This change does not bypass Shanling `home_page_init` or enable `mox_boot_candidate`. It does **not** ship a flashable update.

## Paint proof / watchdog

`hm_painted()` records an AWTK `EVT_AFTER_PAINT` event on the original Home window or the validated M1+ Music entry window. The five-second callback `hm_clear()` now acts as a deadline rather than unconditional success:

- When starting into the stock Shanling Home, its window must receive AFTER_PAINT and remain opened.
- When starting into the music Home, its layout must first contain all 26 rows and required widgets, and its own window must receive AFTER_PAINT and remain opened.
- A paint from another widget/window is never accepted, nor is a callback for an entry that failed validation.
- No paint by the deadline restores the stock grid and persists the failure note; the marker is not cleared until the failure note is durable.
- The marker is only called cleared successfully once both `unlink` and directory fsync succeed. A file-system failure leaves the state unproven and will trigger recovery on the next boot.

**Limitation:** `EVT_AFTER_PAINT` proves that AWTK delivered the post-paint event, not that the physical panel displayed a correct frame or that touch/input and playback work. On-device verification is required before changing the native launcher. At five seconds, a slow or interrupted boot deliberately falls back to Shanling.
