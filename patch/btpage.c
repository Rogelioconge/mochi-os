/* The own Bluetooth page: Settings > Bluetooth (docs/modules/bluetooth.md "The page"), and its Audio Codec picker.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * ui/m1plus_bluetooth.bin (tools/pod_ui.py build_bluetooth_page) is the Wi-Fi page's layout: the Settings cards in the stock list under our navbar. Card 1 is the Bluetooth switch row and, while Bluetooth is on, the Audio
 * Codec value row (it opens the picker m1plus_btcodec); under it a grey note names this player; My Devices (the paired devices) and Other Devices (the found ones, a small spinner after the header's text while the
 * search or the start runs) are cards of pooled device rows, the second ending in Search Again. A device row is the Wi-Fi network row without the lock and the signal: the connected device has a check at the
 * left, a connecting one a spinner, the name follows, and a paired device has the info glyph at the right. Every row is a pooled widget: the payload shows the ones it needs, moves them (widget_move, virtual_h)
 * and gives each its picture piece, so no widget is made at run time.
 *
 * Nothing here talks to the Bluetooth backend: patch/btset.c (the control layer) repeats stock's sequences, this file lays the state out and calls it. One 200 ms timer owned by the page runs bs_tick, only while
 * the page is in front and no dialog of ours is up; the scan is stopped on every way out (Back, Now Playing, to-background, close, destroy).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "home.h"
#include "azlist.h"
#include "i18n.h"
#include "wifictl.h"
#include "btset.h"
#include "entries.h"

#define BP_MY 8 /* the asset's row pools (tools/pod_ui.py BT_MY, BT_OTH): paired devices, found devices */
#define BP_OTH 16
#define BP_ROWS (BP_MY + BP_OTH)
#define BP_DEVS 32 /* the show list is read up to this many devices (paired first); the pools drop the rest */
#define BP_ROW_H 52 /* the Settings pages' numbers (tools/pod_settings.py) */
#define BP_HDR_H 40
#define BP_NOTE_H 34
#define BP_TOP 10
#define BP_END 10
#define BP_HDR_X 24 /* the header's label; its text starts 2 px in */
#define BP_HDR_TW 76 /* the width of the Other Devices header's text when it cannot be measured */
#define BP_NAME_MARGIN 2 /* the stock hscroll_label's default margin_left / margin_right */
#define BP_INFO_X 264 /* a tap right of this on a paired device's row is its info glyph's */
#define BP_TICK_MS 200 /* stock's own timer */
#define BP_VALUE_RIGHT \
    280 /* the value rows' box: right edge, widest text, gap to the label, label's x (tools/pod_settings.py value_box, VALUE_MAX, VALUE_LABEL_GAP, label_box) */
#define BP_VALUE_MAX 140
#define BP_VALUE_GAP 6
#define BP_LABEL_X 24
#define BP_NAME_MAX 256

static struct {
    void *win, *sv, *fade; /* (wf_on_scroll takes a struct that starts with these three) */
    void *sw_row, *sw_img, *sw_hair, *codec_row, *codec_label, *codec_val, *note, *note_t, *hdr_my, *hdr_oth, *spin_img,
        *search_row;
    struct {
        void *row, *chk, *name, *info, *hair;
    } r[BP_ROWS];
    int map[BP_ROWS]; /* the device (index in dev) each shown row slot holds, -1 unused */
    unsigned char
        piece[BP_ROWS +
              3]; /* the picture piece each row has now (WP_P_*), then the switch row, the codec row and Search Again */
    struct bs_dev dev[BP_DEVS];
    int ndev;
    int on, starting, scanning; /* what the last layout showed */
    int crow; /* the slot whose check place shows the spinner (a device is connecting), -1 none */
    int spin; /* the spinners' frame */
    unsigned timer;
    int fg; /* the page is the front window */
} bp __attribute__((section(".scratch")));

/* The codec row's text and the picker's rows: our own keys for the three LDAC choices, stock's keys for the others (tools/pod_pages.py BT_CODECS, BT_CODEC_KEYS). */
static const char *const bp_codec_text[8] = {"LDAC HQ",     "LDAC Standard", "LDAC Connection", "btcode_aptxhd",
                                             "btcode_aptx", "btcode_aac",    "btcode_sbchq",    "btcode_sbc"};

/* ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- the picker */

int bp_codec(void) { return bs_codec(); }

