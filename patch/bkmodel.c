/* M1+ Music Audiobooks, the model: the books on the card, their parts in reading order, the progress by bytes, the MP4 memory guard.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The MP4 walk (bk_mp4_*) follows q2-pod's patch/chapters.c (mp4_samples, mp4_index_bytes, mp4_fits; MIT, DiamondBond): moov / trak / mdia / minf / stbl down to the
 * stsz / stz2 sample counts, 28 bytes a sample, MemAvailable less 16 MiB. Ours reads with open / read / lseek and refuses what q2-pod's breaks out of.
 * Nothing here runs by itself and nothing is hooked: the Audiobooks page (a later increment) calls it. docs/modules/audiobooks.md has the rules and the numbers.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "common.h"
#include "podcasts.h"
#include "books.h"

_Static_assert(sizeof(bk_book_t) == BK_BOOK_SIZE, "bk_book_t");
_Static_assert(sizeof(bk_part_t) == BK_PART_SIZE, "bk_part_t");

#define BM_DNAME 11 /* struct dirent (32-bit, MIPS o32): d_name at 11 */
#define BM_PATH 400
#define BM_ROOT "/mnt/mmc"

/* ---------------------------------------------------------------------------
 * Small helpers (the payload links no libc string functions of its own)
 */
static unsigned bm_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

static int bm_lc(int c) { return (unsigned)(c - 'A') < 26u ? c + 32 : c; }

static int bm_dig(int c) { return (unsigned)(c - '0') < 10u; }

/* s is exactly the lower-case word w, ASCII case aside. */
static int bm_ieq(const char *s, const char *w) {
    while (*s && *w && bm_lc((unsigned char)*s) == *w) ++s, ++w;
    return !*s && !*w;
}

/* out (size) ends with s appended; 0 when it does not fit. */
static int bm_cat(char *out, unsigned size, const char *s) {
    unsigned n = bm_len(out), m = bm_len(s);
    if (n + m + 1 > size) return 0;
    memcpy(out + n, s, m + 1);
    return 1;
}

/* A title from s (n bytes, or to its NUL when n < 0) into out of size bytes, cut before a UTF-8 continuation byte. */
static void bm_title(char *out, unsigned size, const char *s, int n) {
    unsigned len = 0;
    while ((n < 0 || len < (unsigned)n) && s[len]) ++len;
    if (len >= size) {
        len = size - 1;
        while (len && ((unsigned char)s[len] & 0xc0) == 0x80) --len;
    }
    memcpy(out, s, len);
    out[len] = 0;
}

/* root/a[/b] into out; 0 when it does not fit. */
static int bm_join(char *out, unsigned size, const char *root, const char *a, const char *b) {
    out[0] = 0;
    return bm_cat(out, size, root) && bm_cat(out, size, "/") && bm_cat(out, size, a) &&
           (!b || (bm_cat(out, size, "/") && bm_cat(out, size, b)));
}

/* Whether the extension of name is one the player takes for audio (the list Podcasts accepts). */
static int bm_audio(const char *name) {
    static const char *const ext[] = {"mp3", "m4a", "m4b", "aac", "ogg", "opus", "flac", "wav", "wma"};
    unsigned n = bm_len(name), i;
    const char *dot = name + n;
    while (dot > name && dot[-1] != '.') --dot;
    if (dot == name || dot == name + 1) return 0;
    for (i = 0; i < sizeof ext / sizeof *ext; ++i)
        if (bm_ieq(dot, ext[i])) return 1;
    return 0;
}

/* A name worth looking at: not empty, not a dot file or folder (macOS ._ files, .DS_Store), short enough, no control byte. */
static int bm_name_ok(const char *name) {
    unsigned i;
    if (!name[0] || name[0] == '.' || bm_len(name) >= BK_FILE) return 0;
    for (i = 0; name[i]; ++i)
        if ((unsigned char)name[i] < 32) return 0;
    return 1;
}

static const char *bm_basename(const char *rel) {
    const char *p = rel + bm_len(rel);
    while (p > rel && p[-1] != '/') --p;
    return p;
}

/* A title from a file name: the name without its extension. */
static void bm_title_of(char *out, unsigned size, const char *name) {
    int n = (int)bm_len(name);
    while (n > 0 && name[n - 1] != '.') --n;
    bm_title(out, size, name, n > 1 ? n - 1 : -1);
}

