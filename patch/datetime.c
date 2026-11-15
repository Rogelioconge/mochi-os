/* M1+ Music Settings > General > Date & Time (docs/modules/datetime.md): the state behind our page's switches, value rows and pickers.
 *
 * Every state is stock's own and stays under All System Settings: systemset/typedatetime_page (the 24-hour switch), autosynctime_page (Set Automatically and the zone rows) and datetime_page (manual entry). Nothing of
 * ours is saved; the only thing we hold is the date being typed (ed), in memory until Set Date / Set Time. The setters repeat stock's handlers' stores, saves and calls in their order (tools/pod_pins.py DATETIME_PINS)
 * and nothing else: stock's handlers need their own widgets for the refresh, so they are not called. Like stock's confirm handler, dt_apply runs system() twice (date -s, hwclock -wu) on the UI thread. */
#include "offsets.inc"
#include "stock.h"
#include "entries.h"

#define auto_flag (*(volatile unsigned char *)AUTO_TIME)
#define sync_need (*(volatile unsigned char *)SYNC_NEED)
#define hour24 (*(volatile unsigned char *)TIME_24H)
#define time_zone (*(volatile int *)TIME_ZONE)

#define TZ_COUNT \
    ((int)(sizeof((const char *[])TIMEZONE_NAMES) / \
           sizeof(const char *))) /* our table's 43 zones (tools/timezones.py) */
#define TZ_DEFAULT 22 /* config_init's default (Shanghai) */

#define YEAR_MIN 2022 /* stock's manual time page: the year selector's range (its init clamps anything else to 2022) */
#define YEAR_MAX 2050

/* The date being typed: year, month, day, hour, minute (field 0 .. 4), read from the clock when the Date or Time page opens. */
static int ed[5] __attribute__((section(".scratch")));

/* Set Automatically: stock's switch (0x4a2618): the byte and the sync request both stored, then the save of AUTOSYNCTIME. The request is what networktime_adjust_thd (a thread, once a second) acts on when Wi-Fi is
 * up, so nothing runs here. The new state. */
int dt_auto(void) { return auto_flag != 0; }

int dt_auto_toggle(void) {
    if (auto_flag) {
        sync_need = 0;
        auto_flag = 0;
    } else {
        sync_need = 1;
        auto_flag = 1;
    }
    write_int_config(auto_flag, "SYSSET", "AUTOSYNCTIME");
    return auto_flag != 0;
}

/* 24-Hour Time: stock's switch (0x4aeb50): the byte xor 1 stored in the delay slot of change_time24h_12h (the status bar clock's format), then the save of TIME24H. The new state. */
int dt_24h(void) { return hour24 != 0; }

int dt_24h_toggle(void) {
    unsigned char next = (unsigned char)(hour24 ^ 1);
    hour24 = next;
    change_time24h_12h(next);
    write_int_config(hour24, "SYSSET", "TIME24H");
    return hour24 != 0;
}

/* Time Zone: stock's saved index (the word time_zone, [SYSSET] TIMEZONE; config_init keeps an index below our table's 43, patch/timezones.c). A zone row's click (0x4a25b8) stores the index (nothing when it is the zone
 * already), saves TIMEZONE, then calls select_timezone, which setenv("TZ") from our table. 0, or -1 for an index we do not have. */
int dt_zone(void) {
    int z = time_zone;
    return z >= 0 && z < TZ_COUNT ? z : TZ_DEFAULT;
}

int dt_zone_set(int index) {
    if (index < 0 || index >= TZ_COUNT) return -1;
    if (time_zone == index) return 0;
    time_zone = index;
    write_int_config(index, "SYSSET", "TIMEZONE");
    select_timezone();
    return 0;
}

static int days_in(int year, int month) {
    static const unsigned char dim[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (month == 2 && (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0))) return 29;
    return dim[month >= 1 && month <= 12 ? month - 1 : 0]; /* (the callers pass 1 .. 12) */
}

/* The local clock as stock's pages read it: get_systime(&minute, &hour, &day, &month, &year) (it calls tzset, localtime). */
static void now(int *year, int *month, int *day, int *hour, int *minute) {
    get_systime(minute, hour, day, month, year);
}

/* The Date (0) and Time (1) rows' grey value: 2026-11-15, and 14:05 or 2:05 PM by 24-Hour Time. */
void dt_text(int which, char *buf, int n) {
    int y, mo, d, h, mi;
    now(&y, &mo, &d, &h, &mi);
    if (which == 0)
        snprintf(buf, n, "%04d-%02d-%02d", y, mo, d);
    else if (hour24)
        snprintf(buf, n, "%02d:%02d", h, mi);
    else
        snprintf(buf, n, "%d:%02d %s", h % 12 ? h % 12 : 12, mi, h < 12 ? "AM" : "PM");
}

/* Read the clock into the date being typed, as stock's manual page fills its selectors (0x4a58fc): a year outside 2022 .. 2050 is 2022, a month or day outside its range 1; ours also keeps the day inside the month. */
void dt_edit_start(void) {
    int y, mo, d, h, mi;
    now(&y, &mo, &d, &h, &mi);
    if (y < YEAR_MIN || y > YEAR_MAX) y = YEAR_MIN;
    if (mo < 1 || mo > 12) mo = 1;
    if (d < 1 || d > 31) d = 1;
    if (d > days_in(y, mo)) d = days_in(y, mo);
    ed[0] = y, ed[1] = mo, ed[2] = d;
    ed[3] = h >= 0 && h < 24 ? h : 0;
    ed[4] = mi >= 0 && mi < 60 ? mi : 0;
}

/* A field's grey value on the Date and Time pages. */
void dt_field_text(int field, char *buf, int n) {
    if (field < 0 || field > 4) field = 0;
    snprintf(buf, n, field >= 3 ? "%02d" : "%d", ed[field]);
}

/* The pickers' rows: arg = field * 4096 + value. */
int dt_chosen(int arg) {
    int f = arg >> 12;
    return f >= 0 && f <= 4 && ed[f] == (arg & 4095);
}

int dt_set(int arg) {
    int f = arg >> 12, v = arg & 4095;
    static const unsigned short lo[5] = {YEAR_MIN, 1, 1, 0, 0}, hi[5] = {YEAR_MAX, 12, 31, 23, 59};
    if (f < 0 || f > 4 || v < lo[f] || v > hi[f]) return -1;
    ed[f] = v;
    if (ed[2] > days_in(ed[0], ed[1]))
        ed[2] = days_in(ed[0], ed[1]); /* a day the month does not have becomes its last */
    return 0;
}

/* Set Date (0) or Set Time (1): stock's confirm handler (0x4a576c) reads its five selectors and calls set_systime(year, month, day, hour, minute), which sets the seconds to 0 and runs date -s and hwclock -wu.
 * Set Date keeps the clock's time of day and Set Time its date (stock's page holds both). Refused while Set Automatically is on (stock disables its Manual row then). 0, or -1. */
int dt_apply(int which) {
    int y, mo, d, h, mi;
    if (auto_flag) return -1;
    now(&y, &mo, &d, &h, &mi);
    if (which == 0)
        y = ed[0], mo = ed[1], d = ed[2];
    else
        h = ed[3], mi = ed[4];
    set_systime(y, mo, d, h, mi);
    return 0;
}