/* A row of the Audio Codec page: stock's Quality choice behind the init guard. The check follows the codec stock keeps: a refused choice, or a reconnect question that was cancelled, leaves it where it was (-1). */
int bp_codec_set(int c) {
    if (bs_init_guard()) return -1;
    bs_codec_set(c);
    return bs_codec() == c ? 0 : -1;
}

/* ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- the page */

/* The codec row's value takes the room its text needs and the label keeps the rest (patch/m1plus.c value_fit's rule). */
static void bp_value_fit(void) {
    const unsigned *t = widget_get_text(bp.codec_val);
    int vw = t && *t ? m1_text_w(bp.codec_val, t) + 6 : 8;
    if (vw > BP_VALUE_MAX) vw = BP_VALUE_MAX;
    widget_move(bp.codec_val, BP_VALUE_RIGHT - vw, widget_get_prop_int(bp.codec_val, "y", 0));
    widget_resize(bp.codec_val, vw, widget_get_prop_int(bp.codec_val, "h", 0));
    widget_resize(bp.codec_label, BP_VALUE_RIGHT - vw - BP_VALUE_GAP - BP_LABEL_X,
                  widget_get_prop_int(bp.codec_label, "h", 0));
}

/* One device row: the name (cut to the label's room with an ellipsis, so the stock hscroll_label never scrolls it), the check or the spinner place. */
static void bp_fill(int s, const struct bs_dev *d) {
    char u[BP_NAME_MAX];
    int joining = d->state == BS_DEV_CONNECTING;
    wf_utf8((const unsigned char *)d->name, (unsigned)strlen(d->name), u, sizeof u);
    az_fit_room(bp.r[s].name, u, I(bp.r[s].name, W_W) - 2 * BP_NAME_MARGIN);
    wp_vis(bp.r[s].chk, d->state != BS_DEV_NONE);
    if (d->state != BS_DEV_NONE) image_base_set_image(bp.r[s].chk, joining ? "wf_spin0" : "pod_check");
    if (joining) bp.crow = s;
}

/* A card's rows from slot `first` (n devices, `extra` more rows in the same card after them: Search Again): piece, hairline and place. */
static void bp_card(int first, int n, int extra, int *y) {
    int i, total = n + extra;
    for (i = 0; i < n; i++) {
        int s = first + i;
        wp_piece(bp.r[s].row, &bp.piece[s], wp_pos(i, total));
        wp_vis(bp.r[s].hair, i < total - 1);
        wp_put(bp.r[s].row, y, BP_ROW_H, 1);
    }
}

static void bp_spinner(void);

/* The rows as the state says, read again now: moved into place, the unused ones hidden. */
static void bp_layout(void) {
    char note[BP_NAME_MAX + 64], nm[BP_NAME_MAX];
    int y = BP_TOP, i, np = 0, no = 0, busy;
    bp.on = bs_on();
    bp.starting = bs_starting();
    bp.scanning = bs_scanning();
    busy = bp.on && (bp.starting || bp.scanning);
    bp.ndev = bp.on ? bs_devices(bp.dev, BP_DEVS) : 0;
    for (i = 0; i < BP_ROWS; i++) bp.map[i] = -1;
    bp.crow = -1;
    for (i = 0; i < bp.ndev; i++) {
        if (bp.dev[i].paired && np < BP_MY)
            bp.map[np++] = i;
        else if (!bp.dev[i].paired && no < BP_OTH)
            bp.map[BP_MY + no++] = i;
    }
    image_base_set_image(bp.sw_img, bp.on ? "sset_on" : "sset_off");
    wp_piece(bp.sw_row, &bp.piece[BP_ROWS], bp.on ? WP_P_TOP : WP_P_SINGLE);
    wp_vis(bp.sw_hair, bp.on);
    wp_put(bp.sw_row, &y, BP_ROW_H, 1);
    if (bp.on) { /* the codec row: stock's preferred codec, in the language's text */
        widget_set_tr_text(bp.codec_val, bp_codec_text[bs_codec()]);
        bp_value_fit();
        wp_piece(bp.codec_row, &bp.piece[BP_ROWS + 1], WP_P_BOT);
        wp_put(bp.codec_row, &y, BP_ROW_H, 1);
    } else
        m1_show(bp.codec_row, 0);
    wf_utf8((const unsigned char *)bs_name(), (unsigned)strlen(bs_name()), nm, sizeof nm);
    if (bp.on && nm[0]) { /* the note: this player's name as the controller reports it */
        wk_subst(note, sizeof note, TR("This player is shown as “%s”"), nm);
        widget_set_text_utf8(bp.note_t, note);
        wp_put(bp.note, &y, BP_NOTE_H, 0);
    } else
        wp_vis(bp.note, 0);
    if (np)
        wp_put(bp.hdr_my, &y, BP_HDR_H, 0);
    else
        wp_vis(bp.hdr_my, 0);
    bp_card(0, np, 0, &y);
    for (i = 0; i < BP_ROWS; i++)
        if (bp.map[i] < 0) m1_show(bp.r[i].row, 0);
    for (i = 0; i < BP_ROWS; i++)
        if (bp.map[i] >= 0) bp_fill(i, &bp.dev[bp.map[i]]);
    if (bp.on) {
        int search = !busy; /* Search Again: only while no search runs */
        wp_put(bp.hdr_oth, &y, BP_HDR_H, 0);
        bp_card(BP_MY, no, search, &y);
        if (search) {
            wp_piece(bp.search_row, &bp.piece[BP_ROWS + 2], wp_pos(no, no + 1));
            wp_put(bp.search_row, &y, BP_ROW_H, 1);
        } else
            m1_show(bp.search_row, 0);
    } else {
        wp_vis(bp.hdr_oth, 0);
        m1_show(bp.search_row, 0);
    }
    y += BP_END;
    widget_set_prop_int(bp.sv, "virtual_h", y);
    wp_clamp(bp.sv, y);
    bp_spinner();
    widget_invalidate_force(bp.sv, (void *)0);
}