/* A directory: opendir works. */
static int bm_is_dir(const char *path) {
    void *d = opendir(path);
    if (d) closedir(d);
    return d != (void *)0;
}

/* The folder holds a LibriVox manifest (patch/bkdl.c): a dot file the walk never lists. */
static int bm_manifest(const char *dir) {
    char path[BM_PATH];
    return bm_join(path, sizeof path, dir, ".librivox", (const char *)0) && access(path, 4) == 0;
}

/* A file's size in KB, rounded up (st_size at +0x30 of the 144-byte struct stat); 0 when it cannot be seen (*kb is then 0). */
static int bm_stat_kb(const char *path, unsigned *kb) {
    unsigned st[40];
    memset(st, 0, sizeof st);
    *kb = 0;
    if (__xstat(3, path, st) != 0) return 0;
    *kb = (st[0x30 / 4] >> 10) + ((st[0x30 / 4] & 1023) != 0);
    return 1;
}

int bk_root(char *out) {
    void *d;
    char *ent;
    int found = 0;
    memcpy(out, BM_ROOT "/Audiobooks", sizeof(BM_ROOT "/Audiobooks"));
    if (bm_is_dir(out)) return 1;
    d = opendir(BM_ROOT);
    if (!d) return 0;
    while (!found && (ent = readdir(d)) != (char *)0) {
        const char *n = ent + BM_DNAME;
        char path[BK_FILE + 20];
        if (!bm_ieq(n, "audiobooks")) continue;
        memcpy(path, BM_ROOT "/", sizeof(BM_ROOT "/"));
        if (bm_cat(path, sizeof path, n) && bm_is_dir(path)) memcpy(out, path, bm_len(path) + 1), found = 1;
    }
    closedir(d);
    return found;
}

/* ---------------------------------------------------------------------------
 * Natural order
 */
static int bm_key(int c) { return c == '/' ? 1 : bm_lc(c); }

int bk_natcmp(const char *a, const char *b) {
    const char *a0 = a, *b0 = b;
    for (;;) {
        int ca = (unsigned char)*a, cb = (unsigned char)*b;
        if (bm_dig(ca) &&
            bm_dig(
                cb)) { /* digit runs by value: leading zeros dropped, then the longer is the larger, then the digits */
            const char *ea, *eb;
            unsigned la, lb, i;
            while (*a == '0') ++a;
            while (*b == '0') ++b;
            for (ea = a; bm_dig((unsigned char)*ea);) ++ea;
            for (eb = b; bm_dig((unsigned char)*eb);) ++eb;
            la = (unsigned)(ea - a), lb = (unsigned)(eb - b);
            if (la != lb) return la < lb ? -1 : 1;
            for (i = 0; i < la; ++i)
                if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
            a = ea, b = eb;
            continue;
        }
        ca = bm_key(ca), cb = bm_key(cb);
        if (ca != cb) return ca < cb ? -1 : 1;
        if (!ca) break;
        ++a, ++b;
    }
    for (a = a0, b = b0; *a && *a == *b;)
        ++a, ++b; /* equal by the rules above: a plain compare keeps the order total */
    return (unsigned char)*a == (unsigned char)*b ? 0 : (unsigned char)*a < (unsigned char)*b ? -1 : 1;
}

/* ---------------------------------------------------------------------------
 * The files of a book
 */
typedef void (*bm_visit_t)(void *ctx, const char *rel, const char *full, unsigned kb);

