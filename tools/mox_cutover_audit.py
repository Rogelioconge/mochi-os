#!/usr/bin/env python3
"""Read-only audit of Shanling's grid-builder call; never edits the firmware.

The call alone cannot justify removing the stock initializer: it has other
side effects, and the current recovery path relies on its widget tree.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK_HOME_INIT = 0x534CD4
GRID_BUILD_SITE = 0x534DE4
GRID_BUILDER = 0x534064


def elf_offset(blob, address):
    """Resolve VA using ELF32 LE PT_LOAD program headers, no external tools."""
    if len(blob) < 52 or blob[:4] != b'\x7fELF' or blob[4:6] != b'\x01\x01':
        raise ValueError('Expected a 32-bit little-endian ELF')
    phoff = struct.unpack_from('<I', blob, 28)[0]
    entsize, count = struct.unpack_from('<HH', blob, 42)
    if entsize != 32 or count > 256 or phoff + count * entsize > len(blob):
        raise ValueError('Invalid ELF program header table')
    for i in range(count):
        p_type, p_off, p_va, _, p_size, _, _, _ = struct.unpack_from('<8I', blob, phoff + i * entsize)
        if p_type == 1 and p_va <= address < p_va + p_size:
            off = p_off + address - p_va
            if off + 4 > len(blob) or off + 4 > p_off + p_size:
                raise ValueError(f'Unmapped/truncated instruction at {address:#x}')
            return off
    raise ValueError(f'Address {address:#x} is outside file-backed PT_LOAD segments')


def direct_call_target(word, pc):
    """MIPS32 little-endian jal or bal ($zero,bgezal) -> absolute target."""
    op = word >> 26
    if op == 3:  # jal, same 256 MB region as the delay slot
        return ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
    if op == 1 and ((word >> 21) & 31) == 0 and ((word >> 16) & 31) == 17:
        imm = word & 0xFFFF
        if imm & 0x8000:
            imm -= 0x10000
        return (pc + 4 + (imm << 2)) & 0xFFFFFFFF
    return None


def analyze(blob):
    call_off = elf_offset(blob, GRID_BUILD_SITE)
    entry_off = elf_offset(blob, STOCK_HOME_INIT)
    builder_off = elf_offset(blob, GRID_BUILDER)
    word = struct.unpack_from('<I', blob, call_off)[0]
    target = direct_call_target(word, GRID_BUILD_SITE)
    expected = target == GRID_BUILDER
    return {
        'binary_sha256': hashlib.sha256(blob).hexdigest(),
        'home_hook_va': hex(STOCK_HOME_INIT),
        'home_entry_first_word': hex(struct.unpack_from('<I', blob, entry_off)[0]),
        'grid_build_call_va': hex(GRID_BUILD_SITE),
        'grid_build_call_word': hex(word),
        'decoded_target': hex(target) if target is not None else None,
        'grid_builder_va': hex(GRID_BUILDER),
        'grid_builder_first_word': hex(struct.unpack_from('<I', blob, builder_off)[0]),
        'callsite_matches_known_v21': expected,
        'bypass_authorized': False,
        'reason': ('The page builder call is located; stock initializer side effects and '
                   'on-demand grid reconstruction remain unverified.'),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--demo', type=Path, default=ROOT / 'work/check/release/work/mod-release/rootfs/release/bin/demo')
    ap.add_argument('--report', type=Path, default=ROOT / 'out/mox-cutover/audit.json')
    args = ap.parse_args()
    if not args.demo.is_file():
        ap.error(f'Built demo not found: {args.demo}; run make test TEST=home first')
    result = analyze(args.demo.read_bytes())
    if not result['callsite_matches_known_v21']:
        print(f'FAIL: {GRID_BUILD_SITE:#x} does not call {GRID_BUILDER:#x}; actual: {result["decoded_target"]}')
        raise SystemExit(1)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(f'OK: llamada al constructor original {GRID_BUILDER:#x} identificada en {GRID_BUILD_SITE:#x}')
    print('BLOQUEADO: esta coincidencia NO autoriza omitir el inicializador Shanling')
    print(f'Informe: {args.report}')


if __name__ == '__main__':
    main()
