#!/usr/bin/env python3
"""Native smoke tests of real menu_mox_select/menu_mox_reset C functions."""
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'patch/menu.c').read_text()
start = source.index('static unsigned mn_mox_active ')
end = source.index('\n}\n', source.index('void menu_mox_reset(void *win) {', start)) + 2
# Mach-O on macOS does not accept the ELF-only linker section name.
# Remove only that placement attribute for the isolated host C test.
functions = source[start:end].replace(' __attribute__((section(".scratch")))', '')

stub = r"""
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define N 25
struct Card { char state[24]; int calls; };
struct Row { struct Card card; int visible; };
struct Win { struct Row rows[N+1]; };
static void *mn_find(void *ctx, const char *name, unsigned i) {
    if (i > N || !ctx) return 0;
    if (!strcmp(name, "pod_row")) return &((struct Win*)ctx)->rows[i];
    if (!strcmp(name, "mox_card")) return &((struct Row*)ctx)->card;
    return 0;
}
static int widget_get_visible(void *row) { return ((struct Row*)row)->visible; }
static void widget_set_state(void *card, const char *state) {
    struct Card *c = card;
    snprintf(c->state, sizeof c->state, "%s", state);
    c->calls++;
}
"""
main = r"""
int main(void) {
    struct Win w = {0};
    unsigned i;
    for (i = 0; i <= N; ++i) w.rows[i].visible = 1;
    menu_mox_reset(&w);
    assert(strcmp(w.rows[1].card.state, "normal") == 0);
    puts("OK: sin selección, tarjetas normales");
    menu_mox_select(1);
    menu_mox_reset(&w);
    assert(strcmp(w.rows[1].card.state, "focused") == 0);
    assert(strcmp(w.rows[2].card.state, "normal") == 0);
    puts("OK: Cover Flow seleccionado");
    menu_mox_select(2);
    menu_mox_reset(&w);
    assert(strcmp(w.rows[1].card.state, "normal") == 0);
    assert(strcmp(w.rows[2].card.state, "focused") == 0);
    puts("OK: selección cambia de fila");
    w.rows[2].visible = 0;
    menu_mox_reset(&w);
    assert(strcmp(w.rows[2].card.state, "normal") == 0);
    puts("OK: filas ocultas no se resaltan");
    w.rows[2].visible = 1;
    menu_mox_reset(&w);
    assert(strcmp(w.rows[2].card.state, "focused") == 0);
    puts("OK: foco recuperado después de mostrar fila");
    menu_mox_select(N);
    menu_mox_reset(&w);
    assert(strcmp(w.rows[N].card.state, "focused") == 0);
    puts("OK: Extras también registra selección");
    menu_mox_select(N+1);
    menu_mox_reset(&w);
    assert(strcmp(w.rows[N].card.state, "normal") == 0);
    puts("OK: índice fuera de rango limpia selección");
    menu_mox_select(1);
    menu_mox_reset(0);
    assert(strcmp(w.rows[N].card.state, "normal") == 0);
    puts("OK: ventana nula no se toca");
    return 0;
}
"""
with tempfile.TemporaryDirectory(prefix='mox-nav-') as d:
    path = Path(d)
    c = path / 'mox_nav.c'
    exe = path / 'mox_nav'
    c.write_text(stub + '\n' + functions + '\n' + main)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-std=c99', str(c), '-o', str(exe)],
                          check=True, capture_output=True, text=True)
    subprocess.run([str(exe)], check=True)

route = (ROOT / 'patch/m1plus.c').read_text()
assert 'if (row == &menu->rows[i])' in route, 'No se distingue el menú de otras páginas'
assert 'menu_mox_select((unsigned)i);' in route, 'Falta registrar el tap en Home'
assert 'menu_arrange(ctx, 0);\n    menu_mox_reset(ctx);' in route, 'El foco debe restaurarse después del layout'
print('MOX navegación: 8/8 C checks + 3 wiring checks OK')
