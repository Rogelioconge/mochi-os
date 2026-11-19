"""bluealsa's AAC capability without 44.1 kHz (tools/mod_bluealsa.py, docs/modules/bluetooth.md "AAC at 48 kHz"): the built
binary differs from stock in that one byte, keeps its mode and mtime, and the step refuses any other input."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_bluealsa as mb
import mod_wpa as mw


def run(ctx):
    expect = ctx.expect
    stock_path = os.path.join(mw.stock_root(), mb.REL)
    ours_path = os.path.join(WORK, 'rootfs', mb.REL)
    stock, ours = open(stock_path, 'rb').read(), open(ours_path, 'rb').read()

    # ---- the stock input ----
    expect(mb.sha256(stock) == mb.STOCK_SHA, 'the stock bluealsa is the pinned binary')
    expect(stock[mb.AAC_CAPS:mb.AAC_CAPS + 6] == bytes.fromhex('c0018484e200') and stock.count(mb.AAC_STOCK) == 1,
           'the AAC source capability is at 0x317b7 and only there: MPEG-2/4 LC, 44.1 kHz, 48 kHz stereo, VBR, 320 kb/s')

    # ---- the built tree ----
    diff = [i for i in range(len(stock)) if stock[i] != ours[i]] if len(stock) == len(ours) else None
    expect(diff == [mb.AAC_44K1] and ours[mb.AAC_44K1] == 0, 'ours differs from stock in octet 1 alone, now 0 (no 8..44.1 kHz)')
    expect(ours[mb.AAC_44K1 + 1] & 0x80 and ours[mb.AAC_44K1 + 1] & 0x0f == stock[mb.AAC_44K1 + 1] & 0x0f,
           '48 kHz and the channel bits are kept')
    s, o = os.stat(stock_path), os.stat(ours_path)
    expect((s.st_mode, int(s.st_mtime)) == (o.st_mode, int(o.st_mtime)), 'mode and mtime are stock\'s')
    expect(mb.patch(stock) == ours, 'the step is deterministic')

    # ---- refusals ----
    for what, bad in (('the patched binary', ours), ('a moved capability', stock[:mb.AAC_CAPS] + b'\0' + stock[mb.AAC_CAPS:-1])):
        try: mb.patch(bad); refused = False
        except ValueError: refused = True
        expect(refused, f'the step refuses {what}')
