#!/usr/bin/env python3
"""The Home pins file (patch/pins.c, docs/modules/pins.md): the model the tests compare the payload with.

/mnt/mmc/.m1plus/home-pins (on the card):

    M1P1\\n
    <kind: a album | p playlist | s song | r artist>\\t<key: 8 hex>\\t<cover key 0..3: 8 hex each>\\t<name>\\t<path>\\n        (one line per pin, in the user's order)

An album's key is its identity as Recently Played has it (identity(): FNV-1a of its title, ASCII letters folded to lower case; the stock album list groups albums by title alone),
its first cover key is the Cover Flow cache key of the album row (cc_album_key; never 0, the other three are 0) and its path is a track of the album (the way to find the stock row
again; may be empty). A playlist's key is its stock id (REC_DISC, from 0), the cover keys are the keys of up to four distinct albums of its songs (the mosaic of the Playlists page),
nonzero ones first, and its path is empty. A song's key is the FNV-1a of its file path (song_id(): case as written, never 0), its first cover key the key of its album's cover (the
library album of its album tag: cc_album_rep_key, else the record's own key; never 0, the other three 0), its name the title tag (the file's name without one) and its path the file's path (never
empty; a track of a CUE image, which shares its file with the others, has "<CUE start>@" before the path, the start 1 to 9 digits without a leading zero: song_path()). An artist's key is the FNV-1a of its name as the Artists page lists it, ASCII letters folded (identity(), as an album's title), its one cover key the artist photo's cache key (artist_key(): FNV-1a of the name trimmed, ASCII
case folded, without a leading "The "; never 0, the other three 0), its name the artist and its path the artist list it was pinned from: "0" Artists, "1" Album Artists (an old line has it empty; the payload then looks in the list shown, then the other). The name is never empty (an album's title, a playlist's name). Read strictly: the first line exactly the magic, at most MAX lines of
exactly eight fields, a known kind, a non-zero key (a playlist's id may be 0; no (kind, key) twice), eight hex digits per cover key, no control byte (below 0x20, or 0x7f) in a field, every line ended by a
newline, names under STR bytes and paths under PATH, the whole file at most FILE_MAX bytes. Anything else is an empty list.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_mix
MAGIC = b'M1P1\n'
MAX = 6            # patch/offsets.inc PIN_MAX
STR = 96           # PIN_STR: bytes of a name with its NUL
PATH = 256         # PIN_PATH
FILE_MAX = 3072    # PIN_FILE_MAX
ALBUM, PLAYLIST, SONG, ARTIST = b'a', b'p', b's', b'r'
identity = pod_mix.fold_hash   # pn_album_id: the album title folded to lower case ASCII, FNV-1a, never 0


def song_id(path, start=0):
    """pn_song_id: FNV-1a of the path's bytes (path: str or bytes), then (h ^ start) * 16777619 for a CUE track (start > 0), never 0."""
    h = pod_mix.fnv1a(path if isinstance(path, bytes) else path.encode('utf-8'))
    if start: h = ((h ^ start) * 16777619) & 0xffffffff
    return h or 1


def song_path(path, start=0):
    """A song's path field: the path, with "<start>@" before it for a CUE track (start 1 .. 999999999)."""
    return f'{start}@{path}' if start else path


def split_song_path(field):
    """(path, start) of a song's path field (str), or None when it is neither "/path" nor "<digits, no leading zero>@/path"."""
    if field.startswith('/'): return field, 0
    head, at, rest = field.partition('@')
    if at and head.isascii() and head.isdigit() and 1 <= len(head) <= 9 and head[0] != '0' and rest.startswith('/'): return rest, int(head)
    return None


def artist_key(name):
    """patch/artistphoto.c ap_key, written again (an artist's cover key): FNV-1a of the name trimmed of spaces and tabs, ASCII case folded, without a leading "The " (and the space after it); never 0 (0 only for a blank name). The hash is cc_fnv, which also hashes the NUL that ends the name."""
    s = ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in name.strip(' \t'))
    if len(s) > 4 and s.startswith('the '): s = s[4:].lstrip(' \t')
    h = pod_mix.fnv1a(s.encode('utf-8')) * 16777619 & 0xffffffff   # cc_fnv: the NUL after the name is hashed too
    return (h or 1) if s else 0


