#!/usr/bin/env python3
"""MOX OS: inspección y primer recurso de Inicio, sin tocar firmware.

Uso: uv run --locked python -I tools/mod_mox_home.py inspect [archivo.bin]
     uv run --locked python -I tools/mod_mox_home.py build ARCHIVO.bin SALIDA.bin
     uv run --locked python -I tools/mod_mox_home.py verify ORIGINAL.bin CANDIDATO.bin

Siempre preserva los IDs, jerarquía y geometría. Este módulo NO suprime el
launcher, no instala nada y no demuestra mejora de rendimiento. Un parche
posterior, con pruebas en emulador, será necesario para suprimir la creación
de la cuadrícula stock dentro de demo. No modificar S90play ni el trampoline.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile

# El módulo awtk_ui.py ya está incluido en M1+ Music 1.8.0.
import awtk_ui

REQUIRED = {
    'home_page': 'window',
    'app_gesture': 'gesture',
    'home_svview': 'view',
    'home_sview': 'slide_view',
    'home_sindicator': 'slide_indicator',
    'home_bottomview': 'view',
    'home_img_icon': 'image',
    'home_scrlabel_title': 'hscroll_label',
    'home_scrlabel_artist': 'hscroll_label',
    'label_snerr': 'label',
}

# Solo estilos visibles. NO retocar el umbral táctil ni animating_time sin
# mediciones en dispositivo: actualmente no hay línea base de latencia/FPS.
STYLES = {
    ('home_bottomview', 'style:normal:bg_color'): '#0B0B0D',
    ('home_sindicator', 'style:normal:selected_fg_color'): '#E8E8E8',
    ('home_sindicator', 'style:normal:fg_color'): '#555555',
    ('home_scrlabel_artist', 'style:normal:text_color'): '#A9A9AF',
    ('home_scrlabel_artist', 'style:normal:font_size'): '15',
    ('home_scrlabel_artist', 'style:disable:font_size'): '15',
    ('home_scrlabel_artist', 'style:focused:font_size'): '15',
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_resource(path: Path):
    raw = path.read_bytes()
    root = awtk_ui.parse(raw)
    if awtk_ui.serialize(root) != raw:
        raise ValueError('El recurso no supera el round-trip exacto; no se modifica')
    audit(root)
    return raw, root


def audit(root):
    nodes = list(root.walk())
    named = [n for n in nodes if n.name]
    idx = {}
    for n in named:
        if n.name in idx:
            raise ValueError(f'Nombre de control duplicado: {n.name}')
        idx[n.name] = n
    for name, typ in REQUIRED.items():
        if name not in idx or idx[name].type != typ:
            raise ValueError(f'Control incompatible: {name} debe ser {typ}')
    if root.name != 'home_page':
        raise ValueError('La raíz no es home_page')
    if idx['home_sview'] not in idx['home_svview'].children:
        raise ValueError('home_sview fuera de home_svview')
    if idx['home_sindicator'] not in idx['home_svview'].children:
        raise ValueError('home_sindicator fuera de home_svview')
    if idx['home_bottomview'] not in idx['app_gesture'].children:
        raise ValueError('home_bottomview fuera del contenedor esperado')
    if idx['home_sview'].children:
        raise ValueError('El .bin ya trae páginas estáticas: no se esperaba esta variante')
    return idx, nodes


def signature(root):
    # La firma captura el árbol completo, incluso widgets sin nombre,
    # y garantiza que los cambios no alteran la geometría ni los eventos.
    return [(n.type, n.name, n.x, n.y, n.w, n.h,
             tuple(k for k, _ in n.props), len(n.children)) for n in root.walk()]


def transform(root):
    before = signature(root)
    idx, _ = audit(root)
    for (name, prop), val in STYLES.items():
        node = idx[name]
        if node.get(prop) is None:
            raise ValueError(f'Falta la propiedad original {name}/{prop}')
        node.set(prop, val)
    if signature(root) != before:
        raise AssertionError('Se modificó geometría, nombres o jerarquía')
    return root


def report(path: Path):
    data, root = read_resource(path)
    idx, nodes = audit(root)
    print('AWTK home_page.bin:', len(data), 'bytes; SHA-256:', sha(data))
    print('Controles:', len(nodes), '; IDs:', len(idx))
    print('home_sview: 0 páginas predefinidas (se agregan en tiempo de ejecución)')
    print('Se conservan controles de gestos, mini reproductor y mensajes de error')
    print('Aviso: este módulo NO elimina la cuadrícula ni mide memoria')


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'Salida ya existente: {path}. No se sobrescribe')
    fd, temp = tempfile.mkstemp(prefix='.mox-home-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build(source: Path, target: Path):
    if source.resolve() == target.resolve():
        raise ValueError('La salida debe ser diferente del recurso de entrada')
    old, root = read_resource(source)
    old_signature = signature(root)
    new = awtk_ui.serialize(transform(root))
    _, reread = new, awtk_ui.parse(new)
    if signature(reread) != old_signature or awtk_ui.serialize(reread) != new:
        raise AssertionError('La verificación del recurso modificado falló')
    atomic_write(target, new)
    print('Recurso experimental generado:', target)
    print('SHA-256 original:', sha(old))
    print('SHA-256 experimental:', sha(new))
    print('IMPORTANTE: No es un firmware instalable; no se modificó el original')


def verify(source: Path, target: Path):
    _, original = read_resource(source)
    _, candidate = read_resource(target)
    if signature(original) != signature(candidate):
        raise AssertionError('El candidato cambió la estructura de los controles')
    expect = awtk_ui.serialize(transform(original))
    actual = target.read_bytes()
    if expect != actual:
        raise AssertionError('El candidato no coincide con el resultado reproducible')
    print('Verificación MOX home: OK; SHA-256:', sha(actual))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for cmd in ('inspect', 'build', 'verify'):
        p = sub.add_parser(cmd)
        p.add_argument('source', type=Path)
        if cmd != 'inspect':
            p.add_argument('target', type=Path)
    ns = ap.parse_args()
    if ns.cmd == 'inspect': report(ns.source)
    elif ns.cmd == 'build': build(ns.source, ns.target)
    else: verify(ns.source, ns.target)


if __name__ == '__main__':
    main()
