/* The scrobble upload settings (docs/modules/scrobble.md "Settings"): the Scrobbling page's ListenBrainz, Last.fm and Upload Scrobbles rows and the two account pages (one Account row each).
 * All are Settings cards pages of patch/m1plus.c (tools/pod_pages.py SCROBBLING_PAGE, LB_PAGE, LF_PAGE), which binds the rows and asks this file for their texts and their taps; the upload and the
 * accounts are patch/scrobup.c's (one worker thread, an upload or a check). The accounts are the card's scrobble.ini, written on a computer: nothing here sets or removes one.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One timer (LB_TICK_MS), only while one of the three pages is up and a job is in flight or its result is not shown yet: it polls the job this file started (lbs.job), and only that one.
 * scrobup_owner and scrobup_kind are asked before every poll: the automatic upload's job, a job of another kind, or none, means the result is not ours, and nothing is read. An
 * automatic upload (patch/scrobble.c) is only watched (scrobup_busy) so that the rows follow it; once it is over scrobble_auto_collect takes its result, without a toast, so that it
 * never blocks a start here. With the screen dark the tick polls and nothing else: the toast and the rows wait for the first lit tick. While our job runs the tick sets
 * stock's standby countdown again once a second (reset_poweroptions_timer(1, 1, 0), as the Software Update page: standby would stop the Wi-Fi). A job that ends after both pages closed is
 * polled when one opens again. Nothing here runs at boot, from the main loop or without a tap or a page.
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "home.h"
#include "i18n.h"
#include "scrobble.h"
#include "scrobup.h"
#include "scrobpage.h"

#define LB_TICK_MS 500
#define LB_AWAKE_TICKS 2 /* the standby countdown is set again every second while our job runs */

static struct {
    unsigned timer, ticks;
    int pages; /* bit 0: the Scrobbling page is up, bit 1: the ListenBrainz page, bit 2: the Last.fm page */
    int job; /* the job this file started and has not polled the result of: 0 none, else 1 + SCROBUP_UPLOAD / SCROBUP_CHECK / SCROBUP_LFCHECK */
    int done, kind, res, sent, rej,
        auth; /* a result that was polled and is not shown yet (auth: scrobup_auth, the services that refused) */
    char last[SU_UP_LINE]; /* the upload record's last line, read when the page opens and when a job ended ("" none) */
} lbs __attribute__((section(".scratch")));

static int lb_tick(const void *timer);

/* Days since 1970-01-01 of a proleptic Gregorian date (Hinnant's days_from_civil). */
static long lb_days(long y, long m, long d) {
    long era, yoe, doy;
    y -= m <= 2;
    era = (y >= 0 ? y : y - 399) / 400, yoe = y - era * 400;
    doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
    return era * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468;
}

/* The upload record's last line (patch/scrobup.c su_record), read from the file's end. */
static void lb_last_load(void) {
    char buf[SU_UP_LINE + 1];
    int fd = m1_card_mounted() ? open(SC_UPLOADS, O_RDONLY, 0) : -1, n = 0, i;
    long size;
    lbs.last[0] = 0;
    if (fd < 0) return;
    size = lseek(fd, 0, 2);
    if (size > 0 && lseek(fd, size > SU_UP_LINE ? size - SU_UP_LINE : 0, 0) >= 0) n = read(fd, buf, SU_UP_LINE);
    close(fd);
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) --n;
    for (i = n; i > 0 && buf[i - 1] != '\n'; --i) {
    }
    if (n - i <= 0 || n - i >= SU_UP_LINE) return;
    memcpy(lbs.last, buf + i, (unsigned)(n - i));
    lbs.last[n - i] = 0;
}

/* n digits at p as a number, -1 when one is not a digit. */
static int lb_digits(const char *p, int n) {
    int v = 0;
    while (n--) {
        if (*p < '0' || *p > '9') return -1;
        v = v * 10 + (*p++ - '0');
    }
    return v;
}

/* The bytes from p to e are the word w. */
static int lb_is(const char *p, const char *e, const char *w) {
    while (p < e && *w && *p == *w) ++p, ++w;
    return p == e && !*w;
}

/* The page's one note under Auto Upload / Upload Scrobbles: its text and, when a record exists, "Last upload: Today 14:32 · Failed, 3 sent to ListenBrainz" (local time; no time
 * for a clock that was never set). The record is "2026-11-16T14:32:05Z auto ok listenbrainz=12 lastfm=12 rejected=0". */