/* The audio files directly in the folder root/dir and in its immediate subfolders (CD1, Disc 2), dot entries left out: one call each, rel is the path below the folder. Returns the count. */
static unsigned bm_walk(const char *root, const char *dir, bm_visit_t visit, void *ctx) {
    char path[BM_PATH], sub[BM_PATH], full[BM_PATH], rel[BK_REL];
    void *d, *sd;
    char *ent, *e2;
    unsigned count = 0, kb;
    if (!bm_join(path, sizeof path, root, dir, (const char *)0) || !(d = opendir(path))) return 0;
    while ((ent = readdir(d)) != (char *)0) {
        char name[BK_FILE]; /* (a copy: the nested readdir may reuse the entry) */
        if (!bm_name_ok(ent + BM_DNAME)) continue;
        memcpy(name, ent + BM_DNAME, bm_len(ent + BM_DNAME) + 1);
        if (bm_audio(name)) {
            if (bm_join(full, sizeof full, path, name, (const char *)0) && bm_stat_kb(full, &kb)) {
                rel[0] = 0;
                if (bm_cat(rel, sizeof rel, name)) visit(ctx, rel, full, kb), ++count;
            }
            continue;
        }
        if (!bm_join(sub, sizeof sub, path, name, (const char *)0) || !(sd = opendir(sub))) continue;
        while ((e2 = readdir(sd)) != (char *)0) {
            const char *n2 = e2 + BM_DNAME;
            if (!bm_name_ok(n2) || !bm_audio(n2)) continue;
            rel[0] = 0;
            if (!bm_cat(rel, sizeof rel, name) || !bm_cat(rel, sizeof rel, "/") || !bm_cat(rel, sizeof rel, n2))
                continue;
            if (!bm_join(full, sizeof full, sub, n2, (const char *)0) || !bm_stat_kb(full, &kb)) continue;
            visit(ctx, rel, full, kb), ++count;
        }
        closedir(sd);
    }
    closedir(d);
    return count;
}

/* The key of a book: pc_hash("audiobooks/<dir>"). */
static unsigned bm_book_hash(const char *dir) {
    char key[sizeof BK_KEY_PREFIX + BK_FILE];
    memcpy(key, BK_KEY_PREFIX, sizeof BK_KEY_PREFIX);
    bm_cat(key, sizeof key, dir);
    return pc_hash(key);
}

static int bm_cover_rank(const char *name) {
    static const char *const names[] = {"cover.jpg",  "cover.png",  "cover.jpeg",
                                        "folder.jpg", "folder.png", "folder.jpeg"};
    unsigned i;
    for (i = 0; i < sizeof names / sizeof *names; ++i)
        if (bm_ieq(name, names[i])) return (int)i;
    return -1;
}

static void bm_find_cover(const char *root, const char *dir, char *out) {
    char path[BM_PATH];
    void *d;
    char *ent;
    int best = 99;
    out[0] = 0;
    if (!bm_join(path, sizeof path, root, dir, (const char *)0) || !(d = opendir(path))) return;
    while ((ent = readdir(d)) != (char *)0) {
        const char *name = ent + BM_DNAME;
        int r;
        if (!bm_name_ok(name)) continue;
        r = bm_cover_rank(name);
        if (r >= 0 && r < best) best = r, bm_title(out, BK_FILE, name, -1);
    }
    closedir(d);
}

/* The cache key of a book's own art (bk_art_cover): the control byte keeps it apart from an album of an artist called audiobooks. */
unsigned bk_art_key_of(const char *dir) { return cc_key_of("\x01" BK_KEY_PREFIX, dir); }

/* The cover of the book a part's path (an Audiobooks path) is in, as "file://<path>" in url (size, 80 at least): the book folder's cover.* / folder.* when the stock decoder takes it
 * (pc_cover_ok), else the book's own art file from the cover cache when it is there. Never starts the worker (the Audiobooks page does). NULL: another path, no cover, no art yet.
 * A file straight in Audiobooks is a book of its own: no folder, only the cache file. One readdir of the folder. */
const char *bk_art_cover(const char *path, char *url, unsigned size) {
    static const char prefix[] = BM_ROOT "/audiobooks/";
    char root[BK_FILE + 20], name[BK_FILE], file[BK_FILE], full[BM_PATH];
    unsigned n = 0;
    const char *p;
    if (!bk_is_path(path) || size < 80) return (const char *)0;
    p = path + sizeof prefix - 1;
    while (p[n] && p[n] != '/') ++n;
    if (n >= BK_FILE) return (const char *)0;
    memcpy(name, p, n), name[n] = 0;
    if (p[n] == '/' && bk_root(root)) { /* (a folder: its picture file first) */
        bm_find_cover(root, name, file);
        if (file[0] && bm_join(full, sizeof full, root, name, file) && pc_cover_ok(full) && bm_len(full) + 8 <= size) {
            memcpy(url, "file://", 7);
            memcpy(url + 7, full, bm_len(full) + 1);
            return url;
        }
    }
    return cc_url(url, bk_art_key_of(name));
}

