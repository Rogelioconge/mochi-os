/* M1+ Music Battery Percentage: the fuel gauge's exact charge, as a number beside the battery outline (docs/modules/battery.md "The percentage").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Stock never reads the AXP2101 gauge: get_battery_capacity (0x4e6dd8) buckets the battery voltage into 0/20/40/60/80/100 (another table, and a +10 animation, while
 * charging) and leaves the result in the global power_capacity (0xa059ec), which show_sysbar_face (0x544b48, the status bar's 1 s timer) and the pull-down's face read
 * for the fill; the return value is dropped there. The one hook is the call-site word `jalr get_battery_capacity` at 0x5450f8 in show_sysbar_face, now `jal bp_capacity`.
 * bp_capacity runs stock's function first, and then, only while Settings > Battery > Battery Percentage is on and the kill switch /mnt/mmc/m1plus-off is absent and
 * /sys/class/power_supply/battery/capacity reads a plain integer 0..100, stores that percentage in power_capacity (so the fill, the charging picture's fill and the
 * pull-down's bar use the real level, charging included) and shows "N%" in the label pod_pct that sits left of the outline (its twin pod_pct_dd in the pull-down's bar).
 * At BP_LOW (5) percent or less on battery (and when stock's own bucket is 0) the stored value is 0, which is how stock's own test shows the red bar_lowpower (battery.md "BP_LOW").
 * The lock screen (screensaver_page) draws its gauge from the same power_capacity; its label pod_pct_lk is set by the same tick and, at once, by bp_lock at the page's init. The pull-down's label pod_pct_dd is set at once the same way, by bp_pulldown at its init.
 * In every other case the stock value stays and the labels are hidden (visible and sensitive off). The icon pictures stay stock's (charging, low).
 * The same tick then runs the Charge Limit's check (patch/charging.c chg_tick: the kill switch and, when it was read here, the gauge).
 * Two more hooks, the call-site words `jalr toolSetBackLight` at 0x4e71cc (on) and 0x4e71fc (off) in screen_action (0x4e71a4), now `jal bp_light_on` / `jal bp_light_off`, repaint the
 * status bar when the screen wakes (battery.md "The wake repaint"): cost on a wake only (one access, ~34 ms), none while the screen stays lit.
 *
 * The right icon group lays its visible children out right-aligned, so the label (the group's last child but the Screenshot camera, hidden in the asset) makes the icons
 * to its left move aside by its width; the width follows the text (BP_W2 .. BP_W4, measured at build time), and a change of it asks the group to lay out again.
 *
 * Cost: one access (the kill switch), and, with the setting on, one open / read / close of a 4 byte file and a lookup in the small status bar tree per second; the setting
 * is cached (read at the first tick, kept by the Settings switch). Not on the boot path (tools/reach.py), but the first call comes with the status bar window at UI start, so with the setting off (the default) it adds only stock's own call, the access and the cached flag.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "battery.h"
#include "charging.h"
#include "batthist.h"

static struct {
    int state; /* the setting: 0 not read yet, 1 off, 2 on */
    int shown; /* a label may be showing: the hide path has work to do */
    int dark; /* the backlight went off (bp_light_off) and has not come on since: the wake repaint is due */
} bp __attribute__((section(".scratch")));

static int bp_read_setting(void) { return set_read(BP_FILE, 0) == '1'; }

/* Settings > Battery > Battery Percentage: 1 on, 0 off (the default). */
int battpct_setting(void) { return bp_read_setting(); }

int battpct_toggle(void) {
    int next = !bp_read_setting();
    if (home_set_digit(BP_FILE, BP_TMP, next, 1) < 0) return -1;
    bp.state = next ? 2 : 1;
    return next;
}

/* The gauge as a plain integer 0..100 (digits, then the end or a newline): the value, else -1. Also the Charge Limit's input (patch/charging.c). */
int battery_gauge(void) {
    char b[8];
    int fd = open(BP_GAUGE, O_RDONLY, 0), n, i = 0, v = 0;
    if (fd < 0) return -1;
    n = read(fd, b, sizeof b - 1);
    close(fd);
    if (n < 1) return -1;
    b[n] = 0;
    while (i < n && b[i] >= '0' && b[i] <= '9' && i < 4) v = v * 10 + (b[i++] - '0');
    if (i == 0 || i > 3 || v > 100) return -1;
    if (i < n && b[i] == '\n') i++;
    return i == n ? v : -1;
}