static void lb_note_text(char *out, unsigned n) {
    static const char *const mon[12] = {"Jan %d", "Feb %d", "Mar %d", "Apr %d", "May %d", "Jun %d",
                                        "Jul %d", "Aug %d", "Sep %d", "Oct %d", "Nov %d", "Dec %d"};
    char when[48], part[96], res[8];
    int y, mo, d, hh, mm, ss, cnt[2] = {-1, -1}, k, w, field = 0;
    long t, now = time((long *)0);
    const char *p = lbs.last, *e;
    const int *q;
    unsigned o;
    snprintf(out, n, "%s", TR("Uploads when Wi-Fi is connected."));
    if (strlen(p) < 24 || p[4] != '-' || p[7] != '-' || p[10] != 'T' || p[13] != ':' || p[16] != ':' || p[19] != 'Z')
        return;
    y = lb_digits(p, 4), mo = lb_digits(p + 5, 2), d = lb_digits(p + 8, 2), hh = lb_digits(p + 11, 2),
    mm = lb_digits(p + 14, 2), ss = lb_digits(p + 17, 2);
    if (y < 0 || mo < 0 || mo > 12 || d < 0 || d > 31 || hh < 0 || mm < 0 || ss < 0) return;
    res[0] = 0;
    for (p += 20; *p;) { /* the words: mode, result, then name=count */
        while (*p == ' ') ++p;
        for (e = p; *e && *e != ' '; ++e) {
        }
        if (e > p) {
            const char *eq = p;
            while (eq < e && *eq != '=') ++eq;
            if (field == 1 && e - p < (long)sizeof res) memcpy(res, p, (unsigned)(e - p)), res[e - p] = 0;
            if (eq < e && e - eq > 1) {
                k = 0;
                for (w = 1; eq + w < e && eq[w] >= '0' && eq[w] <= '9'; ++w) k = k * 10 + eq[w] - '0';
                if (lb_is(p, eq, "listenbrainz")) cnt[0] = k;
                if (lb_is(p, eq, "lastfm")) cnt[1] = k;
            }
            ++field;
        }
        p = e;
    }
    if (!res[0]) return;
    when[0] = 0;
    t = lb_days(y, mo, d) * 86400L + hh * 3600L + mm * 60L + ss;
    if (y >= 2020 && now >= 1577836800L && (q = localtime(&t))) {
        int lt[9];
        long a, b;
        for (k = 0; k < 9; ++k) lt[k] = q[k]; /* (localtime's one buffer) */
        a = lb_days(lt[5] + 1900, lt[4] + 1, lt[3]);
        q = localtime(&now);
        if (q) {
            b = lb_days(q[5] + 1900, q[4] + 1, q[3]);
            if (a == b)
                snprintf(when, sizeof when, "%s", TR("Today"));
            else if (a == b - 1)
                snprintf(when, sizeof when, "%s", TR("Yesterday"));
            else
                snprintf(when, sizeof when, TR(mon[lt[4] < 0 || lt[4] > 11 ? 0 : lt[4]]), lt[3]);
            w = (int)strlen(when);
            snprintf(when + w, sizeof when - (unsigned)w, " %02d:%02d", lt[2], lt[1]);
        }
    }
    part[0] = 0;
    if (cnt[0] > 0 && cnt[0] == cnt[1])
        snprintf(part, sizeof part, TR("%d sent to ListenBrainz and Last.fm"), cnt[0]);
    else {
        o = 0;
        if (cnt[0] > 0) o += (unsigned)snprintf(part + o, sizeof part - o, TR("%d sent to ListenBrainz"), cnt[0]);
        if (cnt[1] > 0) {
            if (o) o += (unsigned)snprintf(part + o, sizeof part - o, ", ");
            snprintf(part + o, sizeof part - o, TR("%d sent to Last.fm"), cnt[1]);
        }
    }
    o = (unsigned)strlen(out);
    o += (unsigned)snprintf(out + o, n - o, " %s: ", TR("Last upload"));
    if (when[0]) o += (unsigned)snprintf(out + o, n - o, "%s \xc2\xb7 ", when);
    if (strcmp(res, "ok")) {
        const char *w = TR("Card error");
        if (!strcmp(res, "fail"))
            w = TR("Failed");
        else if (!strcmp(res, "auth"))
            w = TR("Refused");
        o += (unsigned)snprintf(out + o, n - o, "%s%s", w, part[0] ? ", " : "");
    } else if (!part[0])
        snprintf(part, sizeof part, "%s", TR("Nothing sent"));
    if (o < n) snprintf(out + o, n - o, "%s", part);
}

/* patch/m1plus.c page_refresh: the Scrobbling page's note (pod_note1_t) from the record read last. */
void lb_note(void *win) {
    char t[256];
    void *w = widget_lookup(win, "pod_note1_t", 1);
    if (!w) return;
    lb_note_text(t, sizeof t);
    widget_set_text_utf8(w, t);
}

void lb_row_text(char *out, unsigned n) {
    char name[SU_NAME];
    name[0] = 0;
    if (!scrobup_account(name, sizeof name))
        snprintf(out, n, "%s", TR("Not Set"));
    else if (scrobup_invalid())
        snprintf(out, n, "%s", TR("Invalid Token"));
    else
        snprintf(out, n, "%s", name);
}

