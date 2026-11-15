/* Audiobooks: the book model (patch/bkmodel.c, docs/modules/audiobooks.md): the books on the card, their parts in reading order, the progress by bytes and the
 * MP4 memory guard. No page and no state of its own: the resume ring is Podcasts' (patch/pcmodel.c).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * bk_mp4_fits borrows q2-pod's mp4_samples / mp4_index_bytes / mp4_fits (patch/chapters.c, MIT, DiamondBond): the walk of moov / trak / mdia / minf / stbl for the
 * stsz / stz2 sample counts and the 28 bytes a sample; here with the open / read / lseek calls demo already imports, a file-size and a box budget, and every
 * malformed or truncated box refused.
 * The test (test/pod/bkmodel.py) parses the #defines of this file, so a change cannot leave the mocks behind.
 */
#pragma once

#define BK_ROOT_PATH \
    "/mnt/mmc/Audiobooks" /* the folder, matched case-insensitively (bk_root gives the spelling the card has) */
#define BK_KEY_PREFIX \
    "audiobooks/" /* a book's key is pc_hash(BK_KEY_PREFIX + the book's folder or file name), case-folded by pc_hash */
#define BK_FILE \
    128 /* a file or folder name with its NUL (a longer name is skipped: it would not fit the path buffers) */
#define BK_TITLE 96 /* a title, UTF-8 bytes with the NUL (cut before a continuation byte) */
#define BK_REL 192 /* a part's path inside its book folder ("CD1/01 Intro.mp3") with the NUL; a longer one is skipped */
#define BK_MAX_BOOKS 100 /* books bk_scan_books returns */
#define BK_MAX_PARTS 300 /* parts bk_load_parts returns */
#define BK_BOOK_SIZE 368 /* sizeof(bk_book_t) */
#define BK_PART_SIZE 296 /* sizeof(bk_part_t) */
#define BK_MP4_SAMPLE_BYTES \
    28 /* what FFmpeg's mov demuxer keeps for a sample: a 24-byte AVIndexEntry and its 4-byte stsz entry */
#define BK_MP4_SPARE_KB (16 * 1024) /* kept free besides the index: the decoder's buffers, the UI, the page cache */
#define BK_MP4_BAD 0xffffffffu /* bk_mp4_index_kb: unreadable, 2 GB or more, malformed or truncated */
#define BK_MP4_MAX_READS 4000 /* header reads one file may cost: a file with more boxes than that is refused */

/* The page (patch/bkpage.c, docs/modules/audiobooks.md "The page"): content y from the list's top, in px; tools/pod_books.py is the same arithmetic and parses this block. */
#define BK_W 320 /* the page's width */
#define BK_LOAD_MS 16 /* the cover loader's tick */
#define BK_TICK_MS 1000 /* pc_note's tick */
#define BK_AWAKE_MS 1000 /* the keep-awake timer while a download runs (Podcasts: PG_AWAKE_MS) */
#define BK_TILES 44 /* the Library's cover tiles (a ring) */
#define BK_PTILES 24 /* the Book level's text tiles (a ring) */
#define BK_TITLE_MAX 100 /* wide chars of the header's title */
#define BK_HEAD_H 52 /* the Library's large heading: the Podcasts pages' PP_TITLE_H; the rows start under it */
#define BK_BOTTOM 10 /* under the last row */
#define BK_ART_Y 8 /* the Book header's cover top (PS_ART px, at PS_ART_X) */
#define BK_NAME_GAP 14 /* cover to title */
#define BK_NAME_PITCH 26 /* a title line (22 px) */
#define BK_NAME_LINES 2
#define BK_NAME_X 17
#define BK_NAME_W 286
#define BK_COLLAPSE_BACK 12 /* the navbar shows the small title this far before the header's title leaves */
#define BK_SUB_GAP 4 /* title to the grey line */
#define BK_SUB_H 20
#define BK_BTN_GAP 14 /* grey line to the buttons */
#define BK_BTN_H 40
#define BK_PLAY_W 156 /* the white capsule */
#define BK_LIST_GAP 16 /* buttons to the first part */
#define BK_PART_X 16 /* a part row's text */
#define BK_PART_W 288
#define BK_TOP \
    60 /* the Library's first block under the large title: Continue Listening, else the books (= PP_LINE_Y + PP_NOLINE_PITCH: the Shows level's top with no refresh line) */
#define BK_LV_LINE_Y \
    52 /* the LibriVox level (patch/bkfind.c; the Podcasts Discover level's look: the large title, then the grey line Public domain audiobooks at the Shows level's refresh line, PP_LINE_X / PP_LINE_Y / PP_LINE_H) */
