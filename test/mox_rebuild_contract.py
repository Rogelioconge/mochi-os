#!/usr/bin/env python3
"""Mutation tests for the two-argument stock MIPS grid builder ABI."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mox_rebuild_contract as rc  # noqa: E402

LOAD_VA, FILE_OFF = 0x530000, 0x100

def put(data, address, word):
    struct.pack_into('<I', data, FILE_OFF + address - LOAD_VA, word)


def fake_elf():
    data = bytearray(0x15200)
    data[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<I', data, 28, 52)
    struct.pack_into('<HH', data, 42, 32, 1)
    struct.pack_into('<8I', data, 52, 1, FILE_OFF, LOAD_VA, 0, 0x15000, 0x15000, 5, 0x1000)
    put(data, rc.cut.GRID_BUILD_SITE, (1 << 26) | (17 << 16) | (((rc.cut.GRID_BUILDER - rc.cut.GRID_BUILD_SITE - 4) // 4) & 0xFFFF))
    for address, (word, _) in rc.CHECKS.items():
        put(data, address, word)
    return data


def check_reject(data, what):
    try:
        rc.inspect(data)
    except ValueError:
        print('OK: rejects', what)
    else:
        raise AssertionError('Unsafe MIPS ABI accepted: ' + what)


def main():
    valid = fake_elf()
    r = rc.inspect(valid)
    assert r['verified_argc'] == 2 and r['a1'] == 1 and not r['bypass_authorized']
    print('OK: known-good two-argument MIPS ABI')
    cases = (
        (0x534DD4, 'missing flag=1'),
        (0x534DE0, 'wrong $t9 setup'),
        (0x534DE8, 'wrong Home pointer'),
        (0x534064, 'changed builder prologue'),
        (0x534068, 'changed PIC adjustment'),
        (0x53406C, 'wrong PIC $gp calculation'),
        (0x534080, 'missing $a1 save'),
        (0x53414C, 'missing $s5 branch'),
        (0x5340E0, 'wrong failure convention'),
        (0x5341C8, 'wrong success convention'),
        (0x534DE4, 'wrong call target'),
    )
    for addr, label in cases:
        mutated = bytearray(valid)
        put(mutated, addr, 0)
        check_reject(mutated, label)
    check_reject(b'not an ELF', 'invalid binary')
    print('MOX builder ABI: 13/13 mutation checks OK; bypass blocked')


if __name__ == '__main__':
    main()
