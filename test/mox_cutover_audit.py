#!/usr/bin/env python3
"""Offline structural checks for the read-only native launcher audit."""
import sys
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mox_cutover_audit as audit  # noqa: E402


def fake_elf(site_word, load_va=0x530000):
    blob = bytearray(0x9000)
    blob[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<I', blob, 28, 52)  # program headers
    struct.pack_into('<HH', blob, 42, 32, 1)
    struct.pack_into('<8I', blob, 52, 1, 0x100, load_va, 0, 0x7000, 0x7000, 5, 0x1000)
    struct.pack_into('<I', blob, 0x100 + audit.GRID_BUILD_SITE - load_va, site_word)
    return bytes(blob)


def bal(pc, target):
    delta = target - (pc + 4)
    assert delta % 4 == 0
    return (1 << 26) | (17 << 16) | ((delta // 4) & 0xFFFF)


pc, target = audit.GRID_BUILD_SITE, audit.GRID_BUILDER
assert audit.direct_call_target(bal(pc, target), pc) == target
print('OK: salto bal negativo decodificado correctamente')
assert audit.direct_call_target(bal(pc, pc + 8), pc) == pc + 8
print('OK: salto bal positivo decodificado correctamente')
assert audit.direct_call_target((3 << 26) | (target >> 2), pc) == target
print('OK: jal decodificado correctamente')
assert audit.direct_call_target(0, pc) is None
print('OK: instrucciones no llamadas no se aceptan')
report = audit.analyze(fake_elf(bal(pc, target)))
assert report['callsite_matches_known_v21'] and not report['bypass_authorized']
print('OK: llamada esperada localizada sin habilitar el bypass')
report = audit.analyze(fake_elf(bal(pc, target + 8)))
assert not report['callsite_matches_known_v21'] and not report['bypass_authorized']
print('OK: cambio inesperado de destino detectado')
for broken in (b'', b'HELLO', bytes(52)):
    try:
        audit.elf_offset(broken, pc)
        raise AssertionError('Malformed ELF accepted')
    except ValueError:
        pass
print('OK: formatos ELF inválidos rechazados')
print('MOX cutover: 7/7 pruebas offline OK; bypass bloqueado')