def _clean(b):
    return not any(c < 0x20 or c == 0x7f for c in b)


def _hex8(b):
    return len(b) == 8 and all(c in b'0123456789abcdef' for c in b)


def parse(data):
    """The entries [(kind, key, (c0, c1, c2, c3), name, path)] (kind 'a' / 'p' / 's' / 'r', the strings keep the file's bytes decoded as latin-1), or [] when anything is malformed."""
    if not isinstance(data, bytes) or len(data) > FILE_MAX or not data.startswith(MAGIC):
        return []
    body = data[len(MAGIC):]
    if body and not body.endswith(b'\n'):
        return []
    out, seen = [], set()
    for line in body.split(b'\n')[:-1] if body else []:
        f = line.split(b'\t')
        if len(f) != 8 or len(out) >= MAX: return []
        kind, key, c0, c1, c2, c3, name, path = f
        if kind not in (ALBUM, PLAYLIST, SONG, ARTIST) or not all(_hex8(x) for x in (key, c0, c1, c2, c3)): return []
        k, cs = int(key, 16), tuple(int(x, 16) for x in (c0, c1, c2, c3))
        if (not k and kind != PLAYLIST) or (kind, k) in seen: return []   # a stock playlist id starts at 0
        if kind != PLAYLIST and (not cs[0] or any(cs[1:])): return []   # an album's and a song's one cover key
        if kind == SONG and split_song_path(path.decode('latin-1')) is None: return []
        if kind == ARTIST and path not in (b'', b'0', b'1'): return []
        if kind == PLAYLIST:
            if path: return []
            n = sum(1 for c in cs if c)
            if not all(cs[:n]) or any(cs[n:]) or len(set(cs[:n])) != n: return []   # non-zero keys first, then zeros, no key twice
        if not name or len(name) >= STR or len(path) >= PATH: return []
        if not _clean(name) or not _clean(path): return []
        seen.add((kind, k))
        out.append((kind.decode(), k, cs, name.decode('latin-1'), path.decode('latin-1')))
    return out


def dump(entries):
    """The file for entries [(kind, key, cover keys, name, path)] (latin-1 strings as parse gives them)."""
    return MAGIC + b''.join(b'%s\t%08x\t%08x\t%08x\t%08x\t%08x\t%s\t%s\n' % (kind.encode(), k, c[0], c[1], c[2], c[3], n.encode('latin-1'), p.encode('latin-1'))
                            for kind, k, c, n, p in entries)


def field(s, size):
    """What the payload stores of a name or path (pn_copy): control bytes as spaces, cut below `size` bytes without splitting a UTF-8 sequence. s is UTF-8 bytes; the result is bytes."""
    n = len(s)
    if n >= size:
        n = size - 1
        while n and (s[n] & 0xc0) == 0x80: n -= 1
    return bytes(32 if (c < 0x20 or c == 0x7f) else c for c in s[:n])


def keys4(keys):
    """A playlist's cover keys as the file holds them: the distinct non-zero ones in order, at most four, zero-padded."""
    out = []
    for k in keys:
        if k and k not in out: out.append(k)
    return tuple((out + [0] * 4)[:4])


def has(entries, kind, key):
    return any(e[0] == kind and e[1] == key for e in entries)


def pin(entries, entry):
    """(entries, status) after pinning: 'ok' appends the entry (the others keep their places); a pin already there stays where it is ('ok'); a full list without it is 'full' and unchanged."""
    if has(entries, entry[0], entry[1]): return list(entries), 'ok'
    if len(entries) >= MAX: return list(entries), 'full'
    return list(entries) + [entry], 'ok'


def move(entries, i, j):
    """The list with the pin at index i moved to index j (the others close up; i == j or out of range: unchanged)."""
    n = len(entries)
    if not (0 <= i < n and 0 <= j < n) or i == j: return list(entries)
    out = list(entries); e = out.pop(i); out.insert(j, e)
    return out


def unpin(entries, kind, key):
    """The list without that pin (unchanged when it is not there)."""
    return [e for e in entries if not (e[0] == kind and e[1] == key)]
