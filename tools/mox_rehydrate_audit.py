#!/usr/bin/env python3
"""MOX OS: read-only V2.1 Home side-effect audit; does not authorize native bypass.

Before replacing Shanling's grid, preserve downstream Home initialization
(buttons, touch, timers). These are validated MIPS anchors, not guesses at a
safe callable rehydration ABI. The report is data, never an installable patch.
"""
import argparse
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# -I excludes the script directory from sys.path. Import the audited sibling
# by an explicit file path rather than disabling Python isolation.
spec = importlib.util.spec_from_file_location('mox_cutover_audit',
                                              Path(__file__).with_name('mox_cutover_audit.py'))
assert spec and spec.loader
cut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cut)
# 0x534de4 is a MIPS bal, and its delay slot is 0x534de8.
GRID_DELAY_SLOT = 0x534DE8
TIMER_CALL = 0x534E54
TIMER_TARGET = 0x5349E4
# These are the $a1 event IDs set immediately before widget_on through jalr $t9.
# The first three are bound to the Home widget, the last eight (and other
# callbacks) belong to the remainder of home_page_init and must be preserved.
# A register call's semantics depend on the resolved GOT entry; no assumption
# that the whole tail is safely callable independently is made.
EVENT_BINDINGS = (
    (0x534DEC, 0x12C, 'home event 0x12c'),
    (0x534E0C, 0x12D, 'home event 0x12d'),
    (0x534E2C, 0x103, 'home event 0x103'),
    (0x534F70, 0x0FF, 'window-manager event 0xff'),
    (0x534F84, 0x101, 'window-manager event 0x101'),
    (0x534FA0, 0x103, 'window-manager pointer up'),
    (0x534FBC, 0x113, 'window-manager key up'),
    (0x534FD8, 0x110, 'window-manager long press'),
    (0x534FF4, 0x102, 'window-manager event 0x102'),
    (0x535010, 0x100, 'window-manager event 0x100'),
    (0x53502C, 0x104, 'window-manager event 0x104'),
)
# Anchors 0x534f70 and 0x534f84 depend on an alternate branch through 0x534f58;
# the register calls are validated by nearest following jalr, not assigned an
# entry count for every execution. Do not infer any handler runs unconditionally.


def word_at(blob, address):
    return struct.unpack_from('<I', blob, cut.elf_offset(blob, address))[0]


def is_addiu_a1(word, value):
    return ((word >> 26) == 9 and ((word >> 21) & 31) == 0
            and ((word >> 16) & 31) == 5 and (word & 0xFFFF) == value)


def is_jalr_t9(word):
    return (word >> 26) == 0 and ((word >> 21) & 31) == 25 and (word & 63) == 9


def inspect(blob):
    base = cut.analyze(blob)
    if not base['callsite_matches_known_v21']:
        raise ValueError('Constructor Shanling inesperado en 0x534de4')
    if word_at(blob, GRID_DELAY_SLOT) != 0x02002025:  # move a0, s0 in delay slot
        raise ValueError('Delay slot de constructor Shanling cambiado')
    if cut.direct_call_target(word_at(blob, TIMER_CALL), TIMER_CALL) != TIMER_TARGET:
        raise ValueError('Home timer call no coincide con V2.1')
    observed = []
    for addr, event, description in EVENT_BINDINGS:
        if not is_addiu_a1(word_at(blob, addr), event):
            raise ValueError(f'ID de evento inesperado en {addr:#x}: {event:#x}')
        # MIPS delays and GP loads occur between the argument and the call.
        # We know the nearest call is within 24 bytes in this V2.1 build.
        nearest = [pc for pc in range(addr + 4, addr + 28, 4)
                   if is_jalr_t9(word_at(blob, pc))]
        if not nearest:
            raise ValueError(f'No se encontró jalr $t9 después de {addr:#x}')
        observed.append({'id_site': hex(addr), 'event': hex(event),
                         'jalr_site': hex(nearest[0]), 'purpose': description})
    return {
        'binary_sha256': base['binary_sha256'],
        'grid_builder_call': {'site': hex(cut.GRID_BUILD_SITE),
                              'target': hex(cut.GRID_BUILDER),
                              'delay_slot': hex(GRID_DELAY_SLOT)},
        'post_grid_timer': {'site': hex(TIMER_CALL), 'target': hex(TIMER_TARGET)},
        'event_registration_sites': observed,
        'verified_event_sites': len(observed),
        'stock_initializer_still_needed': True,
        'on_demand_rehydration_verified': False,
        'bypass_authorized': False,
        'missing_evidence': [
            'safe late widget tree creation with no duplicate event handlers',
            'full path-specific stock Home side effects and persistent global state',
            'real-device touch/buttons/playback and cold-boot/recovery tests',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', type=Path,
                        default=ROOT / 'work/check/release/work/mod-release/rootfs/release/bin/demo')
    parser.add_argument('--report', type=Path, default=ROOT / 'out/mox-cutover/rehydration.json')
    args = parser.parse_args()
    if not args.demo.is_file():
        parser.error(f'Falta el ELF compilado: {args.demo}. Ejecuta make test TEST=home primero.')
    try:
        result = inspect(args.demo.read_bytes())
    except (ValueError, struct.error) as exc:
        parser.error(f'V2.1 incompatibilidad: {exc}')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'OK: {result["verified_event_sites"]} registros de eventos V2.1 posteriores a la cuadrícula')
    print(f'OK: timer de Home en {TIMER_CALL:#x} -> {TIMER_TARGET:#x}')
    print('BLOQUEADO: no se ha demostrado una reconstrucción tardía segura de Shanling')
    print('Informe:', args.report)


if __name__ == '__main__':
    main()