/* The header's spinner while the search or the start runs, and the connecting device's spinner in its check's place: one frame of eight per tick. */
static void bp_spinner(void) {
    char n[12];
    int busy = bp.on && (bp.starting || bp.scanning);
    if (!busy && bp.crow < 0) {
        wp_vis(bp.spin_img, 0);
        return;
    }
    snprintf(n, sizeof n, "wf_spin%d", bp.spin++ & 7);
    wp_vis(bp.spin_img, busy);
    if (busy) image_base_set_image(bp.spin_img, n);
    if (bp.crow >= 0) image_base_set_image(bp.r[bp.crow].chk, n);
}

/* The Other Devices header's spinner goes after the header's text (measured, so it follows the language; BP_HDR_TW px when it cannot be measured). */
static void bp_spin_place(void) {
    void *lab = widget_lookup(bp.win, "bt_hdr_oth_t", 1);
    const unsigned *t = lab ? widget_get_text(lab) : (const unsigned *)0;
    int tw = t && *t ? m1_text_w(lab, t) : 0;
    if (tw <= 0) tw = BP_HDR_TW;
    widget_move(bp.spin_img, BP_HDR_X + 2 + tw + 8, widget_get_prop_int(bp.spin_img, "y", 0));
}

/* Taps. Every action may block as stock's handlers do; after any of them the state is read again. */
static int bp_on_switch(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (bs_modal()) return RET_OK;
    bs_toggle();
    if (!bs_on()) bs_close(); /* (switching off stops the search; stock's off path does it too) */
    bp_layout();
    return RET_OK;
}

static int bp_on_codec(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (bs_modal() || !bp.on) return RET_OK;
    if (bs_init_guard()) return RET_OK; /* stock's Quality row: the toast while the init runs, else the page */
    pod_open_btcodec();
    return RET_OK;
}

static int bp_on_search(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (bs_modal() || !bp.on) return RET_OK;
    bs_search();
    bp_layout();
    return RET_OK;
}

/* The row's tap: connect, disconnect or pair (stock's tap on a device). */
static void bp_link(const char *mac) {
    bs_link(mac);
    bp_layout();
}

/* ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- the device page
 * One paired device's page (window m1plus_btdevice, tools/pod_ui.py build_btdevice_page, docs/modules/bluetooth.md "The device page"): Connect / Disconnect, Headset Volume with its two keys, Forget This Device. It keeps the
 * device's MAC and reads the state again from the show list (bs_devices, into the Bluetooth page's own array: the page is above it) on a 500 ms timer while it is in front, on to-foreground and after every action; a
 * link that finishes on its own shows without a tap, and the page closes when the device is no longer in the list or no longer paired. The timer never runs bs_tick (the search is stopped while this page is up)
 * and never touches the redraw flag, so the Bluetooth page's own read when it returns is not starved.
 */
