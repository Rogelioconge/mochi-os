#!/usr/bin/env python3
"""Read-only V2.1 grid builder ABI check: verifies *two* arguments and PIC.

This does NOT establish safe late invocation, callback idempotence, or allow bypass.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mox_cutover_audit', Path(__file__).with_name('mox_cutover_audit.py'))
assert spec and spec.loader
cut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cut)

CHECKS = {
    0x534DD4: (0x24050001, 'caller passes $a1=1'),
    0x534DE0: (0x27394064, 'caller sets $t9 low address'),
    0x534DE8: (0x02002025, 'delay slot passes Home window in $a0'),
    0x534064: (0x3C1C004D, 'builder PIC gp prologue (lui)'),
    0x534068: (0x279CFE6C, 'builder PIC gp prologue (addiu)'),
    0x53406C: (0x0399E021, 'builder PIC gp prologue (addu $gp,$gp,$t9)'),
    0x534080: (0x00A0A825, 'builder saves $a1 into $s5'),
    0x53414C: (0x12A00015, 'builder branches on $s5'),
    0x5340E0: (0x24020010, 'builder error result 0x10'),
    0x5341C8: (0x00001025, 'builder success result zero'),
}


def inspect(blob):
    base = cut.analyze(blob)
    if not base['callsite_matches_known_v21']:
        raise ValueError('Unexpected grid constructor target')
    mismatches = []
    for addr, (expected, meaning) in CHECKS.items():
        got = int.from_bytes(blob[cut.elf_offset(blob, addr):cut.elf_offset(blob, addr)+4], 'little')
        if got != expected:
            mismatches.append(f'{meaning} at {addr:#x}: {got:#x} instead of {expected:#x}')
    if mismatches:
        raise ValueError('; '.join(mismatches))
    return {
        'binary_sha256': base['binary_sha256'],
        'builder_address': hex(cut.GRID_BUILDER),
        'verified_argc': 2,
        'a0': 'Home widget pointer',
        'a1': 1,
        'pic_requirement': '$t9 must equal the builder entry address',
        'success_return': 0,
        'failure_return_observed': '0x10',
        'verified_instruction_anchors': len(CHECKS) + 1,
        'late_reentry_safety_proven': False,
        'registered_event_idempotence_proven': False,
        'runtime_rollback_proven': False,
        'linked_into_firmware': False,
        'bypass_authorized': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', type=Path,
                        default=ROOT/'work/check/release/work/mod-release/rootfs/release/bin/demo')
    parser.add_argument('--report', type=Path,
                        default=ROOT/'out/mox-cutover/rebuild-contract.json')
    args = parser.parse_args()
    if not args.demo.is_file():
        parser.error(f'Missing built ELF: {args.demo}; run make test TEST=home')
    report = inspect(args.demo.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('OK: MIPS V2.1 builder ABI requires (Home window, 1) and PIC $t9')
    print('OK: builder returns 0 on success, 0x10 for at least one failure path')
    print('BLOQUEADO: calling the builder late and native bypass still unverified')
    print('Report:', args.report)


if __name__ == '__main__':
    main()
