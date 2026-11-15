# Font

**Sources:** `tools/mod_font.py`, `tools/font_inter.py`, `assets/fonts/`, `patch/fontregion.c`,
`patch/textgamma.c`, `tools/textgamma.py`. **Tests:** `test/pod/textgamma.py`, `test/pod/i18n.py`.
**Preview:** `tools/preview/preview_cjk.py`, `tools/preview/preview_aa.py`.

The UI uses one file, `release/assets/default/raw/fonts/default.ttf`, rewritten by code point. Its
unitsPerEm (256), hhea ascender/descender/lineGap and OS/2 metrics stay stock, so every layout sized
from them still adds up. The font step runs first, so every later step measures the new font. A
second file, `lyrics.ttf`, serves the lyric lines only. Text width rules: [ui-rules](ui-rules.md)
"Text width".

## Latin (Inter)

Latin, Greek and Cyrillic come from **Inter 4.1 Medium**: the committed subset
`assets/fonts/Inter-m1plus.ttf` (`INTER_WEIGHT` in `mod_font.py`; `font_inter.py INTER_ZIP`
regenerates it byte-identically; OFL in `assets/fonts/`).

- Outlines are scaled to 252 stock units per Inter em, so the cap height equals Arial's.
- Composites are decomposed. Digits map to the tabular forms (`zero.tf` .. `nine.tf`) so numbers do
  not jitter.
- **Tracking 8:** every advance loses 8 units and each outline moves left 4. Inter as designed is
  3-9 % wider than the stock Arial once demo's +1 px per glyph is added; 8 makes the mean width
  ratio about 1.0.
- **Why Medium:** at 16 to 21 px on the unhinted 320 x 480 panel, Regular's stems read thin on black
  pages. Medium has the weight of the stock text it replaces and matches the CJK Medium beside it.
- Medium is slightly wider; the fit tests in all 13 languages pass. One stock label clips:
  uk_UK "System Settings" in the 200 px navbar title. It is stock's and stays.

## CJK (SHS)

CJK, kana and Hangul come from **Source Han Sans SC Medium 2.005R** (`SHS_WEIGHT`). It covers the
stock CJK, kana and Hangul code points plus CJK punctuation, fullwidth and halfwidth forms, so
`，。：！？（）「」《》` in Chinese text are drawn like the ideographs (SC placement) instead of the old
font's. Conjoining jamo and halfwidth Hangul stay stock. Thai, Arabic, symbols and arrows keep the
stock glyphs.

- The CFF outline is scaled 0.256 and shifted down 7 units, so the ideographs' ink centre matches
  Inter's capitals and stock rows keep their position. Curves are converted to quadratics.
  Hangul advances become proportional (about 8 % narrower).
- **Why Medium:** Regular reads thin at 16 to 22 px. Static SHS weights are not point-compatible, so
  there is no in-between instance. Emboldening Regular fills in dense ideographs; Medium stays open.
- **Fetched, never committed:** the SHS TTC zip is pinned by SHA-256 and fetched into `fonts/` by
  `tools/mod_font.py --fetch`. Committing it would be a Modified Version that cannot keep the
  reserved name "Source". The merged font keeps the stock name table and appends the Inter and SHS
  copyright lines and the OFL.
- **Merge:** the tree font must be the stock SHA-256. CJK glyphs are written over the stock glyph
  by cmap name and Inter glyphs are added. A subset pass drops the replaced glyphs, hinting, `gasp`,
  `DSIG` and glyph names. `mod_font.verify` checks that metrics stay stock and that every stock code
  point still maps, with ink wherever stock had ink (no tofu).

## Regional forms

One file cannot hold three fonts (a second 10 MB face would not fit the rootfs). So `default.ttf`
carries the SC forms in its Unicode cmap (3, 1), which stb_truetype picks, plus three more format-4
subtables on the Mac platform, which it never picks: (1, 25) SC, (1, 1) JP, (1, 2) TC. Each is the
default map with that region's glyph wherever it differs from SC (`mod_font.REGIONS`).