#define BD_TICK_MS 500
#define BD_GAP_H 20 /* the space between two cards (tools/pod_settings.py GAP_H) */
#define BD_DIM 153 /* the opacity of "Connect" while the link is being made (60 %, the dimmed rows' value) */

static struct {
    void *win, *sv, *fade, *title;
    void *nm[2], *name[2]; /* the whole name's lines above the cards (a title that was cut) */
    int lines;
    void *link, *link_t, *vol, *dn, *up, *forget, *gap[2];
    unsigned char piece[2]; /* the picture piece of the Connect and the Forget rows */
    char mac[sizeof(((struct bs_dev *)0)->mac)];
    struct bs_dev cur; /* the device as the last read saw it */
    int vol_on; /* the Headset Volume card is shown */
    unsigned sig, timer;
    int fg, closed;
} bd __attribute__((section(".scratch")));

/* The device in the show list by its MAC: 1 when it is there and paired (bd.cur holds it). The array is the Bluetooth page's, which lays itself out again when this page returns. */
static int bd_read(void) {
    int n, i;
    if (!bp.win || !bs_on()) return 0;
    n = bs_devices(bp.dev, BP_DEVS);
    bp.ndev = n;
    for (i = 0; i < n; i++)
        if (strcmp(bp.dev[i].mac, bd.mac) == 0) {
            memcpy(&bd.cur, &bp.dev[i], sizeof bd.cur);
            return bd.cur.paired;
        }
    return 0;
}

/* The rows as the device's state says: Connect or Disconnect ("Connect" dimmed and not touchable while the link is being made), Headset Volume while it is the connected device and the volume can be set, Forget. */
static void bd_layout(void) {
    int y = BP_TOP, conn = bd.cur.state == BS_DEV_CONNECTED, joining = bd.cur.state == BS_DEV_CONNECTING;
    wf_name_put(bd.nm, bd.lines, &y);
    widget_set_tr_text(bd.link_t, conn ? "Disconnect" : "Connect");
    widget_set_opacity(bd.link_t, joining ? BD_DIM : 255);
    wp_piece(bd.link, &bd.piece[0], WP_P_SINGLE);
    wp_put(bd.link, &y, BP_ROW_H, 1);
    widget_set_sensitive(bd.link, !joining);
    wp_put(bd.gap[0], &y, BD_GAP_H, 0);
    if (bd.vol_on) {
        wp_put(bd.vol, &y, BP_ROW_H, 1);
        wp_put(bd.gap[1], &y, BD_GAP_H, 0);
    } else {
        m1_show(bd.vol, 0);
        wp_vis(bd.gap[1], 0);
    }
    m1_show(bd.dn, bd.vol_on);
    m1_show(bd.up, bd.vol_on);
    wp_piece(bd.forget, &bd.piece[1], WP_P_SINGLE);
    wp_put(bd.forget, &y, BP_ROW_H, 1);
    y += BP_END;
    widget_set_prop_int(bd.sv, "virtual_h", y);
    wp_clamp(bd.sv, y);
    widget_invalidate_force(bd.sv, (void *)0);
}

/* Read the state again; lay out when what the page shows changed; close the page when the device is gone. */
static void bd_refresh(void) {
    unsigned sig;
    if (!bd.win || bd.closed) return;
    if (!bd_read()) {
        bd.closed = 1;
        navigator_back(); /* (the destroy handler clears this page) */
        return;
    }
    bd.vol_on = bd.cur.state == BS_DEV_CONNECTED && bs_volume_ok();
    sig = 1 + (unsigned)bd.cur.state + 4 * (unsigned)bd.vol_on;
    if (sig != bd.sig) bd.sig = sig, bd_layout();
}

static int bd_on_link(void *ctx, void *e) {
    char mac[sizeof bd.mac];
    (void)ctx;
    (void)e;
    if (bs_modal() || bd.cur.state == BS_DEV_CONNECTING) return RET_OK;
    snprintf(mac, sizeof mac, "%s", bd.mac);
    bs_link(mac);
    bd_refresh();
    return RET_OK;
}

static int bd_key(int up) {
    if (bs_modal() || !bd.vol_on || bs_init_guard()) return RET_OK;
    bs_volume(up);
    bd_refresh();
    return RET_OK;
}