void lb_account_text(char *out, unsigned n) {
    char name[SU_NAME];
    name[0] = 0;
    if (!scrobup_account(name, sizeof name))
        snprintf(out, n, "%s", TR("Not Set"));
    else if (scrobup_busy() && scrobup_kind() == SCROBUP_CHECK)
        snprintf(out, n, "%s", TR("Checking…"));
    else if (scrobup_invalid())
        snprintf(out, n, "%s", TR("Invalid Token"));
    else
        snprintf(out, n, "%s", name);
}

/* The Last.fm rows: the USER value of the file, or its state. */
void lf_row_text(char *out, unsigned n) {
    char name[SU_NAME];
    int st = scrobup_lastfm(name, sizeof name);
    snprintf(out, n, "%s", st == SCROBUP_LF_NONE ? TR("Not Set") : st == SCROBUP_LF_BAD ? TR("Sign-in Failed") : name);
}

void lf_account_text(char *out, unsigned n) {
    if (scrobup_lastfm((char *)0, 0) != SCROBUP_LF_NONE && scrobup_busy() && scrobup_kind() == SCROBUP_LFCHECK)
        snprintf(out, n, "%s", TR("Checking…"));
    else
        lf_row_text(out, n);
}

/* The timer, while a page is up and there is a job to wait for or a result to show. */
static void lb_watch(void) {
    if (!lbs.timer && lbs.pages && (lbs.job || lbs.done || scrobup_busy()))
        lbs.timer = timer_add(lb_tick, (void *)0, LB_TICK_MS);
}

/* Our job's result, once: only while the job that runs is the one this file started (its owner and its kind are asked first). An automatic upload that is over is collected
 * first, silently (Invalid Token, if it found that, is on the rows at their next refresh). */
static void lb_poll(void) {
    int sent = 0, r;
    scrobble_auto_collect();
    if (!lbs.job || lbs.done) return;
    if (!scrobup_busy() || scrobup_owner() != SCROBUP_UI || scrobup_kind() != lbs.job - 1) {
        lbs.job = 0; /* its result went to another caller: nothing to read, nothing to say */
        return;
    }
    r = scrobup_poll(&sent);
    if (!r) return;
    lbs.kind = lbs.job - 1;
    lbs.job = 0;
    /* (SCROBUP_AUTH: the poll keeps Invalid Token, scrobup_invalid; the token stays in the file until another one is written there) */
    lbs.done = 1, lbs.res = r, lbs.sent = sent, lbs.rej = scrobup_rejected(), lbs.auth = scrobup_auth();
}

static void lb_check(int lf);

/* The polled result on screen: an upload's toast (a check says nothing: the rows show the name or the refusal); a refusal names its service. After the ListenBrainz
 * check a Last.fm account that waits for its own is asked next (one job at a time). */
static void lb_show(void) {
    char t[128];
    int r = lbs.res;
    if (!lbs.done) return;
    lbs.done = 0;
    if (lbs.kind == SCROBUP_UPLOAD) {
        if (r == SCROBUP_AUTH && (lbs.auth & SCROBUP_LB))
            snprintf(t, sizeof t, "ListenBrainz: %s", TR("Invalid Token"));
        else if (r == SCROBUP_AUTH)
            snprintf(t, sizeof t, "Last.fm: %s", TR("Sign-in Failed"));
        else if (r == SCROBUP_DISK)
            snprintf(t, sizeof t, TR("Card error, %d sent"), lbs.sent);
        else if (r != SCROBUP_OK)
            snprintf(t, sizeof t, TR("Upload failed, %d sent"), lbs.sent);
        else if (lbs.rej > 0)
            snprintf(t, sizeof t, TR("%d sent, %d rejected"), lbs.sent, lbs.rej);
        else if (lbs.sent > 0)
            snprintf(t, sizeof t, TR("Scrobbles sent: %d"), lbs.sent);
        else
            snprintf(t, sizeof t, "%s", TR("Nothing to upload"));
        pod_toast(t);
    } else if (lbs.kind == SCROBUP_CHECK)
        lb_check(1);
    lb_last_load();
    pod_lb_refresh();
}

static int lb_tick(const void *timer) {
    (void)timer;
    if (!lbs.pages) { /* (the destroy handler removes the timer: this only ends a stray one) */
        lbs.timer = 0;
        return RET_OK;
    }
    lb_poll();
    if (lbs.job) {
        if (++lbs.ticks % LB_AWAKE_TICKS == 0) reset_poweroptions_timer(1, 1, 0);
        return RET_REPEAT;
    }
    if (!lbs.done && scrobup_busy()) return RET_REPEAT; /* an automatic upload: watched, collected when it is over */
    if (!m1_screen_lit()) return RET_REPEAT; /* what is left is the toast and the rows: at the first lit tick */
    lbs.timer = 0;
    if (lbs.done)
        lb_show();
    else
        lb_last_load(), pod_lb_refresh();
    return RET_OK;
}

