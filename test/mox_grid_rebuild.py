#!/usr/bin/env python3
"""Compile and execute the real C grid-rehydration *probe* with fake AWTK widgets.

No firmware is generated. This is NOT a MIPS or device integration test.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = r'''#include <assert.h>
#include <stdio.h>
#include "mox_grid_rebuild.h"
static struct {int root, slide, count, valid, status, calls, last_flag, reenter;} fake;
static mox_rebuild_state state;
static const mox_rebuild_ops *current_ops;
static int root_present(void *w){(void)w; return fake.root;}
static int slide_present(void *w){(void)w; return fake.slide;}
static int page_count(void *w){(void)w; return fake.count;}
static int pages_valid(void *w){(void)w; return fake.valid;}
static int build_pages(void *w, int flag){
    fake.calls++; fake.last_flag=flag;
    if(fake.reenter) assert(mox_rebuild_stock_grid_probe(w,&state,current_ops)==MOX_REBUILD_BLOCKED);
    if(fake.status==0){fake.count=1; fake.valid=1;}
    if(fake.status==2){fake.count=1; fake.valid=0;}
    return fake.status==2 ? 0 : fake.status;
}
static const mox_rebuild_ops ops={root_present,slide_present,page_count,pages_valid,build_pages};
static void reset(void){
    fake=(typeof(fake)){.root=1,.slide=1,.count=0,.valid=0,.status=0,.calls=0,.last_flag=-1,.reenter=0};
    state=(mox_rebuild_state){0}; current_ops=&ops;
}
int main(void){
    int home=1;
    reset();
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_RECONSTRUCTED);
    assert(fake.calls==1 && fake.last_flag==1 && state.attempted);
    puts("OK: empty valid grid rebuilt once with ABI flag=1");
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_ALREADY_READY && fake.calls==1);
    puts("OK: already rebuilt grid is idempotent");
    reset(); fake.count=2; fake.valid=1;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_ALREADY_READY && !fake.calls);
    puts("OK: intact grid never rebuilt");
    reset(); fake.count=1; fake.valid=0;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && !fake.calls);
    puts("OK: malformed partial grid fails closed");
    reset(); fake.root=0;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && !fake.calls);
    puts("OK: absent stock root blocks reconstruction");
    reset(); fake.slide=0;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && !fake.calls);
    puts("OK: absent slide_view blocks reconstruction");
    reset(); fake.count=-1;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && !fake.calls);
    puts("OK: invalid page count blocks reconstruction");
    reset(); fake.count=9;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && !fake.calls);
    puts("OK: too many pages block reconstruction");
    reset(); fake.status=-1;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && state.attempted);
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && fake.calls==1);
    puts("OK: builder failure cannot cause repeated writes");
    reset(); fake.status=2;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && state.attempted);
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_BLOCKED && fake.calls==1);
    puts("OK: incomplete rebuild is never accepted or retried");
    reset(); fake.reenter=1;
    assert(mox_rebuild_stock_grid_probe(&home,&state,&ops)==MOX_REBUILD_RECONSTRUCTED && fake.calls==1);
    puts("OK: reentrant builder attempt is blocked");
    reset();
    assert(mox_rebuild_stock_grid_probe(NULL,&state,&ops)==MOX_REBUILD_BLOCKED);
    assert(mox_rebuild_stock_grid_probe(&home,NULL,&ops)==MOX_REBUILD_BLOCKED);
    assert(mox_rebuild_stock_grid_probe(&home,&state,NULL)==MOX_REBUILD_BLOCKED);
    puts("OK: invalid pointer arguments are rejected");
    puts("MOX late grid C probe: 12/12 tests OK (NOT connected to firmware)");
    return 0;
}
'''


def main():
    compiler = shutil.which('clang') or shutil.which('cc')
    if not compiler:
        raise RuntimeError('Missing a native C compiler (clang or cc)')
    with tempfile.TemporaryDirectory(prefix='mox-grid-') as tmp:
        src, exe = Path(tmp) / 'probe.c', Path(tmp) / 'probe'
        src.write_text(TEST)
        subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'patch'), str(src),
                        str(ROOT / 'patch/mox_grid_rebuild.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
