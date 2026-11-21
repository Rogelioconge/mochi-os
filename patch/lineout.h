/* Line Out pill (patch/lineout.c, docs/modules/lineout.md): constants the payload and test/pod/lineout.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define LO_PILL \
    "pod_lo" /* the hidden amber pill image tools/statusbar.py puts after label_volume in view_bar_left (both bar copies) */
#define LO_W_PARENT 0x44 /* widget->parent (pinned by BATTERY_PINS against widget_set_visible) */
#define EQ_IND \
    "pod_eq" /* the hidden "EQ" label tools/statusbar.py puts after the pill in view_bar_left (both bar copies); shown while the Equalizer is on */
#define LO_GROUP "view_bar_left" /* the bar's left group, where the pill and the EQ mark sit */
#define EQ_DIGITAL \
    "img_digital" /* stock's digital-out glyph, the left group's last child: while it shows there is no room for the EQ mark before the clock */
#define SYNC_IND \
    "pod_sync" /* the hidden sync icon tools/statusbar.py puts in view_bar_right (both bar copies); shown while a cover or duration build runs */
#define SLEEP_IND \
    "pod_sleep" /* the hidden moon icon tools/statusbar.py puts in view_bar_right (both bar copies); shown while a Sleep Timer is running */
/* The moon's room test (patch/lineout.c lo_sleep_fits): it shows only if the right group's visible ink, the moon included, spans at most SLEEP_ROOM px, so it never pushes the Bluetooth box into the clock.
 * The group lays out right-aligned with SLEEP_GAP spacing; each visible peer counts its box, the Bluetooth box only its ink (the glyph or codec badge at the box's right edge; an image not listed counts the whole box). */
#define SLEEP_ROOM \
    95 /* the group's right end (x 284) less the 12 h clock's widest ink end (x 186, "10:59 AM") and 3 px clearance */
#define SLEEP_GAP 4 /* tools/statusbar.py GAP */
#define SLEEP_BT "img_btclass" /* stock's Bluetooth box, the group's first child */
#define SLEEP_SYNCLINK "img_synclink" /* stock's SyncLink glyph */
#define SLEEP_WIFI "img_wifi" /* stock's Wi-Fi glyph */
#define SLEEP_SHOT "pod_shot" /* the screenshot mark (system bar only) */
#define SLEEP_PCT "pod_pct" /* the battery percentage (patch/battery.h BP_LABEL) */
#define SLEEP_PCT_DD "pod_pct_dd" /* its twin in the pull-down's bar (BP_LABEL_DD) */
#define SLEEP_BT_GLYPH "bar_bt" /* Bluetooth on: ink 11 px */
#define SLEEP_BT_CON "bar_btcon" /* connected: ink 11 px */
#define SLEEP_INK_GLYPH 11
#define SLEEP_BT_AAC "bar_aac" /* the AAC badge: ink 16 px */
#define SLEEP_INK_AAC 16
#define SLEEP_BT_SBC "bar_sbc" /* the SBC badge: ink 28 px */
#define SLEEP_INK_SBC 28
#define SLEEP_BT_LDAC "bar_ldac" /* the LDAC badge: ink 38 px */
#define SLEEP_INK_LDAC 38

void lo_bar_refresh(
    void *
        win); /* a window's bar copy at its init: the EQ mark follows stock's digital-out glyph at once (patch/lineout.c) */