static int bd_on_dn(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    return bd_key(0);
}

static int bd_on_up(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    return bd_key(1);
}

/* Forget: stock's confirm and toast are bs_forget's; the device is gone from My Devices afterwards, so the page closes (bd_refresh), and stays when the question was cancelled. */
static int bd_on_forget(void *ctx, void *e) {
    char mac[sizeof bd.mac];
    (void)ctx;
    (void)e;
    if (bs_modal()) return RET_OK;
    snprintf(mac, sizeof mac, "%s", bd.mac);
    bs_forget(mac);
    bd_refresh();
    return RET_OK;
}

static int bd_tick(const void *timer) {
    (void)timer;
    if (!bd.win) return RET_OK;
    if (!bd.fg || bs_modal()) return RET_REPEAT;
    bd_refresh();
    return RET_REPEAT;
}

static int bd_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    bd.fg = 1;
    bd.sig = 0;
    if (!bs_modal()) bd_refresh(); /* (under a dialog of ours the timer does it once the dialog is gone) */
    return RET_OK;
}

static int bd_on_bg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    bd.fg = 0;
    return RET_OK;
}

static int bd_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != bd.win) return RET_OK;
    m1_timer_stop(&bd.timer);
    memset(&bd, 0, sizeof bd);
    return RET_OK;
}

/* The name in the navbar's title, and in the lines above the cards when the title cuts it (wf_name_lines), fitted from the device's whole name. */
static void bd_fit_name(void) {
    char u[BP_NAME_MAX];
    wf_utf8((const unsigned char *)bd.cur.name, (unsigned)strlen(bd.cur.name), u, sizeof u);
    bd.lines = az_fit(bd.title, u) ? wf_name_lines(bd.name[0], bd.name[1], u) : 0;
}

/* The window is about to open: stock has just resolved every widget's style, so the name fitted at open (in the default style's smaller font) is fitted again in the title's style. */
static int bd_on_will_open(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!bd.win) return RET_OK;
    bd_fit_name();
    bd_layout();
    return RET_OK;
}

/* The info glyph of a paired device's row: its page. */
static void bd_open(const char *mac) {
    char n[24];
    int i;
    if (bd.win) return;
    memset(&bd, 0, sizeof bd);
    snprintf(bd.mac, sizeof bd.mac, "%s", mac);
    if (!bd_read()) { /* the device left the list since the row was drawn */
        memset(&bd, 0, sizeof bd);
        bp_layout();
        return;
    }
    bd.win = window_open("m1plus_btdevice");
    if (!bd.win) {
        memset(&bd, 0, sizeof bd);
        return;
    }
    widget_on(bd.win, EVT_DESTROY, bd_on_destroy, bd.win);
    widget_on(bd.win, EVT_WINDOW_WILL_OPEN, bd_on_will_open, (void *)0);
    widget_on(bd.win, EVT_WINDOW_TO_FG, bd_on_fg, (void *)0);
    widget_on(bd.win, EVT_WINDOW_TO_BG, bd_on_bg, (void *)0);
    m1_bind(bd.win, "btn_return", m1_on_back, (void *)0);
    m1_bind(bd.win, "btn_backtoplayer", m1_on_player, (void *)0);
    bd.sv = widget_lookup(bd.win, "btdevice_scrollview", 1);
    bd.fade = widget_lookup(bd.win, "img_nb_fade", 1);
    bd.title = widget_lookup(bd.win, "label_title", 1);
    bd.link = m1_bind(bd.win, "bd_row_link", bd_on_link, (void *)0);
    bd.link_t = widget_lookup(bd.win, "bd_link_t", 1);
    bd.vol = widget_lookup(bd.win, "bd_row_vol", 1);
    bd.dn = m1_bind(bd.win, "bd_vol_dn", bd_on_dn, (void *)0);
    bd.up = m1_bind(bd.win, "bd_vol_up", bd_on_up, (void *)0);
    bd.forget = m1_bind(bd.win, "bd_row_forget", bd_on_forget, (void *)0);
    for (i = 0; i < 2; i++) {
        snprintf(n, sizeof n, "bd_gap%d", i);
        bd.gap[i] = widget_lookup(bd.win, n, 1);
        snprintf(n, sizeof n, "bd_nm%d", i);
        bd.nm[i] = widget_lookup(bd.win, n, 1);
        snprintf(n, sizeof n, "bd_name%d", i);
        bd.name[i] = widget_lookup(bd.win, n, 1);
        if (!bd.gap[i] || !bd.nm[i] || !bd.name[i]) bd.sv = (void *)0;
    }
    if (!bd.sv || !bd.title || !bd.link || !bd.link_t || !bd.vol || !bd.dn || !bd.up || !bd.forget) {
        navigator_back(); /* an asset that is not ours: the destroy handler frees what exists */
        return;
    }
    bd_fit_name();
    widget_on(bd.sv, EVT_SCROLL, wf_on_scroll, &bd);
    widget_on(bd.sv, EVT_SCROLL_END, wf_on_scroll, &bd);
    bd.fg = 1;
    bd.timer = timer_add(bd_tick, (void *)0, BD_TICK_MS);
    if (!bd.timer) {
        navigator_back();
        return;
    }
    bd.vol_on = bd.cur.state == BS_DEV_CONNECTED && bs_volume_ok();
    bd.sig = 1 + (unsigned)bd.cur.state + 4 * (unsigned)bd.vol_on;
    bd_layout();
}

