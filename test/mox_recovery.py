#!/usr/bin/env python3
"""Native execution tests of the actual home.c fail-closed Home opening logic."""
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'patch/home.c').read_text()


def c_function(name):
    lines = source.splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines)
                  if line.startswith((f'static int {name}(',
                                      f'static void {name}(',
                                      f'void {name}(')) and '{' in line]
    assert len(candidates) == 1, (name, candidates)
    start = sum(len(line) for line in lines[:candidates[0]])
    brace = source.index('{', start)
    depth = 0
    for idx in range(brace, len(source)):
        if source[idx] == '{':
            depth += 1
        elif source[idx] == '}':
            depth -= 1
            if depth == 0:
                return source[start:idx + 1]
    raise AssertionError('Unterminated ' + name)


functions = '\n\n'.join(c_function(name) for name in (
    'hm_grid', 'hm_failure_grid', 'hm_is', 'hm_fill_window', 'hm_stock_rescue_ready', 'home_menu_opened',
    'hm_open', 'hm_painted', 'hm_clear',
))
stub = r'''
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define RET_OK 0
#define EVT_AFTER_PAINT 0x120
#define CLEAR_MS 5000
#define RETRY_MS 50
#define MAX_TRIES 100
#define HOME_PAD 8
#define SCREEN_W 320
#define WIN_H 450
#define POD_MENU_ROWS 26
#define GRID_ROOT "app_gesture"
#define BAD_NOTE "/mnt/data/m1plus-bad"
#define BAD_TMP BAD_NOTE ".tmp"
#define START_FILE "/mnt/data/m1plus-start"
#define START_TMP START_FILE ".tmp"

enum { H_NEW=0, H_OFF, H_ARMED, H_PROVEN };
static struct {
    int state, start, grid, pending;
    void *entry;
    int tries, as_home, home_valid, stock_painted, entry_painted;
    void *home, *menu, *extras;
} hs;

static int bad_written, start_written, marker_cleared, write_bad_fail, write_start_fail;
static int grid_last, grid_shows, grid_hides, opened, ready_window, skip_callback;
static int open_result, missing_navbar, missing_list, missing_scroll, missing_row, enabled, calls_to_open;
static int minis, pins, recent, daily, cover;
static int paint_register_ok, paint_register_calls, marker_clear_ok;
static char last_log[120];
static int win_home, win_entry, win_sview, win_pg, wm;
static int missing_grid, missing_sview, missing_pages, wrong_page_type;

void home_menu_opened(void *win, int settings, int entry);
static int hm_painted(void *ctx, void *unused);
static int m1plus_open_entry(void);
static int hm_ready(void) { return hs.state == H_ARMED || hs.state == H_PROVEN; }
static int home_off(void) { return !enabled; }
static void *window_manager(void) { return &wm; }
static void *window_manager_get_top_main_window(void *manager) { (void)manager; return &win_home; }
static int widget_is_window_opened(void *win) { (void)win; return ready_window; }
static int timer_add(int (*cb)(const void *), const void *ctx, unsigned ms) {
    (void)cb; (void)ctx; (void)ms; return 1;
}
static void *widget_lookup(void *win, const char *name, int deep) {
    (void)deep;
    if (win == &win_home) {
        if (!strcmp(name, GRID_ROOT)) return missing_grid ? NULL : &win_home;
        if (!strcmp(name, "home_sview")) return missing_sview ? NULL : &win_sview;
        return NULL;
    }
    if (!strcmp(name, "navigationbar_view")) return missing_navbar ? NULL : (void*)0x100;
    if (!strcmp(name, "pod_listview")) return missing_list ? NULL : (void*)0x101;
    if (!strcmp(name, "pod_scrollview")) return missing_scroll ? NULL : (void*)0x102;
    if (!strncmp(name, "pod_row", 7)) return missing_row && !strcmp(name, "pod_row11") ? NULL : (void*)0x104;
    if (!strcmp(name, "scroll_bar_m")) return (void*)0x103;
    return NULL;
}
static const char *widget_get_type(void *w) {
    if (w == &win_sview) return "slide_view";
    if (w == &win_pg) return wrong_page_type ? "button" : "view";
    return NULL;
}
static unsigned widget_count_children(void *w) { return w == &win_sview && !missing_pages ? 1 : 0; }
static void *widget_get_child(void *w, unsigned i) { return w == &win_sview && i == 0 ? &win_pg : NULL; }
static int widget_on(void *w, int ev, int (*cb)(void *, void *), void *ctx) {
    (void)w; (void)cb; (void)ctx;
    assert(ev == EVT_AFTER_PAINT);
    paint_register_calls++;
    return paint_register_ok;
}
static void widget_set_visible(void *w, int visible, int force) {
    (void)force;
    if (w == &win_home) { grid_last=visible; if (visible) grid_shows++; else grid_hides++; }
}
static void widget_set_sensitive(void *w, int sensitive) {(void)w; (void)sensitive;}
static void widget_move(void *w, int x, int y) {(void)w; (void)x; (void)y;}
static void widget_resize(void *w, int width, int height) {(void)w; (void)width; (void)height;}
static int widget_get_prop_int(void *w, const char *name, int d) {
    (void)name; (void)d; return w == (void*)0x103 ? 10 : 310;
}
static void minibar_start(void *w) {(void)w; minis++;}
static void pins_start(void *w) {(void)w; pins++;}
static void recent_start(void *w) {(void)w; recent++;}
static void dailymix_start(void *w) {(void)w; daily++;}
static void homecover_start(void *w) {(void)w; cover++;}
static int home_write_atomic(const char *path, const char *tmp, const char *data) {
    (void)tmp; (void)data;
    if (!strcmp(path, BAD_NOTE)) {if (write_bad_fail) return -1; bad_written++; return 0;}
    if (!strcmp(path, START_FILE)) {if (write_start_fail) return -1; start_written++; return 0;}
    assert(0 && "Unexpected write"); return -1;
}
static int hm_clear_marker(void) {marker_cleared++; return marker_clear_ok;}
static void hm_log(const char *msg) {snprintf(last_log, sizeof last_log, "%s", msg);}
static int m1plus_open_entry(void) {
    calls_to_open++;
    if (open_result) return open_result;
    if (!skip_callback) home_menu_opened(&win_entry, 0, 1);
    return 0;
}
'''
main = r'''
static void init(void) {
    memset(&hs, 0, sizeof hs);
    hs.state=H_ARMED; hs.start=1; hs.home=&win_home;
    bad_written=start_written=marker_cleared=write_bad_fail=write_start_fail=0;
    grid_last=0; grid_shows=grid_hides=0;
    opened=1; ready_window=1; skip_callback=0;
    open_result=0; missing_navbar=missing_list=missing_scroll=missing_row=0; enabled=1; calls_to_open=0;
    minis=pins=recent=daily=cover=0; last_log[0]=0;
    paint_register_ok=1; paint_register_calls=0; marker_clear_ok=1;
    missing_grid=missing_sview=missing_pages=wrong_page_type=0;
}
int main(void) {
    init();
    hm_open(NULL);
    assert(hs.home_valid == 1 && hs.grid == 0 && hs.state == H_ARMED);
    assert(grid_last == 0 && grid_hides == 1 && grid_shows == 0);
    assert(minis == 1 && pins == 1 && recent == 1 && daily == 1 && cover == 1);
    assert(!bad_written && !start_written && !marker_cleared);
    hm_painted(&win_entry, NULL);
    hm_clear(NULL);
    assert(marker_cleared == 1 && hs.state == H_PROVEN && hs.entry_painted);
    puts("OK: Home validado + AFTER_PAINT, marcador confirmado");

    init();
    hm_open(NULL);
    hm_clear(NULL);
    assert(hs.state == H_OFF && hs.grid && bad_written == 1 && start_written == 1);
    assert(marker_cleared == 1 && grid_shows == 1);
    puts("OK: sin AFTER_PAINT, deadline restaura Shanling");

    init();
    hm_open(NULL);
    hm_painted(&wm, NULL);
    hm_clear(NULL);
    assert(!hs.entry_painted && bad_written == 1 && hs.state == H_OFF);
    puts("OK: pintar otra ventana no confirma MOX");

    init();
    hm_open(NULL);
    hm_painted(&win_entry, NULL);
    ready_window=0; hm_clear(NULL);
    assert(hs.state == H_OFF && bad_written == 1);
    puts("OK: una ventana ya cerrada no confirma MOX");

    init();
    hs.start=0;
    hm_painted(&win_home, NULL);
    hm_clear(NULL);
    assert(hs.state == H_PROVEN && hs.stock_painted && !bad_written);
    puts("OK: Shanling también necesita un AFTER_PAINT propio");

    init();
    hs.start=0;
    hm_painted(&win_entry, NULL);
    hm_clear(NULL);
    assert(hs.state == H_OFF && bad_written == 1);
    puts("OK: el pintado de MOX no confirma Shanling");

    init();
    hm_open(NULL);
    hm_painted(&win_entry, NULL);
    marker_clear_ok=0; hm_clear(NULL);
    assert(hs.state == H_ARMED && marker_cleared == 1 && !bad_written);
    puts("OK: fallo al sincronizar el marcador no declara arranque seguro");

    init(); paint_register_ok=0;
    hm_open(NULL);
    assert(hs.state == H_OFF && bad_written == 1 && grid_last == 1);
    puts("OK: sin observador de pintado, Shanling restaurado");

    init();
    hm_open(NULL);
    write_bad_fail=1; hm_clear(NULL);
    assert(hs.state == H_OFF && grid_shows == 1 && marker_cleared == 0);
    puts("OK: deadline sin nota persistente conserva marcador para próximo arranque");

    init(); missing_grid=1;
    hm_open(NULL);
    assert(hs.grid && hs.state == H_OFF && bad_written && !minis);
    puts("OK: sin raiz de la cuadricula no se acepta MOX");

    init(); missing_sview=1;
    hm_open(NULL);
    assert(hs.grid && hs.state == H_OFF && bad_written && !minis);
    puts("OK: sin slide_view no se acepta MOX");

    init(); missing_pages=1;
    hm_open(NULL);
    assert(hs.grid && hs.state == H_OFF && bad_written && !minis);
    puts("OK: sin paginas de rescate no se acepta MOX");

    init(); wrong_page_type=1;
    hm_open(NULL);
    assert(hs.grid && hs.state == H_OFF && bad_written && !minis);
    puts("OK: pagina de rescate invalida bloquea MOX");

    init(); missing_navbar=1;
    hm_open(NULL);
    assert(!hs.home_valid && hs.grid && hs.state == H_OFF && !hs.start);
    assert(grid_last == 1 && grid_shows == 1 && grid_hides == 0);
    assert(bad_written == 1 && start_written == 1 && marker_cleared == 1);
    hm_open(NULL);
    assert(calls_to_open == 1 && bad_written == 1);
    puts("OK: falta navbar -> Shanling restaurado + bloqueo persistente");

    init(); missing_list=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && hs.state == H_OFF);
    assert(minis == 0 && cover == 0);
    puts("OK: falta lista -> no se inicializan extras, Shanling restaurado");

    init(); missing_scroll=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && hs.state == H_OFF);
    puts("OK: falta scrollview -> se restaura Shanling");

    init(); missing_row=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && hs.state == H_OFF);
    puts("OK: falta fila intermedia -> se restaura Shanling");

    init(); open_result=-1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && hs.entry == NULL);
    puts("OK: fallo window_open -> recuperación persistente");

    init(); skip_callback=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && hs.entry == NULL);
    puts("OK: apertura 0 sin inicializar Home -> no se acepta éxito falso");

    init(); missing_navbar=1; write_bad_fail=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 0 && marker_cleared == 0);
    hm_clear(NULL);
    assert(marker_cleared == 0 && hs.state == H_OFF);
    puts("OK: fallo guardando nota -> marcador permanece para recuperar en reinicio");

    init(); missing_navbar=1; write_start_fail=1;
    hm_open(NULL);
    assert(grid_last == 1 && bad_written == 1 && !start_written && marker_cleared == 1);
    puts("OK: nota persistente aunque falle guardar Start-in");

    init(); enabled=0;
    hm_open(NULL);
    assert(!calls_to_open && !bad_written && hs.state == H_ARMED);
    puts("OK: interruptor de emergencia impide abrir Home");

    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='mox-recovery-') as temp:
    src = Path(temp)/'mox_recovery.c'
    exe = Path(temp)/'mox_recovery'
    src.write_text(stub + '\n' + functions + '\n' + main)
    cc = ['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', str(src), '-o', str(exe)]
    result = subprocess.run(cc, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Host-C compilation failed:\n{result.stderr}")
    subprocess.run([str(exe)], check=True)

assert 'hm_failure_grid("m1plus: Home layout or stock rescue grid incomplete' in source
assert 'if (m1plus_open_entry() != 0 || !hs.home_valid)' in source
assert 'hs.state = H_OFF;' in c_function('hm_failure_grid')
assert 'widget_on(win, EVT_AFTER_PAINT, hm_painted, win)' in source
assert 'if (!ready)' in c_function('hm_clear')
print('MOX recuperación: 22/22 native C tests + 5 integration checks OK')
