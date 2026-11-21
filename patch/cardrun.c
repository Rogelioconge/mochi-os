/* M1+ Music Settings > Developer > Tools > Card Script (docs/modules/cardrun.md "Developer page"): start the card script runner by hand, stop it, read its log.
 *
 * The runner is /usr/bin/m1plus-run (tools/mod_cardrun.py): it runs /mnt/mmc/m1plus-run.sh once and keeps three files in /tmp:
 * m1plus-run.pid (the pid of the shell that runs the script, while it runs), m1plus-run.exit (its exit status once it ended) and m1plus-run.log (the output). Running is a pid file naming a live process.
 *
 * Run Now forks twice. The UI process holds open files (the track playing from the card, sockets, input devices), which a child of system() would inherit and so keep the card busy: the child closes every
 * descriptor, reopens 0 to 2 on /dev/null and execs the runner. Its grandchild is the one that calls setsid() and execs, so the runner's pid is also its process group: Stop signals the group (kill(-pid)), then the
 * pid. The first child ends at once and is reaped here; the grandchild is adopted by init.
 *
 * External audio hold (docs/modules/cardrun.md "External audio hold"): a card script that plays straight to the DAC with aplay creates /tmp/m1plus-extaudio; a 500 ms UI timer started by Run Now takes
 * the DAC for it, as q2-pod's librespot hand-over does (spot_take, spot_poll, spot_yield; https://github.com/ubcprogrammers/q2-pod, MIT; README.md acknowledges it).
 *
 * The log page is a Release Notes page (patch/relnotes.c cardlog_open) showing the last CR_LOG_MAX bytes of the log, cut at a line boundary, when it opens.
 */
#include "offsets.inc"
#include "stock.h"
#include "i18n.h"
#include "home.h"
#include "common.h"
#include "entries.h"
#include "radio.h"

#define CR_SCRIPT "/mnt/mmc/m1plus-run.sh"
#define CR_RUNNER "/usr/bin/m1plus-run"
#define CR_PID "/tmp/m1plus-run.pid"
#define CR_EXIT "/tmp/m1plus-run.exit"
#define CR_LOG "/tmp/m1plus-run.log"
#define CR_FDS 1024 /* descriptors the child closes */
#define CR_AT_FDCWD (-100)
#define CR_STATX_MTIME 0x40u
#define CR_SIGKILL 9
#define CR_SIGTERM 15
#define CR_WANT "/tmp/m1plus-extaudio" /* the script wants the DAC (it creates and removes it) */
#define CR_READY "/tmp/m1plus-extaudio.ready" /* the payload readied the DAC for this hold */
#define CR_YIELD "/tmp/m1plus-extaudio.yield" /* local music or a station is about to start: the script lets go */
#define CR_YIELD_STEPS 100 /* checks of 20 ms for the script to drop CR_WANT */
#define CR_POLL_MS 500
#define CR_LINES 300 /* lines of the log kept: the page holds 700 wrapped ones */

/* A small file as text: the byte count (the NUL is added), -1 when it cannot be read. */
static int cr_read(const char *path, char *buf, int n) {
    int fd = open(path, O_RDONLY, 0), got;
    if (fd < 0) return -1;
    got = read(fd, buf, (unsigned)(n - 1));
    close(fd);
    if (got < 0) return -1;
    buf[got] = 0;
    return got;
}