/* The info glyph of a paired device: its page. */
static void bp_open_info(const char *mac) { bd_open(mac); }

static int bp_on_dev(void *ctx, void *e) {
    int s = (int)(long)ctx - 1, i, pt[2];
    char mac[sizeof bp.dev[0].mac];
    if (bs_modal() || s < 0 || s >= BP_ROWS || !bp.on) return RET_OK;
    i = bp.map[s];
    if (i < 0 || i >= bp.ndev) return RET_OK;
    snprintf(mac, sizeof mac, "%s", bp.dev[i].mac); /* (a copy: the actions refill the list) */
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(bp.r[s].row, pt);
    if (s < BP_MY && pt[0] >= BP_INFO_X)
        bp_open_info(mac);
    else
        bp_link(mac);
    return RET_OK;
}

static int bp_on_back(void *ctx, void *e) {
    bs_close();
    return m1_on_back(ctx, e);
}

static int bp_on_player(void *ctx, void *e) {
    bs_close();
    return m1_on_player(ctx, e);
}

/* Stock's 200 ms timer: nothing while another window is in front or a dialog of ours is up; bs_tick counts the search down and says when the list is to be laid out again. A change the redraw flag
 * did not announce (Bluetooth switched elsewhere, a search that ended) is caught by comparing the three things the layout shows. */
static int bp_tick(const void *timer) {
    (void)timer;
    if (!bp.win) return RET_OK;
    if (!bp.fg || bs_modal()) return RET_REPEAT;
    if (bs_tick() & BS_T_REBUILD || bp.on != bs_on() || bp.starting != bs_starting() || bp.scanning != bs_scanning())
        bp_layout();
    else
        bp_spinner();
    return RET_REPEAT;
}

/* The window is about to open: stock has just resolved every widget's style, so the names cut at open (in the default style's smaller font) are cut again in the row's style. */
static int bp_on_will_open(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (bp.win) bp_layout();
    return RET_OK;
}

/* Back in front (from the codec picker, a dialog): the state is read again; stock's handler rebuilds its list. The search was stopped when the page went to the background. */
static int bp_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    bp.fg = 1;
    if (bp.win) bp_layout();
    return RET_OK;
}

static int bp_on_bg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    bp.fg = 0;
    bs_close();
    return RET_OK;
}

static int bp_on_close(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    bs_close();
    return RET_OK;
}

static int bp_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != bp.win) return RET_OK; /* an earlier window's end leaves a newer page alone */
    bs_close();
    m1_timer_stop(&bp.timer);
    memset(&bp, 0, sizeof bp);
    return RET_OK;
}

/* The hook at the Bluetooth row of the stock All System Settings hub (tools/pod.py BTHUB_SITE, docs/modules/payload.md hook 32): stock's row is `navigator_to("systemset/bluetooth_page")` and this call takes its
 * place with the same argument (the delay slot still loads it). Our page opens unless the kill switch exists or the page will not open; both leave stock's page, opened by stock's navigator_to (its init
 * starts a search on every open). Stock ignores the result. A tap on the row only: no state, no timer, not on the boot path. */
int bt_hub_open(const char *name) {
    if (access(KILL_SD, F_OK) != 0 && btpage_open() == 0) return 0;
    return navigator_to(name);
}