typedef struct {
    unsigned parts, kb;
} bm_sum_t;

static void bm_sum_visit(void *ctx, const char *rel, const char *full, unsigned kb) {
    bm_sum_t *s = ctx;
    ++s->parts;
    if (s->kb + kb < s->kb)
        s->kb = 0xffffffffu; /* (4 TB) */
    else
        s->kb += kb;
}

static int bm_book_cmp(const bk_book_t *x, const bk_book_t *y) {
    int d = cc_name_cmp(x->title, y->title);
    if (!d) d = cc_nocase(x->dir, y->dir);
    return d ? d : bk_natcmp(x->dir, y->dir);
}

int bk_scan_books(bk_book_t *out, int max) {
    char root[BK_FILE + 20], path[BM_PATH];
    void *d;
    char *ent;
    int count = 0, i, k;
    bk_book_t tmp;
    if (max > BK_MAX_BOOKS) max = BK_MAX_BOOKS;
    if (!bk_root(root) || !(d = opendir(root))) return 0;
    while (count < max && (ent = readdir(d)) != (char *)0) {
        char name[BK_FILE]; /* (a copy: the walk below reads other directories) */
        bk_book_t *b = &out[count];
        bm_sum_t s;
        if (!bm_name_ok(ent + BM_DNAME)) continue;
        memcpy(name, ent + BM_DNAME, bm_len(ent + BM_DNAME) + 1);
        if (!bm_join(path, sizeof path, root, name, (const char *)0)) continue;
        memset(b, 0, sizeof *b);
        bm_title(b->dir, BK_FILE, name, -1);
        if (bm_audio(name)) { /* a loose file: a one-part book (a folder called x.mp3 is not looked into) */
            unsigned kb;
            if (!bm_stat_kb(path, &kb)) continue;
            b->loose = 1, b->parts = 1, b->kb = kb;
            bm_title_of(b->title, BK_TITLE, name);
        } else {
            s.parts = s.kb = 0;
            if (!bm_is_dir(path)) continue;
            bm_walk(root, name, bm_sum_visit, &s);
            if (!s.parts && !bm_manifest(path))
                continue; /* (a LibriVox book whose first part is still on its way is a book of no parts) */
            b->parts = s.parts, b->kb = s.kb;
            bm_title(b->title, BK_TITLE, name, -1);
            bm_find_cover(root, name, b->cover);
        }
        b->hash = bm_book_hash(b->dir);
        ++count;
    }
    closedir(d);
    for (i = 1; i < count; ++i) { /* insertion sort: at most BK_MAX_BOOKS, no scratch memory */
        memcpy(&tmp, &out[i], sizeof tmp);
        for (k = i; k > 0 && bm_book_cmp(&tmp, &out[k - 1]) < 0; --k) memcpy(&out[k], &out[k - 1], sizeof tmp);
        memcpy(&out[k], &tmp, sizeof tmp);
    }
    return count;
}

/* ---------------------------------------------------------------------------
 * The parts
 */
typedef struct {
    bk_part_t *out;
    int n, max;
} bm_load_t;

static void bm_load_visit(void *ctx, const char *rel, const char *full, unsigned kb) {
    bm_load_t *l = ctx;
    bk_part_t *p;
    if (l->n >= l->max) return;
    p = &l->out[l->n++];
    memset(p, 0, sizeof *p);
    bm_title(p->rel, BK_REL, rel, -1);
    bm_title_of(p->title, BK_TITLE, bm_basename(rel));
    p->kb = kb, p->hash = pc_hash(full);
}

int bk_part_path(const bk_book_t *b, const bk_part_t *p, char *out, unsigned size) {
    char root[BK_FILE + 20];
    bk_root(root);
    return bm_join(out, size, root, b->dir, b->loose ? (const char *)0 : p->rel);
}