static int cr_atoi(const char *s) {
    int v = 0;
    while (*s == ' ') ++s;
    while (*s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    return v;
}

/* The pid of the run in progress, 0 when none (no pid file, or one that names a process that is gone). */
int cardrun_pid(void) {
    char b[16];
    int pid;
    if (cr_read(CR_PID, b, sizeof b) <= 0) return 0;
    pid = cr_atoi(b);
    return pid > 1 && kill(pid, 0) == 0 ? pid : 0;
}

/* Seconds since the pid file was written (the run's start), 0 when unknown. */
static int cr_elapsed(void) {
    unsigned sx[64]; /* struct statx: stx_mask first, stx_mtime.tv_sec at byte 112 */
    long d;
    if (ft_statx(CR_AT_FDCWD, CR_PID, 0, CR_STATX_MTIME, sx) != 0 || !(sx[0] & CR_STATX_MTIME)) return 0;
    d = time((long *)0) - (long)sx[28];
    return d > 0 ? (int)d : 0;
}

/* The Status row's value: No Script, Ready, Running m:ss, Done (exit 0), Stopped (SIGTERM or SIGKILL), Failed (N). */
void cardrun_status_text(char *buf, unsigned n) {
    char b[16];
    int code = cr_read(CR_EXIT, b, sizeof b) > 0 ? cr_atoi(b) : -1, t;
    if (cardrun_pid()) {
        t = cr_elapsed();
        snprintf(buf, n, "%s %d:%02d", TR("Running"), t / 60, t % 60);
    } else if (access(CR_SCRIPT, 0) != 0)
        snprintf(buf, n, "%s", TR("No Script"));
    else if (code < 0)
        snprintf(buf, n, "%s", TR("Ready"));
    else if (code == 0)
        snprintf(buf, n, "%s", TR("Done"));
    else if (code == 128 + CR_SIGTERM || code == 128 + CR_SIGKILL)
        snprintf(buf, n, "%s", TR("Stopped"));
    else
        snprintf(buf, n, "%s (%d)", TR("Failed"), code);
}

/* The detached runner: 0 forked and reaped, -1 when the fork failed. The children never return here. */
static int cr_spawn(void) {
    int a = fork(), st = 0, fd;
    if (a < 0) return -1;
    if (a > 0) {
        waitpid(a, &st, 0);
        return 0;
    }
    if (fork() != 0) { /* the first child ends at once, so that the runner is no child of the UI */
        kill(getpid(), CR_SIGKILL);
        return -1;
    }
    setsid();
    for (fd = 0; fd < CR_FDS; ++fd) close(fd);
    open("/dev/null", O_RDWR, 0);
    open("/dev/null", O_RDWR, 0);
    open("/dev/null", O_RDWR, 0);
    execl(CR_RUNNER, "m1plus-run", (char *)0);
    kill(getpid(), CR_SIGKILL);
    return -1;
}

static unsigned cr_timer __attribute__((section(".scratch")));
static int cr_hold __attribute__((section(".scratch")));

static void cr_touch(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) close(fd);
}

/* A hold in progress: the want file exists. Any thread. */
static int cr_wanted(void) { return access(CR_WANT, 0) == 0; }

/* Local music or a station is about to start (mclStartPlayer's hook, rd_begin): with a hold on, ask the script to let go and wait up to CR_YIELD_STEPS x 20 ms for its want file to go. */
void cr_ext_yield(void) {
    int i;
    if (!cr_wanted()) return;
    cr_touch(CR_YIELD);
    for (i = 0; i < CR_YIELD_STEPS && cr_wanted(); ++i) usleep(20000);
}

/* One tick: a new want file takes the DAC (stop the station, stop local music, ready the output, then the ready file); while held the player stays awake; no want file ends the hold and leaves the DAC. */
static void cr_poll(void) {
    int want = cr_wanted();
    if (want && !cr_hold) {
        if (rd_running()) rd_stop();
        if (mclGetPlayStatus() != 1) stop_player();
        rd_dac_take();
        cr_touch(CR_READY);
        cr_hold = 1;
    } else if (want) {
        reset_poweroptions_timer(1, 1, 0);
        if (*(int *)DACOFF_TIME > 0) *(int *)DACOFF_TIME = 0;
    } else if (cr_hold) {
        unlink(CR_READY);
        unlink(CR_YIELD);
        cr_hold = 0;
    }
}

static int cr_live __attribute__((section(".scratch"))); /* the last tick saw a run */

/* Repeats while the run is alive or the want file exists, then ends itself. While a run is alive, and once more when it ends, the Card Script page (if open) reads its status and rows again. */
static int cr_tick(const void *unused) {
    int run = cardrun_pid() != 0;
    (void)unused;
    cr_poll();
    if (run || cr_live) cardrun_refresh();
    cr_live = run;
    if (run || cr_wanted() || cr_hold) return RET_REPEAT;
    cr_timer = 0;
    return RET_OK;
}

