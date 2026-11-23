#!/usr/bin/env python3
"""MOX OS: audit and deterministic visual approximations of the native Home.

No firmware build required: defaults to the generated source AWTK tree. If a
compiled m1plus_menu.bin is available, --built chooses it for stricter auditing
of icon insertion. The two mockups ARE NOT AWTK screenshots.

Run: uv run --locked python -I tools/mox_home_review.py
     uv run --locked python -I tools/mox_home_review.py --built
"""

import argparse
import json
from pathlib import Path

import awtk_ui
import pod_i18n
import pod_pages
import pod_ui

ROOT = Path(__file__).resolve().parents[1]
BUILT = (ROOT / 'work/check/release/work/mod-release/rootfs/release/'
         'assets/default/raw/ui/m1plus_menu.bin')
OUT = ROOT / 'out/mox-review'
ACCENT = '#83C8FF'


def load_tree(built=False):
    if built:
        if not BUILT.is_file():
            raise FileNotFoundError(f'No hay recurso compilado: {BUILT}')
        content = BUILT.read_bytes()
        tree = awtk_ui.parse(content)
        if awtk_ui.serialize(tree) != content:
            raise ValueError('El recurso compilado no supera el roundtrip AWTK')
        return tree
    tree = pod_ui.build_page(pod_pages.MENU)
    content = awtk_ui.serialize(tree)
    if awtk_ui.serialize(awtk_ui.parse(content)) != content:
        raise ValueError('El recurso fuente no supera el roundtrip AWTK')
    return tree


def audit(tree, built=False):
    """Returns a real structural audit of MOX's menu source/built assets."""
    expected = len(pod_pages.MENU.rows)
    rows = {w.name: w for w in tree.walk() if w.type == 'list_item'
            and w.name and w.name.startswith('pod_row')}
    if len(rows) != expected:
        raise ValueError(f'Cantidad de filas {len(rows)}; se esperaban {expected}')

    title = tree.find('label_title')
    prop, value = pod_i18n.text_prop('Library')
    if not title or title.get(prop) != value:
        raise ValueError('El título no usa la clave traducible Library')
    if not tree.find('navigationbar_view') or not tree.find('pod_minibar'):
        raise ValueError('Falta la cabecera o el mini-reproductor')

    for i in range(expected):
        row = rows.get(f'pod_row{i}')
        if row is None or row.h != pod_ui.ROW_H or row.w != pod_ui.SH_W:
            raise ValueError(f'Fila {i}: dimensión/identificador alterados')
        cards = [c for c in row.children if c.name == f'mox_card{i}']
        if len(cards) != 1 or row.children[0] is not cards[0]:
            raise ValueError(f'Fila {i}: tarjeta ausente o no va detrás')
        card = cards[0]
        if (card.x, card.y, card.w, card.h) != (6, 3, row.w - 12, row.h - 6):
            raise ValueError(f'Fila {i}: geometría de tarjeta incompatible')
        if card.get('sensitive') != 'false':
            raise ValueError(f'Fila {i}: tarjeta interceptaría la pulsación')
        if card.get('style:normal:round_radius') != '10':
            raise ValueError(f'Fila {i}: no se preservó el radio')
        expected_bg = '#213951' if i == 1 else ('#152334' if i % 2 == 0 else '#111d2c')
        if card.get('style:normal:bg_color') != expected_bg:
            raise ValueError(f'Fila {i}: color incorrecto')
        focused = '#294866' if i == 1 else '#1c3046'
        pressed = '#345f83' if i == 1 else '#304b66'
        if (card.get('style:focused:bg_color') != focused or
                card.get('style:pressed:bg_color') != pressed):
            raise ValueError(f'Fila {i}: colores de interacción incorrectos')
        if not any(c.type == 'hscroll_label' for c in row.children):
            raise ValueError(f'Fila {i}: sin etiqueta')
        if built:
            if len([c for c in row.children if c.name == 'pod_icon']) != 1:
                raise ValueError(f'Fila {i}: icono ausente en el recurso compilado')
            if row.children[1].name != 'pod_icon':
                raise ValueError(f'Fila {i}: el icono no está encima de la tarjeta')
            if any(c.name == 'pod_hair' for c in row.children):
                raise ValueError(f'Fila {i}: separador original aún visible')
        if i == 1:
            if len(card.children) != 1:
                raise ValueError('Cover Flow: falta su indicador de acento')
            marker = card.children[0]
            if (marker.name, marker.x, marker.y, marker.w, marker.h) != (
                    'mox_cover_accent', 6, 11, 2, card.h - 22):
                raise ValueError('Cover Flow: indicador desplazado')
            if marker.get('sensitive') != 'false' or marker.get('style:normal:bg_color') != ACCENT:
                raise ValueError('Cover Flow: indicador táctil/color incorrecto')
        elif card.children:
            raise ValueError(f'Fila {i}: indicador añadido fuera de Cover Flow')
    return rows


