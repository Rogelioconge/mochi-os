#!/usr/bin/env python3
"""MOX OS Sprint 7: inspect independent Home AWTK asset and routing.

Does not run the target MIPS program or prove framebuffer/device behavior.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import awtk_ui  # noqa: E402
import mod_mox_native as mn  # noqa: E402
import pod_pages  # noqa: E402
import pod_ui  # noqa: E402


def run():
    # Build a source menu in memory. Simulate the icon-build stage by placing
    # simple image nodes after the already-built native cards (no PNG needed).
    orig = pod_ui.build_page(pod_pages.MENU)
    assert orig.name == 'm1plus_menu_page'
    for i in range(mn.ROW_COUNT):
        row = orig.find(f'pod_row{i}')
        row.children.insert(1, awtk_ui.Widget('image', 16, 14, 24, 24,
                                             [('name', 'pod_icon'), ('image', 'pod_ic_test'), ('sensitive', 'false')]))
    source = awtk_ui.serialize(orig)
    built = mn.transform(source)
    home = awtk_ui.parse(built)
    assert home.name == 'mox_home_page' and home.type == 'window'
    assert (home.find('navigationbar_view').get('visible'), home.find('navigationbar_view').get('sensitive')) == ('false', 'false')
    print('OK: MOX has an independent Home window; the navbar starts hidden')
    # Strict structural equivalence, except for the three audited property values.
    clone = awtk_ui.parse(built)
    clone.set('name', 'm1plus_menu_page')
    nav = clone.find('navigationbar_view')
    nav.remove('visible'); nav.remove('sensitive')
    assert awtk_ui.serialize(clone) == source
    print('OK: row actions and original entry resource are unchanged')
    assert all(home.find(f'mox_card{i}') and home.find(f'pod_row{i}') for i in range(mn.ROW_COUNT))
    assert all(home.find(n) for n in ('pod_minibar', 'pod_pins', 'pod_daily', 'pod_shelf'))
    print('OK: all 26 rows, cover modules, pins and mini player are present')
    with tempfile.TemporaryDirectory() as d:
        parent = Path(d); folder = parent / mn.UI; folder.mkdir(parents=True)
        (folder / mn.SOURCE).write_bytes(source)
        mn.apply(parent, parent)
        assert (folder / mn.NATIVE).read_bytes() == built
        mn.apply(parent, parent)
        assert (folder / mn.SOURCE).read_bytes() == source
        print('OK: deterministic build; repeated installation is byte-identical')
        (folder / mn.NATIVE).write_bytes(b'corrupt')
        try:
            mn.apply(parent, parent)
        except ValueError:
            print('OK: differing pre-existing resource rejected')
        else:
            raise AssertionError('Corrupt native asset was accepted')
    for name in ('pod_minibar', 'pod_pins', 'pod_daily', 'pod_shelf'):
        bad = awtk_ui.parse(source)
        # Remove the named node (root or nested).
        def remove(w):
            w.children = [c for c in w.children if c.name != name]
            for child in w.children:
                remove(child)
        remove(bad)
        try:
            mn.transform(awtk_ui.serialize(bad))
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid resource without {name} accepted')
    print('OK: missing Home components are rejected')
    code = (ROOT / 'patch/m1plus.c').read_text()
    assert 'as_home && index == POD_ENTRY_PAGE ? "mox_home" : page->asset' in code
    assert 'open_page(POD_ENTRY_PAGE, restored ? 1 : 0)' in code
    assert 'if (m1plus_open_entry() != 0 || !hs.home_valid)' in (ROOT / 'patch/home.c').read_text()
    assert 'stock_home_init_trampoline(win, ctx)' in (ROOT / 'patch/home.c').read_text()
    print('OK: MOX is reserved for native Home; Shanling icon retains the normal menu/Back navigation')
    assert mn.added_rels() == ['release/assets/default/raw/ui/mox_home.bin']
    import ast
    import mod_polish
    stages = next(
        ast.literal_eval(node.value)
        for node in ast.parse((ROOT / 'tools/build.py').read_text()).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'STEPS' for target in node.targets)
    )
    names = [stage for stage, _ in stages]
    assert names.count('mod_mox_native') == 1
    assert names.index('mod_icons') < names.index('mod_polish') < names.index('mod_mox_native')
    # Regression: the later navbar-polishing step must be finished before
    # cloning the menu into the separate native Home resource.
    polished = awtk_ui.parse(source)
    assert polished.find('label_title').w > mod_polish.TITLE_W
    mod_polish.edit(polished)
    polished_data = awtk_ui.serialize(polished)
    native_polished = mn.transform(polished_data)
    assert awtk_ui.parse(native_polished).find('label_title').w == mod_polish.TITLE_W
    assert native_polished != built
    print('OK: Home generated after final title geometry (no stale AWTK clone)')
    print('OK: new asset is registered in the build and pack pipelines')
    print('MOX native resource: 8/8 checks OK (no launcher replacement)')


if __name__ == '__main__':
    run()
