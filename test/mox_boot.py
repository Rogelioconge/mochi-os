"""Native MOX boot eligibility tests using the actual C function."""

import ctypes
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "patch/home.c").read_text()

signature = "static int __attribute__((unused)) mox_boot_candidate(void) {"
assert source.count(signature) == 1

start = source.index(signature)
end = source.index("\n}\n", start) + 2
function = source[start:end]

stub = r"""
#include <string.h>

#define MARKER "/mnt/data/m1plus-run"
#define BAD_NOTE "/mnt/data/m1plus-bad"

static int selected, disabled, marker, bad, enabled;

void set_flags(int s, int d, int m, int b, int e) {
    selected = s;
    disabled = d;
    marker = m;
    bad = b;
    enabled = e;
}

int home_off(void) {
    return disabled;
}

int hm_exists(const char *p) {
    if (strcmp(p, MARKER) == 0) return marker;
    if (strcmp(p, BAD_NOTE) == 0) return bad;
    if (strcmp(p, "/mnt/mmc/mox-native-enable") == 0) return enabled;
    return 0;
}

int hm_read_start(void) {
    return selected;
}
"""

with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "probe.c"
    lib = Path(tmp) / "probe.dylib"

    src.write_text(
        stub + "\n" + function +
        "\nint probe(void) { return mox_boot_candidate(); }\n"
    )

    subprocess.run(
        ["cc", "-dynamiclib", "-o", str(lib), str(src)],
        check=True,
    )

    mox = ctypes.CDLL(str(lib))
    mox.set_flags.argtypes = [ctypes.c_int] * 5
    mox.probe.restype = ctypes.c_int

    cases = [
        ("MOX habilitado", (1, 0, 0, 0, 1), 1),
        ("Sin permiso en microSD", (1, 0, 0, 0, 0), 0),
        ("Shanling seleccionado", (0, 0, 0, 0, 1), 0),
        ("Interruptor de emergencia", (1, 1, 0, 0, 1), 0),
        ("Arranque anterior pendiente", (1, 0, 1, 0, 1), 0),
        ("Fallo anterior registrado", (1, 0, 0, 1, 1), 0),
    ]

    for name, flags, expected in cases:
        mox.set_flags(*flags)
        result = mox.probe()
        assert result == expected, f"{name}: {result} != {expected}"
        print(f"OK: {name}")

print("MOX: 6/6 pruebas del selector superadas")
