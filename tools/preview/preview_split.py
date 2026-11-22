#!/usr/bin/env python3
"""Mock-up of Settings > Library > Split Artists (patch/artsplit.c, docs/modules/settings.md): the Library page's row and the Split Artists page, off and on, drawn by preview_settings.py's
cards page from the built tree's own assets (ui/m1plus_library.bin, ui/m1plus_artistsplit.bin). Approximate (PIL, not AWTK).

  preview_split.py WORKDIR OUTDIR

Writes split-library.png (the whole Library page, the row On), split-off.png (the page with the switch off: the separators dimmed), split-on.png (on, the default separators) and
split-on-all.png (on, every separator), and the Split Genres page as split-genres-off.png and split-genres-on.png (its five separators, the semicolon on).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pod_pages as P
import preview_icons as PI, preview_settings as PS

LIB, SPL = P.LIBRARY_PAGE.key, P.ASPLIT_PAGE.key
ROWS = [r.label for r in P.LIBRARY_PAGE.rows]
SROWS = P.ASPLIT_PAGE.rows


def page_state(on, mask, rows=SROWS, actions=P.ASSEP_ACTIONS, bits=range(10)):
    sw = {f'pod_switch{i}': bool(mask >> k & 1) for k, i in zip(bits, (i for i, r in enumerate(rows) if r.action in actions))}
    sw['pod_switch0'] = on
    return {'switches': sw}


def genre_state(on, mask): return page_state(on, mask, P.GSPLIT_PAGE.rows, P.GSSEP_ACTIONS, P.GSSEP_BITS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('outdir')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True)
    os.makedirs(a.outdir, exist_ok=True)
    lib = {'switches': {f'pod_switch{ROWS.index(n)}': True for n in ('Index Rail', 'Section Headers')}, 'values': {f'pod_value{ROWS.index("Split Artists")}': 'On'}}
    panels = [('split-library', PS.draw_page(s, LIB, full=True, state=lib)), ('split-off', PS.draw_page(s, SPL, full=True, state=page_state(False, 0x17))),
              ('split-on', PS.draw_page(s, SPL, full=True, state=page_state(True, 0x17))), ('split-on-all', PS.draw_page(s, SPL, full=True, state=page_state(True, 0x3ff))),
              ('split-genres-off', PS.draw_page(s, P.GSPLIT_PAGE.key, full=True, state=genre_state(False, 1))), ('split-genres-on', PS.draw_page(s, P.GSPLIT_PAGE.key, full=True, state=genre_state(True, 1)))]
    for name, im in panels: im.convert('RGB').save(os.path.join(a.outdir, name + '.png'))
    print('wrote', len(panels), 'images to', a.outdir)


if __name__ == '__main__':
    main()
