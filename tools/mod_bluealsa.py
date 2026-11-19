#!/usr/bin/env python3
"""bluealsa's AAC source capability without 44.1 kHz (docs/modules/bluetooth.md "AAC at 48 kHz").

The player always feeds stock bluealsa (bluez-alsa v4.0.0, Shanling's build) 48 kHz. A link the player opens picks
48 kHz AAC, but a headset or speaker that opens the A2DP stream itself (AirPods taken out of the case, a speaker
reopening it after idling through a long pause) picks 44.1 kHz. bluealsa then drops about 8% of the AAC frames, so
the audio stutters rhythmically and sounds fast until Bluetooth reconnects (issue 15).

The source capability (object type, sampling frequencies, channels, VBR and bitrate) is `c0 01 84 84 e2 00` at file
offset 0x317b7. Octet 1 holds 8 to 44.1 kHz with 44.1 kHz in bit 0; octet 2's top bit is 48 kHz. Clearing octet 1
leaves 48 kHz, which every AAC sink must support. The same binary and fix as q2-pod's (docs/internals.md
"Bluetooth AAC", DiamondBond/q2-pod, MIT). SBC and the other codecs are unchanged.

A capability bit, not a hook: the kill switch does not restore it.

Usage: mod_bluealsa.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, sha256, write_keep_mode

REL = 'usr/bin/bluealsa'
STOCK_SHA = '0a4ffb7cc8207a46a3568440c5f31022b7125befd164e2f1af52537340a9892a'
AAC_CAPS, AAC_STOCK = 0x317b7, bytes.fromhex('c00184 84e200'.replace(' ', ''))
AAC_44K1 = AAC_CAPS + 1   # octet 1: 0x01 (44.1 kHz only) -> 0x00


def patch(data):
    """The stock binary's bytes -> ours; ValueError on anything but the pinned stock file."""
    if sha256(data) != STOCK_SHA: raise ValueError(f'{REL}: not the pinned stock binary')
    if data[AAC_CAPS:AAC_CAPS + len(AAC_STOCK)] != AAC_STOCK or data.count(AAC_STOCK) != 1:
        raise ValueError(f'{REL}: the AAC capability is not at {AAC_CAPS:#x}')
    out = bytearray(data)
    out[AAC_44K1] = 0
    return bytes(out)


def apply(out):
    path = os.path.join(out, 'rootfs', REL)
    write_keep_mode(path, patch(open(path, 'rb').read()))
    print(f'bluealsa: AAC source capability without 44.1 kHz ({AAC_44K1:#x})')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
