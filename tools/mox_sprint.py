"""MOX OS dev sprint: checks, structural preview, and source snapshot.

Runs only read-only build/tests on firmware work trees. Never flashes or packs a firmware.
Run from the repository with: uv run --locked python -I tools/mox_sprint.py
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'mox-sprint'
UI = ROOT / 'work/check/release/work/mod-release/rootfs/release/assets/default/raw/ui/m1plus_menu.bin'


def command(*args):
    print('\n$ ' + ' '.join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, check=False)
    return result.returncode


def source_snapshot():
    """Pack source only, including uncommitted edits; no firmware, assets, keys or Git history."""
    allowed_roots = ('tools', 'patch', 'test', 'docs')
    allowed_ext = {'.py', '.c', '.h', '.inc', '.md', '.sh', '.txt', '.toml'}
    standalone = ('Makefile', 'pyproject.toml', 'uv.lock', 'README.md')
    excludes = ('__pycache__', '.git', '.venv', 'work', 'firmware', 'fonts', 'assets', 'out', 'node_modules')
    path = OUT / 'MOX-OS-fuentes.zip'
    count = 0
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=8) as z:
        for root in allowed_roots:
            folder = ROOT / root
            if not folder.is_dir():
                continue
            for p in sorted(folder.rglob('*')):
                if not p.is_file() or p.is_symlink() or p.suffix not in allowed_ext:
                    continue
                rel = p.relative_to(ROOT)
                parts = tuple(rel.parts)
                lower = p.name.lower()
                if any(t in parts for t in excludes) or lower.startswith('.'):
                    continue
                if any(t in lower for t in ('secret', 'credential', 'password', 'token', 'private_key', '.env')):
                    continue
                if p.stat().st_size > 2_000_000:
                    continue
                z.write(p, str(rel))
                count += 1
        for rel in standalone:
            p = ROOT / rel
            if p.is_file() and p.stat().st_size <= 2_000_000 and rel not in z.namelist():
                z.write(p, rel)
                count += 1
    print(f'Fuentes: {path} ({count} archivos; sin firmware original)', flush=True)
    return str(path)


def rgb(v, default):
    if not isinstance(v, str):
        return default
    m = re.fullmatch(r'#([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?', v)
    return '#' + m.group(1) if m else default


def preview():
    import awtk_ui
    import pod_pages
    import pod_i18n
    from PIL import Image, ImageDraw, ImageFont

    if not UI.is_file():
        raise RuntimeError(f'No se encontró el recurso de compilación: {UI}')
    tree = awtk_ui.parse(UI.read_bytes())
    rows = {w.name: w for w in tree.walk() if w.type == 'list_item' and (w.name or '').startswith('pod_row')}
    total = len(pod_pages.MENU.rows)
    assert len(rows) == total, f'Filas: {len(rows)} != {total}'
    prop, value = pod_i18n.text_prop('Library')
    title = tree.find('label_title')
    assert title and title.get(prop) == value, 'La cabecera no utiliza la traducción Library'
    assert tree.find('pod_minibar'), 'No aparece la minibarra de reproducción'
    for i in range(total):
        row = rows[f'pod_row{i}']
        children = row.children
        assert len(children) >= 3 and children[0].name == f'mox_card{i}' and children[1].name == 'pod_icon', f'Orden fila {i}'
        card = children[0]
        assert (card.x, card.y, card.w, card.h) == (6, 3, row.w - 12, row.h - 6), f'Geometría fila {i}'
        assert card.get('sensitive') == 'false', f'Tarjeta interceptaría pulsaciones: fila {i}'
        assert any(c.type == 'hscroll_label' for c in children), f'Sin texto: fila {i}'
        assert not any(c.name == 'pod_hair' for c in children), f'Separador inesperado: fila {i}'
        assert card.get('style:normal:round_radius') == '10', f'Radio fila {i}'

    base = Image.new('RGB', (320, 480), '#05080e')
    d = ImageDraw.Draw(base)

    def font(size, bold=False):
        candidates = [
            '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
        for f in candidates:
            if Path(f).is_file():
                return ImageFont.truetype(f, size)
        return ImageFont.load_default()

    nav = tree.find('navigationbar_view')
    d.rectangle((0, 0, 319, 49), fill=rgb(nav.get('style:normal:bg_color'), '#0a101a'))
    d.text((15, 14), 'Biblioteca', font=font(19, True), fill='#edf4ff')
    d.text((287, 14), '♫', font=font(18), fill='#9bb7d7')

    row_order = list(pod_pages.DEFAULT_MENU) + [total - 1]
    label_es = {
        'Cover Flow': 'Cover Flow', 'Albums': 'Álbumes', 'Artists': 'Artistas',
        'Songs': 'Canciones', 'Playlists': 'Listas', 'Extras': 'Más opciones',
    }
    y = 50
    for i in row_order:
        row = rows[f'pod_row{i}']
        card = row.children[0]
        fill = rgb(card.get('style:normal:bg_color'), '#182738')
        x0, y0 = card.x, y + card.y
        x1, y1 = x0 + card.w - 1, y0 + card.h - 1
        d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=fill)
        d.rounded_rectangle((16, y + 14, 40, y + 38), radius=6, fill='#355879' if i == 1 else '#263d55')
        label = pod_pages.MENU.rows[i].label
        d.text((56, y + 15), label_es.get(label, label), fill='#f0f5ff', font=font(17, i == 1))
        d.text((286, y + 14), '›', fill='#9ab3cf', font=font(20))
        y += row.h

    mb = tree.find('pod_minibar')
    d.rounded_rectangle((mb.x, mb.y, mb.x + mb.w - 1, mb.y + mb.h - 1), radius=14, fill='#182738')
    d.rounded_rectangle((mb.x + 10, mb.y + 8, mb.x + 50, mb.y + 48), radius=8, fill='#315674')
    d.text((mb.x + 60, mb.y + 10), 'Reproduciendo', font=font(14, True), fill='#f3f7ff')
    d.text((mb.x + 60, mb.y + 30), 'Barra de reproducción', font=font(10), fill='#acbfd2')
    d.text((mb.x + mb.w - 35, mb.y + 14), '▶', font=font(18), fill='#dbeaff')
    d.text((10, 459), 'Vista aproximada · no render de AWTK', font=font(9), fill='#8b9bad')
    out = OUT / 'MOX-Home-preview-aproximada.png'
    base.resize((640, 960), Image.Resampling.NEAREST).save(out)
    print(f'Vista previa: {out}', flush=True)
    return {'cards_checked': total, 'title_translation': 'Library', 'mini_player_found': True,
            'default_menu_ids': row_order, 'preview': str(out), 'limitations': 'Vista aproximada de la estructura y estilos AWTK, no captura real; iconos y texto de minibar son ilustrativos'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / 'tools'))
    report = {'tests': {}, 'notes': ['No crea update.bin ni instala firmware. No modifica archivos de código fuente.']}
    # Save source even if one of the checks fails, so the actual project can be repaired in one batch.
    report['source_zip'] = source_snapshot()
    for target in ('home', 'assets'):
        rc = command('make', 'test', f'TEST={target}')
        report['tests'][target] = {'exit_code': rc, 'passed': rc == 0}
        if rc != 0:
            print(f'Prueba {target} falló; revisa los mensajes anteriores. No se instala nada.', flush=True)
    try:
        report['home'] = preview()
    except Exception as exc:
        report['preview_error'] = str(exc)
        traceback.print_exc()
    report_path = OUT / 'MOX-sprint-reporte.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('\n=== MOX Sprint ===')
    print('Reporte:', report_path)
    print('Fuentes para enviar:', report['source_zip'])
    print('Pruebas:', report['tests'])
    if 'preview_error' in report:
        print('La vista previa necesita revisión:', report['preview_error'])
    return 0 if all(r['passed'] for r in report['tests'].values()) and 'home' in report else 1


if __name__ == '__main__':
    raise SystemExit(main())
