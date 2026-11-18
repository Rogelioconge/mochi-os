# Select mode (shared)

**Sources:** `patch/selmode.c` / `selmode.h`, `m1_sel_all_can` in `patch/common.c`, `LIST_SEL_FILL`
in `offsets.inc`, `select_bar` / `sg_pill` in `tools/pod_ui.py`, `sg_listplus_off` / `sg_trash_off`
in `tools/mod_icons.py` (`SONGS_IMAGES`), `Select Items` / `Deselect All` in `tools/pod_i18n.py`.
**Preview:** `tools/preview/preview_selmode.py` (the album page's select mode).

## Purpose

One multi-select for every list page: the marks bitset and the chrome of the mode, so each page
keeps only its list, its nav buttons and its Add / Delete. Every page:

- nothing marked: the title reads "Select Items"; else "%d Selected";
- Select All reads "Deselect All" while every markable row is marked;
- the bar's pills are insensitive and dim (label and glyph at 35 %: `#595959`, Delete's red
  `#592525`; `sg_*_off` images for the glyphs) while nothing is marked. The dim look is the
  `disable` style, which AWTK picks from `enable`, not `sensitive`: `m1_sel_head` sets both;
- "Deselect All" fits the button's 96 px at 18 px in every language (Japanese `選択解除`,
  French `Aucun`, German `Keine`);
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
| `m1_sel_head(s)` | title text, Select All label, pill sensitivity (only in the mode; the page sets its own title otherwise) |
| `m1_sel_paint(s, canvas, i, y, rh, w, mark_x, view_h)` | the fill and the mark of row i, before the row's cover and text |

The page keeps its own `select` flag (or reads `s->on`), hides its nav buttons, retexts, resizes,
clamps the scroll, fits the rail and runs Add / Delete on `bits` / `nsel`. After a toggle it calls
its own "count changed" (head, redraw). `m1_sel_all_can` (common.c) is the Select All on a bitset.

## Pages on it

Songs (`sg.sel`), Folders (`fo.sel`, `fo_can`: folder or audio file, not a dot name), Playlists
(`pl.sel`, pill `pl_del`; list rows get the fill, grid cells keep `pl_mark`), Podcasts (`pg.msel`
bound on `pg.pick` with `m1_sel_bind`; `can` reads the `pg.can` cache `pg_sel_scan` fills; `pill[0]`
is set at each `pg_select` to Delete or Unsubscribe), the album page (`ab.sel`, view_h `AH_WIN_H`; its bar is in the page's tone, see [album-page](album-page.md): `select_bar` with no hairline, colours set at run time).

## Notes

- `LIST_SEL_FILL` is alpha-blended by `canvas_fill_rect`.
- New pages with a select mode use this module; stock multi-select stays only on the stock fallback pages.