def _font(sz, bold=False):
    from PIL import ImageFont
    candidates = (
        ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Helvetica.ttc',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else
        ['/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    )
    for file in candidates:
        if Path(file).exists():
            return ImageFont.truetype(file, sz)
    return ImageFont.load_default()


def _draw_icon(draw, idx, x, y):
    """Geometric placeholder; not the firmware's PNG glyph."""
    col = '#B5D4EE' if idx == 1 else '#90AAC3'
    x, y = int(x), int(y)
    if idx == 1:
        draw.rounded_rectangle((x, y + 1, x + 21, y + 21), radius=4, outline=col, width=2)
        draw.ellipse((x + 7, y + 7, x + 14, y + 14), outline=col, width=2)
    elif idx == 2:
        for dy in (2, 8, 14):
            draw.line((x + 2, y + dy, x + 21, y + dy), fill=col, width=2)
    elif idx == 3:
        draw.ellipse((x + 5, y + 1, x + 15, y + 11), outline=col, width=2)
        draw.arc((x + 1, y + 8, x + 21, y + 24), 180, 360, fill=col, width=2)
    elif idx == 4:
        draw.line((x + 3, y + 6, x + 3, y + 21), fill=col, width=2)
        draw.ellipse((x + 3, y + 15, x + 12, y + 23), outline=col, width=2)
        draw.line((x + 3, y + 6, x + 19, y + 2), fill=col, width=2)
        draw.line((x + 19, y + 2, x + 19, y + 17), fill=col, width=2)
    elif idx == 5:
        for dy in (4, 10, 16):
            draw.line((x + 3, y + dy, x + 20, y + dy), fill=col, width=2)
    else:
        draw.ellipse((x + 3, y + 3, x + 8, y + 8), fill=col)
        draw.ellipse((x + 13, y + 3, x + 18, y + 8), fill=col)
        draw.ellipse((x + 3, y + 13, x + 8, y + 18), fill=col)
        draw.ellipse((x + 13, y + 13, x + 18, y + 18), fill=col)


def _icon_image(ui_path, icon_name):
    """Load unchanged UI glyph only if the real compiled resource exists."""
    from PIL import Image
    if not ui_path or not icon_name:
        return None
    path = ui_path.parents[1] / 'images/xx' / (icon_name + '.png')
    if path.is_file():
        with Image.open(path) as img:
            return img.convert('RGBA').copy()
    return None


def render(tree, rows, *, home, built=False, pressed_idx=None, focused_idx=None):
    """A geometry-driven PIL mock, not AWTK raster output.

    Screen is 320 x 480: status bar is stock's 30 px, below it is
    an AWTK window of 450 px. As Home, patch/home.c *hides the navbar* and
    shifts the list up to HOME_PAD=10. The mini player is shown only when playing.
    """
    from PIL import Image, ImageDraw
    screen = Image.new('RGBA', (320, 480), '#000000')
    draw = ImageDraw.Draw(screen)
    status = 30
    draw.rectangle((0, 0, 319, status - 1), fill='#090F18')
    # System status bar (the actual icon/time is intentionally not simulated).
    draw.line((12, 24, 308, 24), fill='#152638', width=1)

    if home:
        top = status + 10  # HOME_PAD, not the asset's navbar y=50
    else:
        nav = tree.find('navigationbar_view')
        draw.rectangle((0, status, 319, status + nav.h - 1),
                       fill=nav.get('style:normal:bg_color') or '#0a101a')
        draw.ellipse((12, 41, 41, 70), fill='#18283a')
        draw.text((20, 47), '‹', font=_font(22), fill='#d7e9fa')
        draw.text((58, 44), 'Biblioteca', font=_font(18, True), fill='#eef6ff')
        draw.ellipse((267, 41, 304, 78), fill='#17283b')
        draw.text((280, 47), '♫', font=_font(18), fill='#d2e7ff')
        top = status + tree.find('pod_listview').y
    shown = list(pod_pages.DEFAULT_MENU) + [len(rows) - 1]
    labels = {'Cover Flow': 'Cover Flow', 'Albums': 'Álbumes',
              'Artists': 'Artistas', 'Songs': 'Canciones',
              'Playlists': 'Listas', 'Extras': 'Más opciones'}
    ui_path = BUILT if built else None
    for n, idx in enumerate(shown):
        row = rows[f'pod_row{idx}']
        card = row.children[0]
        y = top + n * row.h
        rect = (card.x, y + card.y, card.x + card.w - 1, y + card.y + card.h - 1)
        draw.rounded_rectangle(rect, radius=int(card.get('style:normal:round_radius')),
                               fill=(card.get('style:pressed:bg_color') if idx == pressed_idx
                                     else card.get('style:focused:bg_color') if idx == focused_idx
                                     else card.get('style:normal:bg_color')))
        if idx == 1:
            mk = card.children[0]
            mx, my = card.x + mk.x, y + card.y + mk.y
            draw.rounded_rectangle((mx, my, mx + mk.w - 1, my + mk.h - 1),
                                   radius=1, fill=mk.get('style:normal:bg_color'))
        glyph = next((c for c in row.children if c.name == 'pod_icon'), None)
        img = _icon_image(ui_path, glyph.get('image')) if glyph else None
        if img is not None:
            if img.size != (24, 24):
                img.thumbnail((24, 24))
            screen.alpha_composite(img, (16 + (24-img.width)//2, y+14 + (24-img.height)//2))
        else:
            _draw_icon(draw, idx, 16, y+14)
        name = pod_pages.MENU.rows[idx].label
        draw.text((56, y + 15), labels.get(name, name),
                  fill='#ecf4ff', font=_font(17, idx == 1))
        if idx != 0:
            draw.text((289, y+10), '›', fill='#9fb2c5', font=_font(22))
    if home:
        mb = tree.find('pod_minibar')
        y = status + mb.y
        draw.rounded_rectangle((mb.x, y, mb.x + mb.w - 1, y + mb.h - 1),
                               radius=18, fill='#17283A')
        draw.rounded_rectangle((mb.x+9, y+8, mb.x+49, y+48), radius=6, fill='#2D5275')
        draw.ellipse((mb.x+21, y+20, mb.x+37, y+36), outline='#C5DAEE', width=2)
        draw.text((mb.x+60, y+8), 'Ejemplo de canción', font=_font(13, True), fill='#f1f6ff')
        draw.text((mb.x+60, y+29), 'Artista · FLAC', font=_font(11), fill='#9eafc2')
        draw.text((mb.x+mb.w-31, y+16), '▶', font=_font(16), fill='#eff7ff')
    return screen.convert('RGB')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--built', action='store_true', help='usar el archivo AWTK compilado de work/check')
    ap.add_argument('--out', type=Path, default=OUT, help='directorio de resultados (solo vista previa)')
    args = ap.parse_args()
    tree = load_tree(built=args.built)
    rows = audit(tree, built=args.built)
    args.out.mkdir(parents=True, exist_ok=True)
    files = {}
    from PIL import Image
    for label, home in (('principal', True), ('abierto-desde-shanling', False),
                        ('cover-flow-pulsado', True), ('albumes-seleccionado', True)):
        img = render(tree, rows, home=home, built=args.built,
                     pressed_idx=1 if label == 'cover-flow-pulsado' else None,
                     focused_idx=2 if label == 'albumes-seleccionado' else None)
        file = args.out / f'MOX-Home-{label}-aproximado.png'
        img.resize((640, 960), Image.Resampling.NEAREST).save(file)
        files[label] = file.name
        print('VISTA:', file)
    report = {
        'mode': 'compiled-asset' if args.built else 'source-only',
        'screen_pixels': [320, 480], 'status_bar_pixels': 30,
        'menu_rows': len(rows), 'cover_flow_id': 1,
        'default_ids': list(pod_pages.DEFAULT_MENU) + [len(rows) - 1],
        'navbar_hidden_on_home': True, 'minibar_only_when_playing': True,
        'files': files, 'caveats': [
            'Aproximación PIL, NO captura del renderizador AWTK ni medición táctil.',
            'Los iconos no disponibles se sustituyen por dibujos indicativos.',
            'La barra de reproducción muestra datos ilustrativos; no está siempre visible.',
            'La pulsación y la selección se simulan a partir de estados AWTK; no se han validado en dispositivo.',
        ],
    }
    report_file = args.out / 'reporte.json'
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('OK:', len(rows), 'tarjetas verificadas;', 'modo', report['mode'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
