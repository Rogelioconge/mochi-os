#!/usr/bin/env python3
"""Create Mochi OS's isolated Now Playing AWTK window and its own page theme.

This stage adds resources only. Nothing in the MIPS payload opens the page.
It must run after mod_nowplaying (styles/icons) and mod_mox_native.
"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awtk_ui
import awtk_style
from awtk_ui import Widget
from pod_ui import UI_MODE, UI_MTIME, scroll_text, styled

RAW = Path(awtk_ui.RAW)
UI = RAW / 'ui'
STYLES = RAW / 'styles'
NATIVE = 'mox_now_playing.bin'
THEME = 'mox_now_playing_page.bin'
NAME = 'mox_now_playing_page'
SOURCE_THEME = 'playing_page.bin'

W, H = 320, 450
STATES = ('normal', 'disable', 'focused')
BTN_STATES = ('normal', 'disable', 'focused', 'over', 'pressed')
BG, TEXT, SECONDARY = '#121417', '#F4F4F1', '#9EA3AA'
ACCENT, TRACK = '#C1D4CF', '#2B3036'
M, COVER, ROW_Y, ROW_H = 28, 232, 400, 50
COVER_X, COVER_Y = 44, 48
TITLE = (M, 292, W - 2 * M, 26)
ARTIST = (M, 320, W - 2 * M, 22)
SLIDER = (M, 350, W - 2 * M, 30)
BAR, TIMES_Y, TIMES_H, TIMES_W = 4, 382, 18, 72
GRABBER, FAV, MORE = (100, 0, 120, 44), (12, 0, 44, 44), (264, 0, 44, 44)
SLOTS = {
    'btn_playmode': (4, 56), 'btn_prev': (64, 60), 'btn_play': (124, 72),
    'btn_next': (196, 60), 'btn_queue': (260, 56),
}
GLYPHS = {
    'btn_playmode': 'np_cycle', 'btn_prev': 'np_prev', 'btn_play': 'np_play',
    'btn_next': 'np_next', 'btn_queue': 'np_playqueue', 'btn_return': 'np_grabber',
    'btn_fav': 'np_unfav', 'btn_more': 'np_more',
}
# Style-managed buttons must not have an inline bg_image that masks play/pause or favourite changes.
DYNAMIC_STYLES = {
    'btn_play': 'btn_imgplay_style',
    'btn_playmode': 'btn_imgcycle_style',
    'btn_fav': 'btn_imgunfav_style',
}
THEME_STYLES = {
    'btn_imgplay_style', 'btn_imgpause_style',
    'btn_imgrandom_style', 'btn_imgcycle_style', 'btn_imgcycle1_style',
    'btn_imgorder_style', 'btn_imgfav_style', 'btn_imgunfav_style',
    'btn_imgsave_style', 'btn_imgunsave_style',
    'btn_imgspeed0_style', 'btn_imgspeed1_style', 'btn_imgspeed2_style',
    'btn_imgspeed3_style',
}
REQUIRED = (
    'img_playcover', 'scrlabel_title', 'scrlabel_artist', 'slider_play',
    'label_playtime', 'label_playlen', 'btn_return', 'btn_fav', 'btn_more',
    'view_buttons', *SLOTS,
)


def added_rels(stock_rootfs=None, *args):
    return [
        f'release/assets/default/raw/ui/{NATIVE}',
        f'release/assets/default/raw/styles/{THEME}',
    ]


def image_names():
    names = set()
    for widget in build().walk():
        for key, value in widget.props:
            if (key == 'image' or key.endswith(':bg_image') or key.endswith(':icon')) and value:
                names.add(value)
    return names


def _button(name, rect, glyph):
    style = DYNAMIC_STYLES.get(name, 'img_btn_style')
    button = Widget('button', *rect, [('name', name), ('enable', 'true'), ('style', style)])
    if name not in DYNAMIC_STYLES:
        for state in BTN_STATES:
            down = glyph + '_down' if state == 'pressed' and glyph != 'np_cycle' else glyph
            button.set(f'style:{state}:bg_image', down)
    return button


def _label(name, x, y, width, height, size, colour, align):
    result = Widget('label', x, y, width, height,
                    [('name', name), ('text', ''), ('sensitive', 'false')])
    for state in STATES:
        styled(result, (state,), 'font_size', str(size))
        styled(result, (state,), 'text_color', colour)
        styled(result, (state,), 'text_align_h', align)
    return result


def build():
    root = Widget('window', 0, 0, W, H, [('name', NAME)])
    styled(root, STATES, 'bg_color', BG)
    cover = Widget('image', COVER_X, COVER_Y, COVER, COVER,
                   [('name', 'img_playcover'), ('draw_type', 'scale'),
                    ('clickable', 'false'), ('sensitive', 'false')])
    title = scroll_text('scrlabel_title', *TITLE, 20, TEXT, 'center')
    artist = scroll_text('scrlabel_artist', *ARTIST, 16, SECONDARY, 'center')
    slider = Widget('slider', *SLIDER, [('name', 'slider_play'), ('bar_size', str(BAR))])
    for state in BTN_STATES:
        styled(slider, (state,), 'bg_color', TRACK)
        styled(slider, (state,), 'fg_color', ACCENT)
        styled(slider, (state,), 'round_radius', str(BAR // 2 + 1))
        styled(slider, (state,), 'icon', '')
    played = _label('label_playtime', M, TIMES_Y, TIMES_W, TIMES_H, 14, SECONDARY, 'left')
    length = _label('label_playlen', W - M - TIMES_W, TIMES_Y, TIMES_W, TIMES_H,
                    14, SECONDARY, 'right')
    row = Widget('view', 0, ROW_Y, W, ROW_H, [('name', 'view_buttons')])
    for name, (x, width) in SLOTS.items():
        button = _button(name, (x, 0, width, ROW_H), GLYPHS[name])
        button.set('self_layout', f'default(x={x},y=0,w={width},h=100%)')
        row.children.append(button)
    root.children = [
        cover, title, artist, slider, played, length,
        _button('btn_return', GRABBER, GLYPHS['btn_return']),
        _button('btn_fav', FAV, GLYPHS['btn_fav']),
        _button('btn_more', MORE, GLYPHS['btn_more']),
        row,
    ]
    return root


def transform():
    root = build()
    result = awtk_ui.serialize(root)
    if awtk_ui.serialize(awtk_ui.parse(result)) != result:
        raise AssertionError('Now Playing AWTK round-trip failed')
    for name in REQUIRED:
        if sum(widget.name == name for widget in root.walk()) != 1:
            raise ValueError(f'Missing or repeated widget: {name}')
    return result


def transform_theme(data):
    source = awtk_style.parse(data)
    if awtk_style.serialize(source) != data:
        raise ValueError('Source Now Playing theme failed binary round-trip')
    items = [
        awtk_style.Item(it.widget, it.style, it.state, list(it.props))
        for it in source.items if it.widget == 'button' and it.style in THEME_STYLES
    ]
    present = {(it.style, it.state) for it in items}
    for name in THEME_STYLES:
        for state in BTN_STATES:
            if (name, state) not in present:
                raise ValueError(f'Missing button state in source theme: {name}/{state}')
    theme = awtk_style.Theme(items, source.version)
    result = awtk_style.serialize(theme)
    if awtk_style.serialize(awtk_style.parse(result)) != result:
        raise AssertionError('Mochi page theme failed binary round-trip')
    return result


def apply(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() != output.resolve():
        raise ValueError('Expected an in-place build step')
    ui_folder, style_folder = source / UI, source / STYLES
    if not ui_folder.is_dir() or not style_folder.is_dir():
        raise FileNotFoundError('AWTK UI or styles folder missing')
    source_theme = style_folder / SOURCE_THEME
    if not source_theme.is_file():
        raise FileNotFoundError(source_theme)
    products = [
        (ui_folder / NATIVE, transform()),
        (style_folder / THEME, transform_theme(source_theme.read_bytes())),
    ]
    for dest, data in products:
        if dest.exists() and dest.read_bytes() != data:
            raise ValueError(f'Conflicting existing Mochi resource: {dest}')
    for dest, data in products:
        if not dest.exists():
            dest.write_bytes(data)
            os.chmod(dest, UI_MODE)
            os.utime(dest, (UI_MTIME, UI_MTIME))
    print('MOX Now Playing resources: independent window + page-local button theme (not opened by payload)')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: mod_mox_nowplaying.py WORKDIR WORKDIR')
    apply(sys.argv[1], sys.argv[2])
