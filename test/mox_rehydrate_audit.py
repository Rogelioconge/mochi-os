#!/usr/bin/env python3
"""Synthetic ELF mutation tests of the read-only stock Home dependencies."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mox_rehydrate_audit as audit  # noqa: E402

LOAD_VA = 0x530000
FILE_OFF = 0x100


def fake_elf():
    data = bytearray(0x13200)
    data[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<I', data, 28, 52)
    struct.pack_into('<HH', data, 42, 32, 1)
    struct.pack_into('<8I', data, 52, 1, FILE_OFF, LOAD_VA, 0, 0x13000, 0x13000, 5, 0x1000)
    put(data, audit.cut.GRID_BUILD_SITE,
        (1 << 26) | (17 << 16) |
        (((audit.cut.GRID_BUILDER - audit.cut.GRID_BUILD_SITE - 4) // 4) & 0xFFFF))
    put(data, audit.GRID_DELAY_SLOT, 0x02002025)
    put(data, audit.TIMER_CALL, (1 << 26) | (17 << 16) |
        (((audit.TIMER_TARGET - audit.TIMER_CALL - 4) // 4) & 0xFFFF))
    for addr, event, _ in audit.EVENT_BINDINGS:
        put(data, addr, 0x24050000 | event)
        put(data, addr + (4 if addr == 0x534F70 else
                          24 if addr == 0x534DEC else
                          20 if addr in (0x534E0C, 0x534E2C) else 12),
            0x0320F809)  # jalr t9
    return data


def put(data, pc, word):
    struct.pack_into('<I', data, FILE_OFF + pc - LOAD_VA, word)


def must_reject(data, context):
    try:
        audit.inspect(data)
    except ValueError:
        print('OK:', context)
    else:
        raise AssertionError('Unsafe ELF accepted: ' + context)


def main():
    stock = fake_elf()
    report = audit.inspect(stock)
    assert report['verified_event_sites'] == 11
    assert not report['bypass_authorized'] and not report['on_demand_rehydration_verified']
    print('OK: once-verified synthetic V2.1 dependencies remain blocked')
    modified = bytearray(stock)
    put(modified, audit.cut.GRID_BUILD_SITE, 0)
    must_reject(modified, 'different grid call')
    modified = bytearray(stock)
    put(modified, audit.GRID_DELAY_SLOT, 0)
    must_reject(modified, 'changed grid call delay slot')
    modified = bytearray(stock)
    put(modified, audit.TIMER_CALL, 0)
    must_reject(modified, 'missing Home timer')
    modified = bytearray(stock)
    put(modified, 0x534FBC, 0x24050114)
    must_reject(modified, 'changed key-up event')
    modified = bytearray(stock)
    put(modified, 0x534FD8 + 12, 0)
    must_reject(modified, 'missing long-press callback registration')
    modified = bytearray(stock)
    put(modified, 0x534E2C, 0)
    must_reject(modified, 'missing stock Home event ID')
    must_reject(b'not an ELF', 'invalid executable')
    assert len(report['event_registration_sites']) == len(audit.EVENT_BINDINGS)
    print('MOX read-only rehydration dependency audit: 8/8 tests OK; bypass blocked')


if __name__ == '__main__':
    main()