int bk_load_parts(const bk_book_t *b, bk_part_t *out, int max) {
    char root[BK_FILE + 20];
    bm_load_t l;
    int i, k;
    bk_part_t tmp;
    if (max > BK_MAX_PARTS) max = BK_MAX_PARTS;
    l.out = out, l.n = 0, l.max = max;
    if (max <= 0 || !bk_root(root)) return 0;
    if (b->loose) {
        char full[BM_PATH];
        unsigned kb;
        if (bm_join(full, sizeof full, root, b->dir, (const char *)0) && bm_stat_kb(full, &kb))
            bm_load_visit(&l, b->dir, full, kb);
        return l.n;
    }
    bm_walk(root, b->dir, bm_load_visit, &l);
    for (i = 1; i < l.n; ++i) {
        memcpy(&tmp, &out[i], sizeof tmp);
        for (k = i; k > 0 && bk_natcmp(tmp.rel, out[k - 1].rel) < 0; --k) memcpy(&out[k], &out[k - 1], sizeof tmp);
        memcpy(&out[k], &tmp, sizeof tmp);
    }
    return l.n;
}

/* ---------------------------------------------------------------------------
 * Progress by bytes
 */
int bk_progress(const bk_part_t *parts, int n, unsigned *permille, int *current) {
    unsigned total = 0, done = 0, shift = 0, w, pos, len, pm,
             frac[BK_MAX_PARTS]; /* frac: a part in progress, in permille of itself */
    int i, recent = -1, rank, best = 0x7fffffff, touched = 0, all_done = n > 0, state[BK_MAX_PARTS];
    *permille = 0, *current = 0;
    if (n <= 0) return BK_NOT_STARTED;
    if (n > BK_MAX_PARTS) n = BK_MAX_PARTS;
    for (i = 0; i < n; ++i) {
        unsigned kb = parts[i].kb;
        total += kb + (kb == 0); /* (a part with no size still counts as one unit) */
        state[i] = pc_state(parts[i].hash, &pos, &len);
        frac[i] = 0;
        if (state[i] != PC_DONE) all_done = 0;
        if (state[i] == PC_NEW) continue;
        touched = 1;
        if (state[i] == PC_PROGRESS &&
            len) { /* (pos and len are seconds: 4 million is 46 days, so *1000 stays in 32 bits) */
            if (len > 4000000u) len = 4000000u;
            if (pos > len) pos = len;
            frac[i] = pos * 1000u / len;
        }
        rank = pc_recent_rank(parts[i].hash);
        if (rank >= 0 && rank < best) best = rank, recent = i;
    }
    while ((total >> shift) > 4000000u) ++shift; /* the sums and *1000 stay in 32 bits */
    for (i = 0; i < n; ++i) {
        w = (parts[i].kb + (parts[i].kb == 0)) >> shift;
        done += state[i] == PC_DONE ? w : w * frac[i] / 1000u;
    }
    total >>= shift;
    pm = total ? done * 1000u / total : 0;
    if (all_done) pm = 1000;
    *permille = pm > 1000 ? 1000 : pm;
    if (all_done) {
        *current = n;
        return BK_FINISHED;
    }
    if (!touched) return BK_NOT_STARTED;
    i = recent < 0 ? 0 : recent;
    if (recent >= 0 && state[recent] == PC_DONE) ++i;
    while (i < n && state[i] == PC_DONE) ++i;
    if (i >= n) { /* the last part was the one finished: what is left of the book is before it */
        for (i = 0; i < n && state[i] == PC_DONE; ++i) {
        }
    }
    *current = i;
    return BK_IN_PROGRESS;
}

/* ---------------------------------------------------------------------------
 * The MP4 memory guard
 */
static unsigned long long bm_be(const unsigned char *p, int n) {
    unsigned long long v = 0;
    while (n--) v = v << 8 | *p++;
    return v;
}

static int bm_tag(const unsigned char *p, const char *tag) {
    return p[0] == (unsigned char)tag[0] && p[1] == (unsigned char)tag[1] && p[2] == (unsigned char)tag[2] &&
           p[3] == (unsigned char)tag[3];
}

static int bm_is_mp4(const char *path) {
    const char *dot = path + bm_len(path);
    while (dot > path && dot[-1] != '.' && dot[-1] != '/') --dot;
    return dot > path && dot[-1] == '.' && (bm_ieq(dot, "m4b") || bm_ieq(dot, "m4a") || bm_ieq(dot, "mp4"));
}

static int bm_pread(int fd, unsigned long long at, void *buf, unsigned n) {
    unsigned got = 0;
    int r;
    if (at > 0x7fffffffull || lseek(fd, (long)at, 0) != (long)at) return 0;
    while (got < n && (r = read(fd, (char *)buf + got, n - got)) > 0) got += (unsigned)r;
    return got == n;
}

