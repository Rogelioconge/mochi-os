#!/usr/bin/env python3
"""The card script runner: /usr/bin/m1plus-run (docs/modules/cardrun.md).

Stock has no shell on the network and the UART pads are not located, so a probe of the running system is a script on
the card: Settings > Developer > Tools > Card Script (patch/cardrun.c) runs m1plus-run, which runs a copy of
/mnt/mmc/m1plus-run.sh once and keeps /tmp/m1plus-run.pid, .exit and .log. Nothing runs at boot. The kill switch
/mnt/mmc/m1plus-off is not read: a probe has to run with the payload off too.
The script is assets/cardrun/m1plus-run, pinned here; no stock file changes.

Usage: mod_cardrun.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'cardrun', 'm1plus-run')
SHA = '1e96281c255cbc17c8ccea195bce47e78812382ce6f239382f0bbc1b29afdce0'
REL = 'usr/bin/m1plus-run'
MODE, MTIME = 0o755, 1750924035   # stock /usr/bin mode; a stock mtime, so the build is deterministic


def added_rels(stock_rootfs=None):
    return [REL]


def apply(out):
    data = open(SRC, 'rb').read()
    assert hashlib.sha256(data).hexdigest() == SHA, f'{SRC}: not the pinned script'
    path = os.path.join(out, 'rootfs', REL)
    assert not os.path.exists(path), path
    with open(path, 'wb') as f: f.write(data)
    os.chmod(path, MODE); os.utime(path, (MTIME, MTIME))
    print(f'cardrun: /{REL} ({len(data)} bytes)')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