/* Settings > Bluetooth. 0 once the page is up (or already open); -1 when it could not open (nothing is left of it): the caller opens the stock page. */
int btpage_open(void) {
    char n[24];
    int i;
    if (bp.win) return 0;
    memset(&bp, 0, sizeof bp);
    bp.win = window_open("m1plus_bluetooth");
    if (!bp.win) {
        memset(&bp, 0, sizeof bp);
        return -1;
    }
    widget_on(bp.win, EVT_DESTROY, bp_on_destroy, bp.win);
    widget_on(bp.win, EVT_WINDOW_WILL_OPEN, bp_on_will_open, (void *)0);
    widget_on(bp.win, EVT_WINDOW_TO_FG, bp_on_fg, (void *)0);
    widget_on(bp.win, EVT_WINDOW_TO_BG, bp_on_bg, (void *)0);
    widget_on(bp.win, EVT_WINDOW_CLOSE, bp_on_close, (void *)0);
    m1_bind(bp.win, "btn_return", bp_on_back, (void *)0);
    m1_bind(bp.win, "btn_backtoplayer", bp_on_player, (void *)0);
    bp.sv = widget_lookup(bp.win, "bluetooth_scrollview", 1);
    bp.fade = widget_lookup(bp.win, "img_nb_fade", 1);
    bp.sw_row = m1_bind(bp.win, "bt_row_sw", bp_on_switch, (void *)0);
    bp.sw_img = widget_lookup(bp.win, "bt_sw_img", 1);
    bp.sw_hair = widget_lookup(bp.win, "bt_hair_sw", 1);
    bp.codec_row = m1_bind(bp.win, "bt_row_codec", bp_on_codec, (void *)0);
    bp.codec_label = widget_lookup(bp.win, "bt_codec_label", 1);
    bp.codec_val = widget_lookup(bp.win, "bt_codec_val", 1);
    bp.note = widget_lookup(bp.win, "bt_note", 1);
    bp.note_t = widget_lookup(bp.win, "bt_note_t", 1);
    bp.hdr_my = widget_lookup(bp.win, "bt_hdr_my", 1);
    bp.hdr_oth = widget_lookup(bp.win, "bt_hdr_oth", 1);
    bp.spin_img = widget_lookup(bp.win, "bt_hdr_oth_spin", 1);
    bp.search_row = m1_bind(bp.win, "bt_row_search", bp_on_search, (void *)0);
    for (i = 0; i < BP_ROWS; i++) {
        snprintf(n, sizeof n, "bt_row%d", i);
        bp.r[i].row = m1_bind(bp.win, n, bp_on_dev, (void *)(long)(i + 1));
        snprintf(n, sizeof n, "bt_chk%d", i);
        bp.r[i].chk = widget_lookup(bp.win, n, 1);
        snprintf(n, sizeof n, "bt_name%d", i);
        bp.r[i].name = widget_lookup(bp.win, n, 1);
        snprintf(n, sizeof n, "bt_hair%d", i);
        bp.r[i].hair = widget_lookup(bp.win, n, 1);
        if (i < BP_MY) {
            snprintf(n, sizeof n, "bt_info%d", i);
            bp.r[i].info = widget_lookup(bp.win, n, 1);
            if (!bp.r[i].info) bp.sv = (void *)0;
        }
        if (!bp.r[i].row || !bp.r[i].chk || !bp.r[i].name || !bp.r[i].hair) bp.sv = (void *)0;
    }
    if (!bp.sv || !bp.sw_row || !bp.sw_img || !bp.sw_hair || !bp.codec_row || !bp.codec_label || !bp.codec_val ||
        !bp.note || !bp.note_t || !bp.hdr_my || !bp.hdr_oth || !bp.spin_img || !bp.search_row) {
        navigator_back(); /* an asset that is not ours: the destroy handler frees what exists */
        return -1;
    }
    bp_spin_place();
    widget_on(bp.sv, EVT_SCROLL, wf_on_scroll, &bp);
    widget_on(bp.sv, EVT_SCROLL_END, wf_on_scroll, &bp);
    bp.fg = 1, bp.crow = -1;
    bp.timer = timer_add(bp_tick, (void *)0, BP_TICK_MS);
    if (!bp.timer) {
        navigator_back();
        return -1;
    }
    bs_open(); /* stock's page init: with Bluetooth on and no start running, the search begins as the page opens */
    bp_layout();
    return 0;
}
