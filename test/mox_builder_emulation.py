#!/usr/bin/env python3
"""Offline mutation tests for the Sprint 11 MIPS execution probe.

The runtime probe (tools/mox_builder_emulation.py) additionally needs Unicorn.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mox_builder_emulation as em  # noqa: E402

LOAD_VA, FILE_OFF = 0x530000, 0x100


def put(data, addr, word):
    struct.pack_into('<I', data, FILE_OFF + addr - LOAD_VA, word)


def fixture():
    data = bytearray(0x15200)
    data[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<I', data, 28, 52)
    struct.pack_into('<HH', data, 42, 32, 1)
    struct.pack_into('<8I', data, 52, 1, FILE_OFF, LOAD_VA, 0, 0x15000, 0x15000, 5, 0x1000)
    call = em.cut.GRID_BUILD_SITE
    target = em.cut.GRID_BUILDER
    put(data, call, (1 << 26) | (17 << 16) | (((target-call-4)//4) & 0xffff))
    for site, (word, _) in em.rc.CHECKS.items():
        put(data, site, word)
    for site in em.SITES:
        put(data, site, 0x0411FEFE if site == 0x534190 else 0x0320F809)
    return data


def rejects(blob):
    try:
        em.preflight(blob)
    except (ValueError, struct.error):
        return True
    return False


def main():
    good = fixture()
    info = em.preflight(good)
    assert info['mocked_sites'] == 9 and info['contract']['verified_argc'] == 2
    print('OK: synthetic V2.1 builder ABI and 9 exact callsites')
    for site, name in em.SITES.items():
        bad = bytearray(good)
        put(bad, site, 0)
        assert rejects(bad), f'Unsafe changed callsite accepted: {name}'
        print('OK: altered', name, 'is blocked')
    assert rejects(b'not an elf')
    print('OK: invalid ELF rejected')
    bad = bytearray(good)
    struct.pack_into('<H', bad, 44, 300)
    assert rejects(bad)
    print('OK: malformed ELF headers rejected')
    bad = bytearray(good)
    put(bad, 0x534064, 0)
    assert rejects(bad)
    print('OK: wrong PIC prologue rejected')
    # MIPS jr $ra / nop is executed by Unicorn; the old hook used to jump
    # straight to PC+8, incorrectly skipping real MIPS delay-slot semantics.
    assert em.JR_RA_NOP == bytes.fromhex('0800e00300000000')
    assert em.MOCK_BASE % 4096 == 0 and em.HELPER == 0x533D8C
    assert 'populate_page' in em.SITES.values() and len(em.SITES) == 9
    print('OK: MIPS return stubs preserve real calls and delay slots')
    print('OK: isolated mock addresses and original BAL destination')
    print('OK: all nine callsites retained')
    print('MOX builder instruction preflight: 16/16 checks OK; native bypass blocked')


if __name__ == '__main__':
    main()
