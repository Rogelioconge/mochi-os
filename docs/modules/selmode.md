# Select mode (shared)

**Sources:** `patch/selmode.c` / `selmode.h`, `m1_sel_all_can` in `patch/common.c`, `LIST_SEL_FILL`
in `offsets.inc`, `selall_button` / `select_bar` in `tools/pod_ui.py`, `selbar_images` / `glass_piece` in
`tools/mod_icons.py` (`SELBAR_*`), `Select Items` / `Deselect All` in `tools/pod_i18n.py`.
**Preview:** `tools/preview/preview_selmode.py` (the album page's select mode).

## Purpose

One multi-select for every list page: the marks bitset and the chrome of the mode, so each page
keeps only its list, its nav buttons and its Add / Delete. Every page:

- nothing marked: the title reads "Select Items"; else "%d Selected";
- Select All reads "Deselect All" while every markable row is marked;
- Select All / Deselect All is a glass pill at the navbar's right (`sg_selall_glass`, drawn `patch3_x`, y 4, 42 high,
  right edge `SG_SELALL_R` 311, the 17 px label centred with `SG_SELALL_PAD` 14 px each side). `m1_selall_fit` sets its width from the
  label after each text change; the title ends at `SG_SELALL_X`, the pill's left edge at its widest label (every language fits);
- the bar holds ONE centred glass capsule of icon-only buttons (no text): two 60 px slots (Add to Playlist, Delete; 120 x 42) or
  one (Playlists, Podcasts: Delete, Unsubscribe; 60 x 42), vertically centred in the 64 px bar. Each slot is a slice of the
  capsule (`glass_piece`: `sg_bar_add`, `sg_bar_del`, `sg_bar_one`; `_down` with the round highlight; `_off` with the glyph at 35 %).
  The bar has no background: the `sg_bar` view is the capsule's own box, floating over the rows (a touch beside it reaches them);
- the buttons are insensitive and dim while nothing is marked (the `_off` images). The dim look is the
  `disable` style, which AWTK picks from `enable`, not `sensitive`: `m1_sel_head` sets both;
- a marked row has a faint fill: white at alpha `0x12` (`LIST_SEL_FILL`; `#121212` on black), the
  window's full width under mark, cover and text, not over the hairline.

## API

`m1_sel_t` (in the page's static struct): `bits`, `count`, `nsel`, `nmark`, `on`, `can`, `ctx`, the
two marks, the chrome widgets.

| call | does |
|---|---|
| `m1_sel_init(s, win, back, title, btn_selall, bar, pill0, pill1, can, ctx)` | widgets, `can(ctx, i)` (NULL: all rows), the marks; 0 without marks |
| `m1_sel_free(s)` | bits (when ours) and marks |
| `m1_sel_reset(s, count)` | new list: own bits, nothing marked, `nmark` recounted through `can` (call after the list the predicate reads is set); 0 without memory |
| `m1_sel_bind(s, bits, count)` | the same on a borrowed fixed vector (never freed) |
| `m1_sel_clear`, `m1_sel_is`, `m1_sel_every` | |
| `m1_sel_toggle(s, i)` | flips a markable row; 1 when it did |
| `m1_sel_toggle_all(s)` | all markable rows, unless all are: then none |
| `m1_sel_enter(s, on, off_end)` | clears, back icon x / back, Select All and the bar shown, the title's end `SG_SELALL_X` (off: `off_end`), then `m1_sel_head` |
| `m1_selall_fit(btn)` | the Select All pill as wide as its label plus the padding, right edge at 311 |
| `m1_sel_head(s)` | title text, Select All label (then `m1_selall_fit`), pill sensitivity (only in the mode; the page sets its own title otherwise) |
| `m1_sel_paint(s, canvas, i, y, rh, w, mark_x, view_h)` | the fill and the mark of row i, before the row's cover and text |

The page keeps its own `select` flag (or reads `s->on`), hides its nav buttons, retexts, resizes,
clamps the scroll, fits the rail and runs Add / Delete on `bits` / `nsel`. After a toggle it calls
its own "count changed" (head, redraw). `m1_sel_all_can` (common.c) is the Select All on a bitset.

## Pages on it

Songs (`sg.sel`), Folders (`fo.sel`, `fo_can`: folder or audio file, not a dot name), Playlists
(`pl.sel`, pill `pl_del`; list rows get the fill, grid cells keep `pl_mark`), Podcasts (`pg.msel`
bound on `pg.pick` with `m1_sel_bind`; `can` reads the `pg.can` cache `pg_sel_scan` fills; `pill[0]`
is set at each `pg_select` to Delete or Unsubscribe), the album page (`ab.sel`, view_h `AH_WIN_H`; its bar is in the page's tone, see [album-page](album-page.md): colour set at run time).

The Update Library folder picker (`patch/lupick.c`) uses the same Select All / Deselect All glass pill (`m1_selall_fit`; inert: the glass stays, the label dims to `SELECT_DIM`), marks and bar style, but keeps its own path set (folders across levels; a chosen folder covers its children) rather than `m1_sel_t`.

## Notes

- `LIST_SEL_FILL` is alpha-blended by `canvas_fill_rect`.
- New pages with a select mode use this module; stock multi-select stays only on the stock fallback pages.