/* Show the percentage in the label w (the number as its text, its width fitted), or hide it for pct < 0. */
static void bp_label(void *w, int pct, int fit) {
    char t[5];
    int n = 0;
    if (!w) return;
    if (pct < 0) {
        widget_set_visible(w, 0, 0);
        widget_set_sensitive(w, 0);
        return;
    }
    if (pct >= 100)
        t[n++] = '1', t[n++] = '0', t[n++] = '0';
    else {
        if (pct >= 10) t[n++] = (char)('0' + pct / 10);
        t[n++] = (char)('0' + pct % 10);
    }
    t[n++] = '%';
    t[n] = 0;
    if (fit) {
        int want = n == 4 ? BP_W4 : n == 3 ? BP_W3 : BP_W2;
        int *geo = (int *)w;
        if (geo[BP_W_W / 4] != want) {
            widget_resize(w, want, geo[BP_W_H / 4]);
            if (geo[BP_W_PARENT / 4]) widget_set_need_relayout_children((void *)geo[BP_W_PARENT / 4]);
        }
    }
    widget_set_text_utf8(w, t);
    widget_set_visible(w, 1, 0);
}

/* A page's label at its init (after stock's init and only without the kill switch): the percentage at once, where the status bar's tick would show it up to a second later. The label is hidden in
 * the asset, so with the setting off or an unreadable gauge nothing is touched. */
static void bp_init_label(void *win, const char *name, int fit) {
    int pct;
    if (bp.state == 0) bp.state = bp_read_setting() ? 2 : 1;
    if (bp.state != 2 || (pct = battery_gauge()) < 0) return;
    bp_label(widget_lookup(win, name, 1), pct, fit);
    bp.shown = 1;
}

/* The lock screen's label (patch/lockscreen.c). Its box is fixed (the widest text, right-aligned). */
void bp_lock(void *win) { bp_init_label(win, BP_LABEL_LK, 0); }

/* The pull-down's label (patch/pulldown.c m1plus_pulldown_init): fitted like the status bar's. */
void bp_pulldown(void *dlg) { bp_init_label(dlg, BP_LABEL_DD, 1); }

/* The hook (tools/pod.py BATTERY_SITE): stock's get_battery_capacity, then the real percentage when asked for. Returns what stock's function returned, or the percentage. */
int bp_capacity(void) {
    int cap = get_battery_capacity(), pct = -1, killed = access(KILL_SD, F_OK) == 0;
    void *bar, *wm;
    if (!killed) {
        if (bp.state == 0) bp.state = bp_read_setting() ? 2 : 1;
        if (bp.state == 2) pct = battery_gauge();
    }
    chg_tick(killed, pct); /* the Charge Limit (patch/charging.c), on the same tick */
    if (!killed) bh_poll(); /* Battery History (patch/batthist.c): starts its recorder thread while the setting is on */
    if (pct < 0 && !bp.shown) return cap; /* off and nothing to hide: stock, no lookups */
    if (pct >= 0) {
        /* stock picks bar_lowpower only for power_capacity <= 0, and only when it reaches that test (not on the charging / full pictures: show_sysbar_face 0x54510c..0x54514c) */
        int low_test = *(int *)POWER_EXT != 1 ||
                       (*(int *)POWER_USBSTATE == 2 && *(char *)POWER_FLAG == 1 && *(int *)USBDAC_CHARGEFLAG == 0);
        *(int *)POWER_CAPACITY = cap = low_test && (pct <= BP_LOW || cap <= 0) ? 0 : pct;
    }
    bar = *(void **)SYSTEM_BAR;
    bp_label(bar ? widget_lookup(bar, BP_LABEL, 1) : (void *)0, pct, 1);
    wm = window_manager();
    bp_label(wm ? widget_lookup(wm, BP_LABEL_DD, 1) : (void *)0, pct, 1);
    bp_label(wm ? widget_lookup(wm, BP_LABEL_LK, 1) : (void *)0, pct, 0);
    bp.shown = pct >= 0;
    return cap;
}

/* The wake repaint (tools/pod_pins.py LIGHT_ON_SITE / LIGHT_OFF_SITE): screen_action's two toolSetBackLight calls, the one place every path (awake_screen, the power key) turns the backlight
 * on or off. Off: remember it (bp.dark). On, after an off: before the backlight comes on, on the UI thread, show_sysbar_face(0) (the status bar's own timer call; it runs bp_capacity, so the
 * battery labels follow), widget_invalidate_force(wm, null) (the whole screen dirty), then the main loop's own pair window_manager_check_and_layout (a label whose width
 * changed asks its group to lay out again) and window_manager_paint, so the first frame the panel shows is a fresh one. A screen_action(1)
 * while lit paints nothing. The kill switch present: toolSetBackLight only. */
int bp_light_on(int level) {
    if (bp.dark && access(KILL_SD, F_OK) != 0) {
        void *wm = window_manager();
        show_sysbar_face(0);
        if (wm) widget_invalidate_force(wm, (void *)0), window_manager_check_and_layout(wm), window_manager_paint(wm);
    }
    bp.dark = 0;
    return toolSetBackLight(level);
}

int bp_light_off(int level) {
    bp.dark = 1;
    return toolSetBackLight(level);
}
