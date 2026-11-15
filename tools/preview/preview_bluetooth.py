#!/usr/bin/env python3
"""Settings > Bluetooth (patch/btpage.c, docs/modules/bluetooth.md "The page"): the widgets of ui/m1plus_bluetooth.bin laid out as the payload lays them out (bp_layout), and the Audio Codec picker
(ui/m1plus_btcodec.bin), with sample devices, in a built tree's font and card pieces. The two device pages (patch/btpage.c bd_layout) are drawn from ui/m1plus_btdevice.bin.
Approximate (PIL, not AWTK).

  out/preview/bluetooth/bluetooth.png

Usage: uv run python -I tools/preview/preview_bluetooth.py WORKDIR [OUT.png]     (en_US; WORKDIR: a built tree, e.g. out/dev/<tag>/tree)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import awtk_ui, build, preview_icons as PI, pod_settings as ST
from preview_settings import W, NAV, SCREEN, rgb, sheet, draw_page

RAW = PI.RAW
GREY = rgb(ST.GREY)
# Sample devices: (name, paired, state), state 'on' connected, 'join' connecting, None
NAME = 'Shanling M1 Plus'   # the controller's name the note shows (a sample)
DEVICES = [('AirPods Pro', True, 'on'), ('Sony WH-1000XM5', True, None), ('JBL Flip 6', False, None), ('Living Room TV', False, None)]
CODEC_KEYS = ('LDAC HQ', 'LDAC Standard', 'LDAC Connection', 'btcode_aptxhd', 'btcode_aptx', 'btcode_aac', 'btcode_sbchq', 'btcode_sbc')   # patch/btpage.c bp_codec_text
BP_MY = 8   # patch/btpage.c: the first pool is the paired devices' (their rows have the info glyph and a narrower name)


class Page:
    """A scrolling cards page: rows are drawn on a tall canvas, out() crops a screen of it under the navbar."""
    def __init__(self, s):
        self.s = s; self.im = Image.new('RGBA', (W, 1200), (0, 0, 0, 255)); self.d = ImageDraw.Draw(self.im); self.y = ST.CM
        root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', 'm1plus_bluetooth.bin'), 'rb').read())
        self.by = {w.name: w for w in root.walk() if w.name}

    def card(self, rows):
        """rows: callables (y) drawing one row's content; the card's pieces and hairlines are drawn here."""
        n = len(rows)
        for i, draw in enumerate(rows):
            p = 'single' if n == 1 else 'top' if i == 0 else 'bot' if i == n - 1 else 'mid'
            self.im.alpha_composite(self.s.img(f'pod_cd_{p}'), (0, self.y))
            if i < n - 1: self.d.rectangle((24, self.y + 51, 309, self.y + 51), fill=rgb(ST.CARD_HAIR_RGB))
            draw(self.y); self.y += ST.ROW_H

    def mid(self, y): return y + ST.ROW_H / 2

    def switch(self, text, on):
        def f(y):
            self.s.text(self.im, 26, self.mid(y), text, 21)
            self.im.alpha_composite(self.s.img('sset_on' if on else 'sset_off'), (self.by['bt_sw_img'].x, y + self.by['bt_sw_img'].y))
        return f

    def codec(self, val):
        """The Audio Codec row: the label, the value (the payload's bp_value_fit: it takes the room its text needs, the label the rest) and the Settings chevron."""
        by = self.by
        def f(y):
            lab, chev = by['bt_codec_label'], by['bt_codec_chev']
            vw = min(self.s.font.width(val, ST.VALUE_PX) + 6, ST.VALUE_MAX); right = by['bt_codec_val'].x + by['bt_codec_val'].w
            self.s.text(self.im, lab.x + 2, self.mid(y), self.s.clip(self.s.shown(lab), 21, right - vw - ST.VALUE_LABEL_GAP - lab.x - 4), 21)
            self.im.alpha_composite(self.s.img(chev.get('image')), (chev.x, y + chev.y))
            self.s.text(self.im, right - 2, self.mid(y), val, ST.VALUE_PX, GREY, 'r')
        return f

    def device(self, name, paired, state):
        by = self.by
        k = 0 if paired else BP_MY   # a paired row (the info glyph, name room up to it) or another
        def f(y):
            chk, nm = by[f'bt_chk{k}'], by[f'bt_name{k}']
            if state == 'on': self.im.alpha_composite(self.s.img('pod_check'), (chk.x, y + chk.y))
            elif state == 'join': self.im.alpha_composite(self.s.img('wf_spin1'), (chk.x + 3, y + chk.y + 3))
            self.s.text(self.im, nm.x + 2, self.mid(y), self.s.clip(name, 21, nm.w - 4), 21)   # (az_fit_room cuts a long name with an ellipsis to the label's room)
            if paired: self.im.alpha_composite(self.s.img(by['bt_info0'].get('image')), (by['bt_info0'].x, y + by['bt_info0'].y))
        return f

    def search(self):
        lab = self.by['bt_search_label']
        return lambda y: self.s.text(self.im, lab.x + 2, self.mid(y), self.s.shown(lab), 21)

    def header(self, name, spinner=False):
        t = self.by[name + '_t']; px = int(t.get('style:normal:font_size')); text = self.s.shown(t)
        self.s.text(self.im, t.x + 2, self.y + t.y + t.h / 2, text, px, GREY)
        if spinner: self.im.alpha_composite(self.s.img('wf_spin2'), (t.x + 2 + self.s.font.width(text, px) + 8, self.y + self.by['bt_hdr_oth_spin'].y))
        self.y += ST.HDR_H

    def note(self):
        """The note: the template of the translation table with this player's name put in (patch/btpage.c, wk_subst), clipped to the label."""
        t = self.by['bt_note_t']; text = self.s.shown(t).replace('%s', NAME)
        self.s.text(self.im, t.x + 2, self.y + t.y + t.h / 2, self.s.clip(text, ST.NOTE_PX, t.w - 4), ST.NOTE_PX, GREY); self.y += ST.NOTE_H

    def gap(self): self.y += ST.GAP_H

    def out(self, title, scroll=0):
        s = self.s
        out = Image.new('RGBA', (W, SCREEN), (0, 0, 0, 255)); out.alpha_composite(self.im.crop((0, scroll, W, scroll + SCREEN - NAV)), (0, NAV))
        lt = self.by['label_title']; tpx = PI.title_px(s.tree)
        s.text(out, lt.x, NAV / 2, s.clip(title, tpx, lt.w), tpx)
        for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
            g = s.img(name); out.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
        return out


def draw_bt(s, on=True, devices=(), scanning=True, codec=3, scroll=0):
    """The page as bp_layout lays it out: the switch and Audio Codec, the note with this player's name, My Devices (paired; the connected one checked, a connecting one with the spinner; the info glyph
    opens the device's page), Other Devices (the found ones, the spinner after the header while the search runs, Search Again as the card's last row once it ended)."""
    p = Page(s)
    if not on:
        p.card([p.switch(s.shown(p.by['bt_sw_label']), False)])
        return p.out(s.shown(p.by['label_title']))
    p.card([p.switch(s.shown(p.by['bt_sw_label']), True), p.codec(s.strings.get(CODEC_KEYS[codec], CODEC_KEYS[codec]))])
    p.note()
    mine = [d for d in devices if d[1]]; others = [d for d in devices if not d[1]]
    if mine:
        p.header('bt_hdr_my'); p.card([p.device(*d) for d in mine])
    p.header('bt_hdr_oth', scanning)
    rows = [p.device(*d) for d in others] + ([] if scanning else [p.search()])
    if rows: p.card(rows)
    return p.out(s.shown(p.by['label_title']), scroll)


def draw_btinfo(s, name, connected, joining=False):
    """A paired device's page (patch/btpage.c bd_layout): the widgets of ui/m1plus_btdevice.bin as the payload lays them out. Connect or Disconnect ("Connect" dimmed while the link is made), Headset Volume with its two
    keys while the device is the connected one, Forget This Device; the whole name above the cards when the navbar's title is cut (the Wi-Fi info page's rule)."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', 'm1plus_btdevice.bin'), 'rb').read())
    by = {w.name: w for w in root.walk() if w.name}
    im = Image.new('RGBA', (W, 400), (0, 0, 0, 255))
    grey = rgb(ST.GREY)
    def card(y): im.alpha_composite(s.img('pod_cd_single'), (0, y))
    def centred(name, y, text, ink=(255, 255, 255)):
        w = by[name]; s.text(im, w.x + w.w // 2, y + ST.ROW_H / 2, text, 21, ink, 'm')
    y = ST.CM
    lt = by['label_title']; tpx = PI.title_px(s.tree); cut = s.clip(name, tpx, lt.w)
    if cut != name:   # the whole name in one grey line (wf_name_lines), as the Wi-Fi info page
        nl = by['bd_name0']; npx = int(nl.get('style:normal:font_size'))
        s.text(im, nl.x + nl.w // 2, y + nl.h / 2, s.clip(name, npx, nl.w), npx, grey, 'm'); y += nl.h + 8
    card(y)
    centred('bd_link_t', y, s.strings.get('Disconnect', 'Disconnect') if connected else s.strings.get('Connect', 'Connect'), (255 * 153 // 255,) * 3 if joining else (255, 255, 255)); y += ST.ROW_H + ST.GAP_H
    if connected:
        card(y)
        s.text(im, by['bd_vol_t'].x + 2, y + ST.ROW_H / 2, s.shown(by['bd_vol_t']), 21)
        for key, icon in (('bd_vol_dn', 'pod_ic_btvol_dn'), ('bd_vol_up', 'pod_ic_btvol_up')):
            k = by[key]; g = s.img(icon); im.alpha_composite(g, (k.x + (k.w - g.width) // 2, y + (ST.ROW_H - g.height) // 2))
        y += ST.ROW_H + ST.GAP_H
    card(y); centred('bd_forget_t', y, s.shown(by['bd_forget_t']))
    out = Image.new('RGBA', (W, SCREEN), (0, 0, 0, 255)); out.alpha_composite(im.crop((0, 0, W, SCREEN - NAV)), (0, NAV))
    s.text(out, lt.x, NAV / 2, cut, tpx)
    for nm, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(nm); out.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return out


def draw_codec(s, chosen):
    """The Audio Codec picker: the page's own asset (ui/m1plus_btcodec.bin) as the generic cards page draws it, the check on the chosen row."""
    return draw_page(s, 'm1plus_btcodec', state={'shown': {f'pod_check{chosen}'}})


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    s = PI.Side(sys.argv[1], True, 'en_US'); s.mark = lambda *a: None
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'bluetooth', 'bluetooth.png')
    join = [('AirPods Pro', True, None), ('Sony WH-1000XM5', True, 'join')] + DEVICES[2:]
    sheet([('Bluetooth, on', draw_bt(s, True, DEVICES, scanning=True, scroll=110)),
           ('connecting, search ended', draw_bt(s, True, join, scanning=False, scroll=110)),
           ('no paired device, searching', draw_bt(s, True, DEVICES[2:])),
           ('off', draw_bt(s, False)),
           ('device (connected)', draw_btinfo(s, 'AirPods Pro', True)),
           ('device (not connected)', draw_btinfo(s, 'Sony WH-1000XM5', False)),
           ('Audio Codec', draw_codec(s, 3))], out)


if __name__ == '__main__':
    main()
