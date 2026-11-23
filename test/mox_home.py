#!/usr/bin/env python3
"""Pruebas aisladas para tools/mod_mox_home.py. No requieren firmware ni dispositivo."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import awtk_ui
import mod_mox_home as mox


def widget(typ, name, kids=(), props=()):
    return awtk_ui.Widget(typ, 0, 0, 100, 100,
                          [('name', name)] + list(props), list(kids))


def sample():
    sv = widget('slide_view', 'home_sview')
    indicator = widget('slide_indicator', 'home_sindicator', props=[
        ('style:normal:selected_fg_color', '#FFFFFF'),
        ('style:normal:fg_color', '#666666'),
    ])
    v = widget('view', 'home_svview', [sv, indicator])
    title = widget('hscroll_label', 'home_scrlabel_title')
    artist = widget('hscroll_label', 'home_scrlabel_artist', props=[
        ('style:normal:text_color', '#FFFFFF'),
        ('style:normal:font_size', '16'),
        ('style:disable:font_size', '16'),
        ('style:focused:font_size', '16'),
    ])
    bar = widget('view', 'home_bottomview', [widget('image', 'home_img_icon'), title, artist],
                 [('style:normal:bg_color', '#131313')])
    gesture = widget('gesture', 'app_gesture', [v, bar])
    return widget('window', 'home_page', [gesture, widget('label', 'label_snerr')])


def check(ok, desc):
    if not ok: raise AssertionError(desc)
    print('OK:', desc)


def main():
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / 'home_page.bin', Path(d) / 'home_mox.bin'
        src.write_bytes(awtk_ui.serialize(sample()))
        old, root = mox.read_resource(src)
        check(awtk_ui.serialize(root) == old, 'round-trip exacto')
        check(len(list(root.walk())) == 10, 'estructura de la pantalla')
        check(len(root.find('home_sview').children) == 0, 'el launcher se crea dinámicamente')
        mox.build(src, out)
        mox.verify(src, out)
        new = awtk_ui.parse(out.read_bytes())
        check(mox.signature(root) == mox.signature(new), 'misma geometría e IDs')
        check(root.find('home_sview').children == [], 'no se añade otro launcher')
        check(new.find('home_bottomview').get('style:normal:bg_color') == '#0B0B0D', 'nuevo color')
        check(new.find('home_scrlabel_artist').get('style:normal:font_size') == '15', 'fuente legible')
        check('MOX OS' not in repr(new.to_dict()), 'sin branding en Inicio')
        try:
            mox.build(src, src)
            raise AssertionError('Se permitió sobrescribir la fuente')
        except ValueError:
            print('OK: protege fuente original')
        try:
            mox.build(src, out)
            raise AssertionError('Se permitió sobrescribir candidato')
        except FileExistsError:
            print('OK: protege candidato existente')
        broken = sample()
        broken.find('home_sview').children.append(widget('view', 'unknown'))
        try:
            mox.audit(broken)
            raise AssertionError('Se aceptaron páginas inesperadas')
        except ValueError:
            print('OK: rechaza estructura inesperada')
        print('12 comprobaciones superadas')


if __name__ == '__main__':
    main()