/* The tick runs while a run is alive: started by Run Now, and by the page when it shows during a run. */
void cardrun_watch(void) {
    if (!cr_timer && cardrun_pid()) cr_timer = timer_add(cr_tick, (void *)0, CR_POLL_MS);
}

/* Run Now (the row says Stop during a run; the runner itself refuses a second run): a toast with no script. */
void cardrun_run(void) {
    if (access(CR_SCRIPT, 0) != 0) {
        pod_toast(TR("No m1plus-run.sh on the card"));
        return;
    }
    if (cr_spawn() != 0) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    cr_live = 1; /* a run too short for a tick to see still gets its end shown */
    if (!cr_timer) cr_timer = timer_add(cr_tick, (void *)0, CR_POLL_MS);
}

/* Stop: the run's process group, then its pid, with SIGTERM; the tick shows the end. */
void cardrun_stop(void) {
    int pid = cardrun_pid();
    if (!pid) return;
    kill(-pid, CR_SIGTERM);
    kill(pid, CR_SIGTERM);
}

/* A file as the text pages show it: tail 1 the end of the file (the log), 0 the start (the script); at most n - 1 bytes after the cleanup, plain ASCII (a tab is four spaces, another control byte a space, a byte over 0x7e
 * a "?"), at most CR_LINES lines (the last ones for the tail, the first for the head). A cut falls on a line boundary when the text has one: the tail starts at a line start, the head ends at a line end.
 * Its length; 0 when the file is missing or empty. */
static int cr_text(const char *path, char *buf, int n, int tail) {
    int fd = open(path, O_RDONLY, 0), got = 0, cut, i, len = 0, from = 0, lines = 0;
    char *raw, *ex;
    if (fd < 0) return 0;
    raw = calloc((unsigned)n, 1);
    ex = calloc(4u * (unsigned)n, 1);
    if (raw && ex) {
        int size = (int)lseek(fd, 0, 2);
        cut = size > n - 1; /* the file is longer than the window */
        if (size > 0 && lseek(fd, tail && cut ? size - (n - 1) : 0, 0) >= 0) got = read(fd, raw, (unsigned)(n - 1));
        for (i = 0; i < got; ++i) {
            unsigned char c = (unsigned char)raw[i];
            if (c == '\t')
                ex[len++] = ' ', ex[len++] = ' ', ex[len++] = ' ', ex[len++] = ' ';
            else
                ex[len++] = c == '\n' ? '\n' : c < ' ' ? ' ' : c > '~' ? '?' : (char)c;
        }
        while (len > 0 && ex[len - 1] == '\n') --len;
        cut |= len > n - 1; /* the tabs made it longer than the room */
        if (tail) {
            if (len > n - 1) from = len - (n - 1);
            if (cut) { /* the window starts inside a line: drop it, unless there is no line start */
                for (i = from; i < len && !(i ? ex[i - 1] == '\n' : !cut); ++i) {
                }
                if (i < len) from = i;
            }
            for (i = len - 1; i >= from; --i) /* the last CR_LINES lines */
                if (ex[i] == '\n' && ++lines == CR_LINES) {
                    from = i + 1;
                    break;
                }
        } else {
            if (len > n - 1) len = n - 1;
            if (cut) { /* the window ends inside a line: drop it, unless there is no line end */
                for (i = len; i > 0 && ex[i] != '\n'; --i) {
                }
                if (i > 0) len = i;
            }
            for (i = 0; i < len; ++i)
                if (ex[i] == '\n' && ++lines == CR_LINES) {
                    len = i;
                    break;
                }
        }
        for (i = from, got = 0; i < len; ++i) buf[got++] = ex[i];
        buf[got] = 0;
    } else
        got = 0;
    free(raw);
    free(ex);
    close(fd);
    return got;
}

/* The log page's text: the end of /tmp/m1plus-run.log. */
int cardrun_log(char *buf, int n) { return cr_text(CR_LOG, buf, n, 1); }

/* The script page's text: the start of the card's /mnt/mmc/m1plus-run.sh (not the copy in /tmp). */
int cardrun_src(char *buf, int n) { return cr_text(CR_SCRIPT, buf, n, 0); }
