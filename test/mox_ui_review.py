#!/usr/bin/env python3
"""Isolated checks for the MOX Home source scene (no firmware required)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import awtk_ui
import mox_home_review as review


def main():
    checks = 0

    def ok(value, explanation):
        nonlocal checks
        assert value, explanation
        checks += 1

    scene = review.load_tree()
    rows = review.audit(scene)
    ok(len(rows) == 26, '26 native menu rows')
    ok(scene.find('mox_cover_accent') is not None, 'Cover Flow accent')
    ok(scene.find('pod_minibar') is not None, 'Native mini-player included')
    ok(scene.find('navigationbar_view') is not None, 'Grid-entry navbar retained')
    ok(awtk_ui.serialize(awtk_ui.parse(awtk_ui.serialize(scene))) == awtk_ui.serialize(scene),
       'Source AWTK roundtrip exact')

    # Negative structural tests must actually fail, rather than watering down
    # the existing firmware integration tests.
    broken = awtk_ui.parse(awtk_ui.serialize(scene))
    broken.find('mox_card1').w += 1
    try:
        review.audit(broken)
    except ValueError:
        ok(True, 'Rejects wrong touch-safe geometry')
    else:
        raise AssertionError('Bad card geometry was accepted')
    broken = awtk_ui.parse(awtk_ui.serialize(scene))
    broken.find('mox_cover_accent').set('sensitive', 'true')
    try:
        review.audit(broken)
    except ValueError:
        ok(True, 'Rejects an intercepting accent')
    else:
        raise AssertionError('Intercepting accent was accepted')
    pressed = scene.find('mox_card1').get('style:pressed:bg_color')
    idle = scene.find('mox_card1').get('style:normal:bg_color')
    ok(pressed == '#345f83' and pressed != idle,
       'Cover Flow has distinct pressed and idle styles')
    other = scene.find('mox_card2')
    ok(other.get('style:pressed:bg_color') != other.get('style:normal:bg_color'),
       'Other native cards have touch feedback')
    print(f'MOX UI: {checks}/{checks} source-level checks passed')


if __name__ == '__main__':
    main()