typedef struct {
    int fd;
    int reads; /* headers still allowed */
    int stsz; /* sample tables found */
    int bad;
    unsigned long long samples;
} bm_mp4_t;

/* The stsz / stz2 sample counts under [at, end): moov, trak, mdia, minf and stbl are walked. Anything that does not fit its parent is bad. */
static void bm_mp4_walk(bm_mp4_t *m, unsigned long long at, unsigned long long end, int depth) {
    while (!m->bad && end - at >= 8) {
        unsigned char h[16];
        unsigned long long size, head = 8;
        if (m->reads-- <= 0 || !bm_pread(m->fd, at, h, 8)) {
            m->bad = 1;
            return;
        }
        size = bm_be(h, 4);
        if (size == 1) {
            if (end - at < 16 || !bm_pread(m->fd, at + 8, h + 8, 8)) {
                m->bad = 1;
                return;
            }
            size = bm_be(h + 8, 8), head = 16;
        } else if (!size)
            size = end - at; /* to the end of the file */
        if (size < head || size > end - at) { /* truncated or malformed */
            m->bad = 1;
            return;
        }
        if (depth < 5 && (bm_tag(h + 4, "moov") || bm_tag(h + 4, "trak") || bm_tag(h + 4, "mdia") ||
                          bm_tag(h + 4, "minf") || bm_tag(h + 4, "stbl")))
            bm_mp4_walk(m, at + head, at + size, depth + 1);
        else if (bm_tag(h + 4, "stsz") || bm_tag(h + 4, "stz2")) {
            if (size < head + 12 ||
                !bm_pread(m->fd, at + head, h, 12)) { /* version / flags, sample size (stz2: field size), count */
                m->bad = 1;
                return;
            }
            m->samples += bm_be(h + 8, 4), ++m->stsz;
        }
        at += size;
    }
}

unsigned bk_mp4_index_kb(const char *path) {
    bm_mp4_t m;
    long size;
    unsigned long long kb;
    if (!bm_is_mp4(path)) return 0;
    m.fd = open(path, O_RDONLY, 0); /* (no O_LARGEFILE: a file of 2 GB or more fails with EOVERFLOW) */
    if (m.fd < 0) return BK_MP4_BAD;
    size = lseek(m.fd, 0, 2);
    m.reads = BK_MP4_MAX_READS, m.stsz = m.bad = 0, m.samples = 0;
    if (size > 0 && size < 0x7fffffffl)
        bm_mp4_walk(&m, 0, (unsigned long long)size, 0);
    else
        m.bad = 1;
    close(m.fd);
    if (m.bad || !m.stsz) return BK_MP4_BAD;
    kb = (m.samples * BK_MP4_SAMPLE_BYTES + 1023) >> 10;
    return kb >= BK_MP4_BAD ? BK_MP4_BAD : (unsigned)kb;
}

unsigned bk_parse_meminfo(const char *buf) {
    static const char key[] = "MemAvailable:";
    const char *p;
    unsigned v = 0, i;
    for (p = buf; *p; ++p) {
        for (i = 0; i < sizeof key - 1 && p[i] == key[i]; ++i) {
        }
        if (i == sizeof key - 1) break;
    }
    if (!*p) return 0;
    p += sizeof key - 1;
    while (*p == ' ' || *p == '\t') ++p;
    for (i = 0; bm_dig((unsigned char)p[i]); ++i) {
        if (v > 429496728u) return 0; /* (4 TB) */
        v = v * 10 + (unsigned)(p[i] - '0');
    }
    return i ? v : 0;
}

int bk_mp4_fits(const char *path) {
    char buf[1024];
    unsigned kb, avail;
    int fd, got = 0, r;
    if (!bm_is_mp4(path)) return 1;
    kb = bk_mp4_index_kb(path);
    if (kb == BK_MP4_BAD) return 0;
    fd = open("/proc/meminfo", O_RDONLY, 0);
    if (fd < 0) return 0;
    while (got < (int)sizeof buf - 1 && (r = read(fd, buf + got, sizeof buf - 1 - (unsigned)got)) > 0) got += r;
    close(fd);
    buf[got] = 0;
    avail = bk_parse_meminfo(buf);
    return avail && (unsigned long long)kb + BK_MP4_SPARE_KB <= avail;
}
