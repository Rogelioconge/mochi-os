#!/usr/bin/env python3
"""Native C smoke tests: MOX card press feedback doesn't consume row actions."""
import ctypes
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'patch/menu.c').read_text()
signature = 'static int mn_mox_touch(void *ctx, void *e) {'
assert source.count(signature) == 1
start = source.index(signature)
end = source.index('\n}\n', start) + 2
function = source[start:end]

stub = r'''
#include <string.h>
#define RET_OK 0
#define EVT_POINTER_DOWN 0xff
#define EVT_POINTER_UP 0x103
#define EVT_POINTER_ABORT 0x107
struct card { char state[16]; int calls; };
void widget_set_state(void *v, const char *s) {
    struct card *c = v;
    strncpy(c->state, s, sizeof c->state - 1);
    c->state[sizeof c->state - 1] = 0;
    c->calls++;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src = base / 'probe.c'
    lib = base / ('probe.dylib' if sys.platform == 'darwin' else 'probe.so')
    src.write_text(stub + function + '\nint probe(void *v, int e) { return mn_mox_touch(v, &e); }\n'
                   + 'int null_probe(int e) { return mn_mox_touch(0, &e); }\n')
    cmd = ['cc', '-dynamiclib'] if sys.platform == 'darwin' else ['cc', '-shared', '-fPIC']
    subprocess.run([*cmd, '-o', str(lib), str(src)], check=True, capture_output=True)
    native = ctypes.CDLL(str(lib))
    native.probe.argtypes = [ctypes.c_void_p, ctypes.c_int]
    native.probe.restype = ctypes.c_int
    native.null_probe.argtypes = [ctypes.c_int]
    native.null_probe.restype = ctypes.c_int

    class Card(ctypes.Structure):
        _fields_ = [('state', ctypes.c_char * 16), ('calls', ctypes.c_int)]

    card = Card()
    cases = ((0xff, b'pressed', 1), (0x103, b'normal', 2),
             (0xff, b'pressed', 3), (0x107, b'normal', 4))
    for ev, expected, num in cases:
        assert native.probe(ctypes.byref(card), ev) == 0
        assert card.state == expected and card.calls == num, (ev, card.state, card.calls)
    assert native.probe(ctypes.byref(card), 0x999) == 0 and card.calls == 4
    assert native.null_probe(0xff) == 0
    print('MOX touch: 6/6 native event tests OK')

# Verifications are complementary to the C smoke test; they do not establish
# device-level interaction safety or MIPS timing.
assert 'menu_mox_bind(win);' in (ROOT / 'patch/m1plus.c').read_text()
assert 'menu_mox_reset(ctx);' in (ROOT / 'patch/m1plus.c').read_text()
assert 'EVT_CLICK' not in function