/* An account no check has confirmed is asked of the service, when the Wi-Fi is connected and no job runs: ListenBrainz a token without a name (and not refused),
 * Last.fm credentials not asked since the boot. */
static void lb_check(int lf) {
    char name[SU_NAME];
    if (get_wifisignal() > 0 && !lbs.job && !scrobup_busy()) {
        if (lf) {
            if (scrobup_lastfm((char *)0, 0) == SCROBUP_LF_NEW && scrobup_lastfm_check_start(SCROBUP_UI) == 1)
                lbs.job = 1 + SCROBUP_LFCHECK;
        } else if (scrobup_account(name, sizeof name) && !name[0] && !scrobup_invalid() &&
                   scrobup_check_start(SCROBUP_UI) == 1)
            lbs.job = 1 + SCROBUP_CHECK;
    }
    lb_watch();
}

/* Upload Scrobbles. In this order: a job that runs, USB mode, no card (the token is on the card: neither is "no token"), no token (the card's scrobble.ini is read again first, as scrobup_start does), no Wi-Fi; then the start. The
 * Scrobbling switch is not asked. */
void lb_upload_tap(void) {
    int r;
    lb_poll(); /* a job of ours that ended while no page was up: its result first (and an automatic upload that is over is out of the way) */
    if (lbs.done) {
        lb_show();
        return;
    }
    if (scrobup_busy()) {
        pod_toast(TR("Already uploading"));
        lb_watch();
        return;
    }
    scrobup_forget(); /* the file as it is now */
    if (navigator_window_is_exist(SCROBUP_USB_PAGE))
        pod_toast(TR("Not available in USB mode")); /* (the computer has the card, and the token with it) */
    else if (!m1_card_mounted())
        pod_toast(TR("Storage unavailable")); /* (no card is no account, but not one to set up) */
    else if (!scrobup_configured()) /* (either service: the upload goes to every one that is set up) */
        pod_toast(TR("Set up an account first"));
    else if (get_wifisignal() <= 0)
        pod_toast(TR("Connect to Wi-Fi first"));
    else if ((r = scrobup_start(SCROBUP_UI)) == 1) {
        lbs.job = 1 + SCROBUP_UPLOAD;
        pod_toast(TR("Uploading scrobbles"));
        lb_watch();
    } else if (r == 0)
        pod_toast(TR("Already uploading"));
    else
        pod_toast(TR("Storage unavailable")); /* (-1 with a card and a token: the kill switch, or no thread) */
    pod_lb_refresh();
}

static int lb_on_destroy(void *ctx, void *e) {
    (void)e;
    lbs.pages &= ~(int)(long)ctx;
    if (!lbs.pages) m1_timer_stop(&lbs.timer); /* a job that still runs is polled when a page opens again */
    return RET_OK;
}

/* Back in front (patch/m1plus.c on_page_fg, the one EVT_WINDOW_TO_FG handler of the scrobble pages). */
void lb_on_front(void) { lb_watch(); }

/* A page opens (0 the Scrobbling page, 1 ListenBrainz, 2 Last.fm): the card's scrobble.ini is read again (a computer may have changed it; only here and at an Upload
 * Scrobbles tap, never from the timer or when a page comes back in front), and an account no check has confirmed yet is asked of the service: the page's own first, the
 * other one when that needs no check (lb_show asks Last.fm after a ListenBrainz check). */
void lb_opened(void *win, int page) {
    char was[SU_NAME], now[SU_NAME], lwas[SU_NAME], lnow[SU_NAME];
    int had, has, bad, job, lst;
    lbs.pages |= 1 << page;
    lb_last_load();
    if (!page)
        lb_note(
            win); /* the page's first refresh came before this read, and nothing below refreshes it when the account is as it was */
    widget_on(win, EVT_DESTROY, lb_on_destroy, (void *)(long)(1 << page));
    lb_poll();
    had = scrobup_account(was, sizeof was), bad = scrobup_invalid(), job = lbs.job,
    lst = scrobup_lastfm(lwas, sizeof lwas);
    scrobup_forget();
    has = scrobup_account(now, sizeof now);
    lb_check(page == 2);
    lb_check(page != 2);
    if (has != had || strcmp(was, now) || bad != scrobup_invalid() || job != lbs.job ||
        lst != scrobup_lastfm(lnow, sizeof lnow) || strcmp(lwas, lnow))
        pod_lb_refresh(); /* (the page read its rows before this; a result polled above is shown, and the rows read again, at the first tick) */
    lb_watch();
}
