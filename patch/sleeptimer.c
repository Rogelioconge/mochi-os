/* M1+ Music Sleep Timer page (docs/modules/sleeptimer.md): the state behind our page's check rows. A row picked on our page stays checked while its timer counts down (the pick is remembered in .scratch).
 *
 * The state is stock's own, the two words systemset/powermanager_page's view_sleep keeps: the byte sleepflag (the switch) and the word sleep_time, the seconds left. Stock's Power page stays reachable under
 * All System Settings and reads the same two words. Nothing of ours is saved: stock saves nothing either (no config key; the timer is gone at the next boot). The setters store what stock's handlers store, in
 * their order (tools/pod_pins.py SLEEPTIMER_PINS), and nothing else: the switch (0x4a9ae0) xors the byte and zeroes the word, Back (0x4a91d0) stores (hours * 60 + minutes) * 60; neither calls a save or
 * reset_poweroptions_timer. stock's own handlers need their widgets for the refresh, so they are not called. */
#include "offsets.inc"
#include "stock.h"
#include "entries.h"
#include "home.h"
#include "common.h"

#define SLEEP_N 7 /* the rows: Off and six times (tools/pod_pages.py SLEEP_VALUES, SLEEP_SECONDS) */

#define sleep_flag (*(volatile unsigned char *)SLEEP_FLAG)
#define sleep_time (*(volatile int *)SLEEP_TIME)

static const int st_secs[SLEEP_N] = {0, 900, 1800, 2700, 3600, 5400, 7200}; /* what each row leaves in the word */

/* The row picked on our page and the word as last seen (zero-initialised .scratch): the word counts down, so the picked row stays checked while the word only goes down; 0: none remembered. */
static struct {
    int row;
    int last;
} st_pick __attribute__((section(".scratch")));

/* The row to check: 0 Off while stock's byte is 0. A row picked on our page stays checked while 0 < the word <= the last seen word (the same timer counting down); a word above it or 0 is another timer (set on
 * stock's Power page) or the end, and the pick is forgotten. Without a pick: a time while the word is exactly that time, else -1. A time set on stock's page that is lower than the last seen word cannot be told
 * from the countdown and keeps the old check. */
int st_choice(void) {
    int i, t = sleep_time;
    if (!sleep_flag) {
        st_pick.row = 0;
        return 0;
    }
    if (st_pick.row) {
        if (t > 0 && t <= st_pick.last) {
            st_pick.last = t;
            return st_pick.row;
        }
        st_pick.row = 0;
    }
    for (i = 1; i < SLEEP_N; i++)
        if (t == st_secs[i]) return i;
    return -1;
}

/* Choose a row as stock's page does. Off is the switch while it is on: the byte xor 1 (0), the word 0. A time from Off is the switch (the byte 1, the word 0), then the selectors' store, the word in seconds;
 * from a running timer it is the selectors' store alone. Nothing is saved and no countdown call is made, as in stock. 0, or -1 for a row there is not. */
int st_set(int v) {
    if (v < 0 || v >= SLEEP_N) return -1;
    if (v == 0) {
        st_pick.row = 0;
        if (!sleep_flag) return 0;
        sleep_flag = 0;
        sleep_time = 0;
        return 0;
    }
    if (!sleep_flag) {
        sleep_flag = 1;
        sleep_time = 0;
    }
    sleep_time = st_secs[v];
    st_pick.row = v;
    st_pick.last = st_secs[v];
    return 0;
}

/* Time Left: the seconds left as H:MM, rounded up to the next minute (59 s reads 0:01), language-free. 1 while a timer runs (the byte on and the word above 0), else 0 and an empty text. */
int st_left_text(char *buf, unsigned n) {
    int t = sleep_time, m;
    buf[0] = 0;
    if (!sleep_flag || t <= 0) return 0;
    m = (t + 59) / 60;
    snprintf(buf, n, "%d:%02d", m / 60, m % 60);
    return 1;
}

/* The page's own refresh timer, added when the window opens and removed with it (and while it is in the background): the countdown moves a second at a time, the text is read again every ST_MS. */
#define ST_MS 4000
static struct {
    void *win;
    int page;
    unsigned timer;
} st __attribute__((section(".scratch")));

static int st_tick(const void *timer) {
    (void)timer;
    if (!st.win) return RET_OK;
    pod_page_refresh(st.page);
    return RET_REPEAT;
}

static void st_stop(void) { m1_timer_stop(&st.timer); }

/* The generic page's own destroy and foreground handlers (patch/m1plus.c on_page_gone, on_page_fg) call these two; only the background event is bound here. */
void st_gone(void) {
    st_stop();
    st.win = (void *)0;
}

void st_front(void) {
    if (st.win && !st.timer) st.timer = timer_add(st_tick, (void *)0, ST_MS);
}

static int st_on_background(void *ctx, void *e) {
    (void)e;
    if (ctx == st.win) st_stop();
    return RET_OK;
}

void st_opened(void *win, int page) {
    st_stop();
    st.win = win;
    st.page = page;
    if (!widget_on(win, EVT_WINDOW_TO_BG, st_on_background, win)) {
        st.win = (void *)0; /* no timer: the page still follows each choice and each return to the front */
        return;
    }
    st.timer = timer_add(st_tick, (void *)0, ST_MS);
}
