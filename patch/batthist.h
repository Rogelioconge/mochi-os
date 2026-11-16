/* Battery History (patch/batthist.c, docs/modules/batthist.md): constants the payload and test/pod/batthist.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define BH_FILE \
    "/mnt/data/m1plus/battery-history" /* "1" = on, anything else or missing = off (Settings > Battery > Battery History) */
#define BH_TMP "/mnt/data/m1plus/battery-history.tmp"
#define BH_DATA \
    "/mnt/data/m1plus/battery-history.bin" /* the ring: BH_HEAD + BH_BUCKETS * 8 bytes, never grows; deleted when the setting goes off */
#define BH_DATA_TMP "/mnt/data/m1plus/battery-history.bin.tmp"
#define BH_STATUS \
    "/sys/class/power_supply/battery/status" /* the kernel's power_supply status text: Charging, Full, Not charging, Discharging, Unknown */

#define BH_BUCKETS 96 /* 96 buckets of BH_SECS = the last 24 hours */
#define BH_SECS \
    900 /* one bucket: a quarter hour of wall clock (UTC, so the same bucket edges in every time zone with a 15 minute offset) */
#define BH_PERIOD 15 /* seconds between two samples */
#define BH_GAUGE 60 /* seconds between two gauge reads (and one at once after a standby) */
#define BH_NONE 0xff /* a bucket's level when no gauge reading is known */
#define BH_SUSP 5 /* BOOTTIME minus MONOTONIC seconds in one step that count as a standby */
#define BH_SUSP_DROP 30 /* standby seconds since the last gauge read after which a drop is the standby's */
#define BH_JUMP \
    120 /* seconds the wall clock may differ from BOOTTIME in one step before it counts as set (forward: a gap, backward: the history is dropped) */
#define BH_MIN_WALL 1577836800 /* 2020-01-01: an earlier wall clock is an unset RTC, nothing is recorded */

#define BH_F_CHG \
    1 /* flags: on external power at some sample of the bucket (its drops are not attributed, and rates leave it out) */
#define BH_F_GAP 2 /* no data: the player was off, the clock jumped or nothing was recorded yet */

/* One bucket, 8 bytes; times in units of 8 seconds, drops in percent. */
struct bh_bucket {
    unsigned char level; /* the gauge at the end of the bucket, 0..100, BH_NONE unknown */
    unsigned char flags; /* BH_F_* */
    unsigned char on; /* screen on */
    unsigned char play; /* playing with the screen off */
    unsigned char
        cov; /* known time: sampled, or standby seen across a gap (on and play are parts of it, the rest is idle / standby) */
    unsigned char d_on, d_play,
        d_idle; /* percent the gauge fell, attributed to the screen on / playing with the screen off / idle and standby */
};

/* What the History page draws (bh_snapshot). */
struct bh_view {
    unsigned head; /* the newest bucket's number (wall seconds / BH_SECS) */
    struct bh_bucket b[BH_BUCKETS]; /* oldest first; b[BH_BUCKETS - 1] is the open bucket, head */
    unsigned t_on, t_play, t_idle; /* seconds on battery (buckets with no charging and data) per state */
    unsigned d_on, d_play, d_idle; /* percent dropped in those buckets per state */
    unsigned act_on,
        act_play; /* seconds of screen on / playing with the screen off over every bucket with data, charging included */
    long
        unplug_at; /* since last charge: wall time the charger was last removed, 0 none seen yet (the counters below are then 0) */
    unsigned unplug_lvl; /* the gauge then, BH_NONE unknown */
    unsigned level; /* the gauge now (the open bucket's level), BH_NONE unknown */
    unsigned sc_play, sc_on,
        sc_total; /* seconds on battery since unplug_at: playing with the screen off, screen on, all of it (awake, idle and standby) */
};

int bh_setting(void); /* Settings > Battery > Battery History: 1 on, 0 off (the default) */
int bh_toggle(void); /* flip it: the new state, or -1; off stops the recorder and deletes the data */
void bh_poll(
    void); /* from bp_capacity (patch/battery.c) every status bar tick: starts the recorder thread while the setting is on */
/* The thread's pieces, public so that the test runs them one at a time: bh_load reads the file, bh_sample takes one sample, bh_main is the loop (load, then sample and sleep BH_PERIOD while the setting is on). */
void bh_load(void);
void bh_sample(void);
void *bh_main(void *arg);
int bh_snapshot(
    struct bh_view *
        out); /* 1 and the view when the setting is on and a bucket is open, else 0 (out zeroed); safe from the UI thread */
void bhpage_show(
    void *
        win); /* patch/bhpage.c: the Battery History page's items for the setting's state (page_refresh in patch/m1plus.c: as the page opens, back in front, the switch turned) */
