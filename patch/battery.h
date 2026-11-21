/* Battery Percentage (patch/battery.c, docs/modules/battery.md "The percentage"): constants the payload and test/pod/battery.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define BP_FILE \
    "/mnt/data/m1plus/battery-percentage" /* "1" = on, anything else or missing = off (Settings > Battery) */
#define BP_TMP "/mnt/data/m1plus/battery-percentage.tmp"
#define BP_GAUGE \
    "/sys/class/power_supply/battery/capacity" /* the AXP2101 fuel gauge: an integer 0..100 and a newline */
#define BP_VOLT \
    "/sys/class/power_supply/battery/voltage_now" /* microvolts and a newline: read only when the gauge says 0 */
#define BP_EMPTY_UV \
    3535001 /* below this, stock's get_battery_capacity buckets the battery as 0 (0x35f099 at 0x4e6ec4): a gauge 0 is believed */
#define BP_LABEL "pod_pct" /* the hidden number in the status bar's battery (tools/statusbar.py battery_parts) */
#define BP_LABEL_DD "pod_pct_dd" /* its twin in the pull-down's own bar (dropdown_dialog.bin) */
#define BP_LABEL_LK "pod_pct_lk" /* the lock screen's (tools/mod_lockscreen.py) */
#define BP_BG "pod_pct_bg" /* the lighter grey under the level, shown with the number so that its black digits read */
#define BP_BG_DD "pod_pct_bg_dd"
#define BP_BG_LK "pod_pct_bg_lk"

#define BP_LOW \
    5 /* a gauge reading of at most this, on battery, is stored as 0: stock's red bar_lowpower (and its other low-battery readers) */

void bp_lock(
    void *win); /* the lock screen's init: show the percentage in its label at once (setting on, gauge readable) */
void bp_pulldown(void *dlg); /* the pull-down's init: the same for its label BP_LABEL_DD */
int battery_gauge(void); /* the gauge, 0..100, or -1 (patch/battery.c; the Charge Limit's input too) */
int bp_light_on(
    int level); /* the hooks at screen_action's two toolSetBackLight calls (tools/pod.py LIGHT_ON_SITE, LIGHT_OFF_SITE): repaint at once on wake */
int bp_light_off(int level);