- Ideographs are limited to the region's common set because of the rootfs size: JP the JIS X 0208
  level-1 kanji, TC the Big5 frequent hanzi. Every differing non-ideograph is included.
- Every regional map gives `—` and `…` SHS's full-width forms, so `——` and `……` run on in Chinese
  and Japanese UIs. The ink of `—` is stretched past both edges because demo's +1 px per glyph would
  leave a gap. The default map keeps Inter's for English and the other Latin UIs.
- Curly quotes stay Inter's in every map, so `Don’t` in a Chinese UI is not split by a full-width
  apostrophe.
- **Runtime:** `patch/fontregion.c` points the live font's `index_map` at the subtable of the UI
  language (`ja` JP; `zh` with `HK` or `TW` TC; other `zh` SC; anything else or the kill switch, the
  default map). It then empties the glyph cache and repaints, only when the choice changes. It runs
  from the boot guard's ready path and from one 10 ms timer after `EVT_LOCALE_CHANGED` or
  `EVT_THEME_CHANGED`. No hook.
- The language picks the forms, not the text: a Japanese title in a Chinese UI uses SC forms. A
  per-text choice would need code at paint.

## Lyrics face

`release/assets/default/raw/fonts/lyrics.ttf` (AWTK font name `lyrics`) is the Inter 4.1 **Bold**
subset (`assets/fonts/Inter-Bold-m1plus.ttf`, `font_inter.py --weight Bold`) with the same code
points and tabular digits. It is **tracked 16 units** (`LYRIC_TRACKING`): the UI face's 8 is looser
than Apple's bold lyric text, and at 30 px 16 keeps `Be what you want to be` in one 264 px row.

- **Why a separate file:** AWTK has no per-glyph fallback. `font_get_glyph` is one call through the
  one font's vtable, so every glyph of a draw comes from the canvas font. The lyrics payload picks
  the style per line: a line whose code points are all in `lyrics.ttf` takes the bold style, any
  other line (CJK, kana, Hangul, symbols) the default font's. [lyrics](lyrics.md).
- `mod_font.lyric_face` builds it with `default.ttf`'s unitsPerEm and vertical metrics, so a font
  size is the same number of pixels and the baseline matches. Only the two lyric label styles of
  Now Playing name it.
- A font that cannot be loaded falls back to the default font, so a missing file shows the default,
  not nothing.

## Coverage gamma

stb_truetype blends each glyph's 8-bit coverage straight into sRGB, so light text on black reads
thin. Every freshly rasterised mask of the default font is mapped once through
`a' = round(255 (a/255)^(1/G))`, **G = 1.45** (`GAMMA` in `tools/textgamma.py`; 1.25 is the other
candidate in `preview_aa.py`). The 256-byte table `TEXT_GAMMA_LUT` is written into `stock.h` by
`tools/pod.py`.

- `tg_apply` (called from `fr_apply`) swaps the font object's get_glyph slot for `tg_get_glyph`.
  A glyph-cache hit returns stock's copy untouched, because its mask was mapped when it was
  rasterised. A miss lets stock rasterise and cache the glyph, then maps the bitmap in place, so
  no glyph is mapped twice. Installing empties the glyph cache and repaints.
- Mono fonts, fonts that are not stb fonts, a foreign get_glyph slot and the kill switch leave
  stock. No hook and no per-paint work.
- `lyrics.ttf` is covered too: `ly_start` applies it on each Now Playing open, and `ly_title_face` (the Vinyl and VU titles) on each Latin title. The first open loads
  the file earlier than stock would and repaints once. A language or theme change recreates the font
  with the stock slot until the next open.

## Limits

- Rootfs size: stock is the limit (`fwtool` enforces it). The font changes fit, with the regional
  forms and `lyrics.ttf` taking most of the headroom.
- Latin UIs draw CJK ellipsis and dashes with Inter's.
- The colon is not raised between digits (no contextual alternates in AWTK).
- Combining marks are drawn without positioning; the few absent from Inter keep the stock glyph.
- The pull-down's volume label (`100` at 16 px) fits the stock 30 px label; the font step does
  nothing for it.