#define BK_LV_POP_Y \
    80 /* the section header Popular (the Library's Books header: BS_SECH at PP_SHOWS_X, PP_HEAD_H high) */
#define BK_LV_POP_TOP \
    114 /* the rows of Popular (= BK_LV_POP_Y + PP_HEAD_PITCH); the search level's rows start at PQ_TOP, under the field */

typedef struct {
    char dir
        [BK_FILE]; /* the book's folder name, as the card spells it; a loose file: its file name (with the extension) */
    char title[BK_TITLE]; /* the folder name, or the loose file's name without its extension */
    char
        cover[BK_FILE]; /* cover.jpg / .jpeg / .png or folder.* in the book folder, "" = none (a loose file has none) */
    unsigned parts; /* audio files in the book (all of them, even beyond BK_MAX_PARTS) */
    unsigned kb; /* their total size in KB (rounded up per file) */
    unsigned
        hash; /* the key: pc_hash("audiobooks/<dir>"), what the Podcasts side's bk_book_of(path) returns for a path in this book */
    unsigned loose; /* 1: a single audio file directly in Audiobooks/ (dir is that file) */
} bk_book_t;

typedef struct {
    char rel[BK_REL]; /* the path below the book folder ("Part 2.mp3", "CD1/01.mp3"); a loose book: the file name */
    char title[BK_TITLE]; /* the file name without its extension */
    unsigned kb; /* size in KB, rounded up */
    unsigned hash; /* the resume ring's key: pc_hash of the full path, as Podcasts keys an episode */
} bk_part_t;

enum { BK_NOT_STARTED = 0, BK_IN_PROGRESS = 1, BK_FINISHED = 2 };

/* The folder: out (BK_FILE + 20 bytes) is "/mnt/mmc/<Audiobooks as the card spells it>"; 1 when it exists, else 0 (out then holds the default spelling). */
int bk_root(char *out);
/* The books, sorted by title (ASCII case-insensitive, a leading "The " aside, then the folder name); at most max, and in any case BK_MAX_BOOKS (the card's own order
 * decides which survive when there are more). Returns the count. */
int bk_scan_books(bk_book_t *out, int max);
/* The parts of a book in reading order (natural order of the path, bk_natcmp); at most max, and in any case BK_MAX_PARTS. Returns the count. */
int bk_load_parts(const bk_book_t *b, bk_part_t *out, int max);
/* The cover of the book an Audiobooks path is in as "file://<path>" in url (size, 80 at least): its cover.* / folder.* file, else its own art in the cover cache; NULL for none (the
 * placeholder), another path, or art not made yet. Never starts the cover worker. The Queue page's covers of a part (the Audiobooks page's rule). */
const char *bk_art_cover(const char *path, char *url, unsigned size);
/* The cover cache key of a book's own art: from the book's folder name, or the loose file's name. */
unsigned bk_art_key_of(const char *dir);
/* The full path of a part into out; 1 when it fits. */
int bk_part_path(const bk_book_t *b, const bk_part_t *p, char *out, unsigned size);
/* Natural, ASCII case-insensitive order: digit runs compare by value ("Part 2" < "Part 10"), '/' sorts before every other character (a folder's files stay together);
 * ties are broken by a plain compare, so no two different paths are equal. */
int bk_natcmp(const char *a, const char *b);
/* The book's progress from the resume ring (pc_state, pc_recent_rank). *permille: 0..1000 by bytes (a part PC_DONE counts whole, a part PC_PROGRESS pos / len of its bytes).
 * *current: the part to play: the one most recently touched in the ring, or the one after it when that is PC_DONE (the first part not PC_DONE when it was the last);
 * 0 when nothing was touched; n when every part is PC_DONE. Returns BK_NOT_STARTED, BK_IN_PROGRESS or BK_FINISHED (no parts: BK_NOT_STARTED). */
int bk_progress(const bk_part_t *parts, int n, unsigned *permille, int *current);

/* The MP4 memory guard. The index the demuxer builds for an .m4b / .m4a / .mp4 file in KB: 0 for any other extension (nothing to guard), BK_MP4_BAD when the file
 * cannot be opened or is 2 GB or more, or a box is malformed or truncated, or no sample table is found. */
unsigned bk_mp4_index_kb(const char *path);
/* MemAvailable of a /proc/meminfo text in KB; 0 when the line is missing or malformed. */
unsigned bk_parse_meminfo(const char *buf);
/* Whether the file may be opened by the player: not an MP4 extension, or an index (bk_mp4_index_kb) that fits MemAvailable less BK_MP4_SPARE_KB. Everything unknown
 * (BK_MP4_BAD, no /proc/meminfo, no MemAvailable) is refused. */
int bk_mp4_fits(const char *path);
