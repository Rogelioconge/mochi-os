#!/usr/bin/env python3
"""The player side of the parametric EQ and of Mono Audio / Crossfeed: hciplayer's equalizer filter replaced by
patch/peq_player.c (docs/modules/peq.md, docs/modules/stereo.md).

hciplayer (/usr/bin/hciplayer, the audio daemon: MPlayer 1.3.0 modified) is pinned by SHA-256. Its final program
header is an unused PT_NULL; pod.py's append_payload turns it into a file-backed PT_LOAD (RWX) at PLAYER_BASE holding the
payload (patch/peq.c, patch/stereo.c, patch/vu.c and patch/peq_player.c, built with PEQ_PLAYER, non-PIC, linked at PLAYER_BASE, no .bss: per-instance
state is heap). Four edits, each pinned with its neighbours and the facts the C code reads:

  * the equalizer's af_info open slot (EQ_OPEN_SLOT, stock af_equalizer open 0x44fd14) becomes peq_open;
  * stock skips the equalizer above 48 kHz in two places (RATE_GATES): the mcl-seteq command (beqz to the
    "===setequalizer off===" log) becomes a nop, and the playback loop's per-stream insert (bnez around the add at
    0x42fbc4) an unconditional branch, so the filter runs at every rate (it passes DSD through itself);
  * the strtol call that parses mcl-seteq's flag (SETEQ_CALL) becomes peq_seteq_flag, which answers 2 for an off flag, so
    stock keeps the filter in the chain with its Equalizer switch off (the filter then passes the native format through
    unless Mono Audio or Crossfeed is on) and, when the filter must leave native pass-through, calls stock's removal
    0x42929c so the playback loop adds a float one. The kill switch gets stock's own answer.

libc is reached only through hciplayer's own PLT GOT slots (no new import): a stub sets $gp and $t8 (the slot, which
the lazy resolver PLT0 expects) and jumps through it, as q2-pod's tools/peq.py does.

Usage: mod_player.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import json, os, pathlib, re, stat, struct, sys
from elftools.elf.elffile import ELFFile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir
import pod

REL = 'usr/bin/hciplayer'
PLAYER_SHA = 'a64503746862af3e69b57f2e06167351b30cda28479348a845be5172e083a8c6'
PLAYER_GP = 0xb16750          # DT_PLTGOT + 0x7ff0
PLAYER_BASE = 0xe10000        # stock's last LOAD ends at 0xe03b38
SOURCES = ['peq.c', 'stereo.c', 'vu.c', 'icy.c', 'peq_player.c']
FLAGS = [*pod.FLAGS, '-mnan=2008', '-fno-math-errno', '-DPEQ_PLAYER']   # hciplayer: FP64, NaN2008 (its .MIPS.abiflags, e_flags 0x400)

# The equalizer's af_info: info, name ("equalizer"), author, comment, flags, open.
EQ_INFO = 0x893808
EQ_INFO_WORDS = (0x8937bc, 0x885e2c, 0x89354c, 0x88c3b8, 1, 0x44fd14)
EQ_OPEN_SLOT, STOCK_OPEN = EQ_INFO + 0x14, 0x44fd14
# (address, stock word, patched word)
RATE_GATES = ((0x42ce34, 0x10400098, 0),             # mcl-seteq: beqz $v0, 0x42d098 ("setequalizer off") -> nop
              (0x42fa78, 0x14400052, 0x10000052))    # the insert: bnez $v0, 0x42fbc4 -> b 0x42fbc4
# The strtol call that parses mcl-seteq's flag (jal 0xadae10, the PLT stub of strtol): peq_seteq_flag takes it over.
SETEQ_CALL, SETEQ_STOCK = 0x42cd1c, 0x0c2b6b84
# Read-only ICY metadata tap (patch/icy.c, docs/modules/radio.md): MPlayer HTTP mp_msg (jal 0x445cec) and FFmpeg HTTPS av_opt_set (jal 0x6f86f0).
ICY_MP_CALL, ICY_MP_STOCK = 0x4be4d0, 0x0c11173b
ICY_FF_CALL, ICY_FF_STOCK = 0x5020cc, 0x0c1be1bc
ICY_CALLS = ((ICY_MP_CALL, ICY_MP_STOCK, 'icy_mplayer_msg'), (ICY_FF_CALL, ICY_FF_STOCK, 'icy_av_opt_set'))
# Checked, not written: (address, stock word, what it proves).
PINS = (
    (0x42cd14, 0x2406000a, 'mcl-seteq flag: a2 = 10 (base)'),
    (0x42cd18, 0x00002825, 'mcl-seteq flag: a1 = 0 (no end pointer)'),
    (0x42cd20, 0x27a40e5c, 'mcl-seteq flag: a0 = the text (delay slot of the call)'),
    (0x42cd24, 0x24030001, 'mcl-seteq flag: v1 = 1'),
    (0x42cd28, 0x1043003c, 'mcl-seteq flag: beq v0, v1 -> flag 1 (0x42ce1c)'),
    (0x42cd2c, 0x00408825, 'mcl-seteq flag: s1 = the flag'),
    (0x42cd30, 0x24020002, 'mcl-seteq flag: v0 = 2'),
    (0x42cd34, 0x12220032, 'mcl-seteq flag: beq s1, v0 -> flag 2 (0x42ce00)'),
    (0x42cd54, 0x0c10a4a7, 'mcl-seteq flag 0 (not reached once the flag answers 2): jal 0x42929c, remove "equalizer"'),
    (0x42cd64, 0xac400df0, 'mcl-seteq flag 0 (not reached): sw $zero, 0xdf0: the insert state 0'),
    (0x42ce00, 0x3c060088, 'mcl-seteq flag 2: lui $a2, 0x88 (log)'),
    (0x42ce0c, 0x24c66804, 'mcl-seteq flag 2: the log text "====pre_eqset======" (0x886804)'),
    (0x42ce10, 0x3c0200b1, 'mcl-seteq flag 2: lui $v0, 0xb1'),
    (0x42ce14, 0x1000fc3e, 'mcl-seteq flag 2: b 0x42bf10'),
    (0x42ce18, 0xac510df0, 'mcl-seteq flag 2: sw $s1, 0xdf0($v0): the insert state becomes the flag, 2'),
    (0x42ce3c, 0x24030002, 'mcl-seteq flag 1: v1 = 2'),
    (0x42ce44, 0xac430df0, 'mcl-seteq flag 1: sw $v1, 0xdf0($v0): the insert state 2'),
    (0x42929c, 0x27bdffd8, 'remove: the function stock removes "equalizer" with (a0 = mpctx + 0x40): addiu sp'),
    (0x4292b0, 0x8c920004, 'remove: lw $s2, 4($a0): the filter chain'),
    (0x4224e0, 0x8c440df0, 'file start: lw the insert state'),
    (0x4224e4, 0x14830002, 'file start: bne state, 1'),
    (0x4224ec, 0xac430df0, 'file start: state 1 becomes 2 (the filter is added again for each file)'),
    (0x42f438, 0x8e830df0, 'the loop: lw the insert state'),
    (0x42fbd4, 0xae820df0, 'the insert: state 1 after the add'),
    (0xadae10, 0x3c0f00b0, 'strtol stub: lui $t7, 0xb0'),
    (0xadae14, 0x8df998e8, 'strtol stub: lw $t9, -0x6718($t7): the GOT slot 0xaf98e8 (strtol)'),
    (0x42ce1c, 0x3c0200b0, 'mcl-seteq gate: lui $v0, 0xb0'),
    (0x42ce20, 0x3403bb81, 'mcl-seteq gate: ori $v1, $zero, 48001'),
    (0x42ce24, 0x8c429e30, 'mcl-seteq gate: lw $v0, -0x61d0($v0): mpctx at 0xaf9e30'),
    (0x42ce28, 0x8c42002c, 'mcl-seteq gate: lw $v0, 0x2c($v0): mpctx->sh_audio'),
    (0x42ce2c, 0x8c42003c, 'mcl-seteq gate: lw $v0, 0x3c($v0): the sample rate'),
    (0x42ce30, 0x0043102a, 'mcl-seteq gate: slt $v0, $v0, $v1'),
    (0x42f43c, 0x1062018a, 'the loop: beq $v1, $v0 (insert pending) to the insert gate'),
    (0x42f440, 0x3403bb81, 'the loop: ori $v1, $zero, 48001'),
    (0x42fa68, 0x8e649e30, 'insert gate: lw $a0, -0x61d0($s3): mpctx'),
    (0x42fa6c, 0x8c82002c, 'insert gate: sh_audio'),
    (0x42fa70, 0x8c42003c, 'insert gate: the sample rate'),
    (0x42fa74, 0x0043102a, 'insert gate: slt'),
    (0x42fbc4, 0x0c10a473, 'the insert: jal 0x4291cc (find or add "equalizer", then GAIN SET channels 0..7)'),
    (0x4291f8, 0x26715e2c, 'add: the name "equalizer" (0x885e2c)'),
    (0x429228, 0x3c1300b1, 'add: lui $s3, 0xb1'),
    (0x42922c, 0x3c124000, 'add: lui $s2, 0x4000'),
    (0x429234, 0x26730df4, 'add: the gains at 0xb10df4'),
    (0x429238, 0x26521d00, 'add: AF_CONTROL_EQUALIZER_GAIN | SET (0x40001d00)'),
    (0x42923c, 0x8e190004, 'add: lw $t9, 4($s0): af->control'),
    (0x429250, 0x0320f809, 'add: jalr $t9'),
    (0x42ca74, 0x24570df4, 'mcl-seteq: the ten gains parsed into 0xb10df4'),
    (0x42ca7c, 0xe4400df4, 'mcl-seteq: swc1 (float gains)'),
    (0x42f78c, 0x8e629e30, 'the audio EOF test: lw $v0, -0x61d0($s3): mpctx'),
    (0x42f790, 0x8c420034, 'the audio EOF test: mpctx->d_audio (+0x34)'),
    (0x42f794, 0x8c42001c, 'the audio EOF test: d_audio->eof (+0x1c), what the carried filter memory reads'),
    (0x47ed5c, 0x8e020004, 'sh_audio->codec (+4)'),
    (0x47ed74, 0x8c4703d0, 'codec->name (+0x3d0)'),
    (0x47ed7c, 0x8c4203e0, 'codec->drv (+0x3e0)'),
    (0x44fd38, 0xac820004, 'stock open: af->control at +4'),
    (0x44fd48, 0xac820008, 'stock open: af->uninit at +8'),
    (0x44fd54, 0xf4800028, 'stock open: af->mul (double) at +0x28'),
    (0x44fd60, 0xae02000c, 'stock open: af->play at +0xc'),
    (0x44fd6c, 0xae020014, 'stock open: af->data at +0x14'),
    (0x44fd7c, 0xae020010, 'stock open: af->setup at +0x10'),
    (0x44fe38, 0x3c021000, 'stock control: lui 0x1000'),
    (0x44fe3c, 0x24420100, 'stock control: AF_CONTROL_REINIT 0x10000100'),
    (0x44fe48, 0x3c022000, 'stock control: lui 0x2000'),
    (0x44fe4c, 0x24420300, 'stock control: AF_CONTROL_COMMAND_LINE 0x20000300'),
    (0x42686c, 0x8e060008, 'playing_audio_pts caller: lw $a2, 8($s0): mpctx->audio_out (the level tap reads the output delay from it)'),
    (0x426878, 0x8e050034, 'playing_audio_pts caller: lw $a1, 0x34($s0): mpctx->d_audio'),
    (0x42687c, 0x0c10c03d, 'playing_audio_pts caller: jal 0x4300f4'),
    (0x43010c, 0x00c08825, 'playing_audio_pts: move $s1, $a2 (the audio_out)'),
    (0x430148, 0x8e39001c, 'playing_audio_pts: lw $t9, 0x1c($s1): audio_out->get_delay'),
    (0x430170, 0x0320f809, 'playing_audio_pts: jalr $t9 (no argument; the float seconds come back in $f0)'),
    (0x43018c, 0x46010002, 'playing_audio_pts: mul.s $f0, $f0, $f1 (speed): the delay is a single float'),
    (0x44fddc, 0x3c024000, 'stock control: lui 0x4000'),
    (0x44fdec, 0x24431d00, 'stock control: AF_CONTROL_EQUALIZER_GAIN 0x40001d00'),
    (0x4bdf70, 0x24427264, 'MPlayer ICY: addiu $v0, $v0, 0x7264 ("\\nICY Info: %s\\n" at 0x8a7264)'),
    (0x4be4c0, 0x8fa6002c, 'MPlayer ICY: lw $a2, 0x2c($sp) (format string)'),
    (0x4be4c4, 0x24050004, 'MPlayer ICY: a1 = MSGL_INFO (4)'),
    (0x4be4c8, 0x24040005, 'MPlayer ICY: a0 = MSGT_NETWORK (5)'),
    (0x4be4cc, 0x03c03825, 'MPlayer ICY: a3 = $fp (ICY info string)'),
    (0x4be4d4, 0xa0400000, 'MPlayer ICY: delay slot sb $zero, ($v0) (NUL-terminates $fp)'),
    (0x445cec, 0x27bdffd8, 'mp_msg prologue: addiu $sp, $sp, -0x28'),
    (0x445cfc, 0xafa70034, 'mp_msg prologue: sw $a3, 0x34($sp)'),
    (0x5020b4, 0x3c05008b, 'FFmpeg ICY: lui $a1, 0x8b'),
    (0x5020bc, 0x00003825, 'FFmpeg ICY: a3 = 0 (flags)'),
    (0x5020c0, 0x24a52b50, 'FFmpeg ICY: a1 = "icy_metadata_packet" (0x8b2b50)'),
    (0x5020c4, 0x00403025, 'FFmpeg ICY: a2 = $v0 (packet buffer)'),
    (0x5020c8, 0xa2800001, 'FFmpeg ICY: sb $zero, 1($s4) (NUL-terminates packet buffer)'),
    (0x5020d0, 0x02602025, 'FFmpeg ICY: delay slot a0 = $s3 (HTTPContext)'),
    (0x6f86f0, 0x27bdffb0, 'av_opt_set prologue: addiu $sp, $sp, -0x50'),
    (0x6f870c, 0x00c09025, 'av_opt_set prologue: move $s2, $a2'),
)
NAME_AT, NAME = 0x885e2c, b'equalizer\0'
DSD_DRV = (0x89b4f0, b'dsdiff\0')   # the vendor's DSD driver name, as the filter compares it
ICY_STRS = ((0x8a7264, b'\nICY Info: %s\n\0'), (0x8b2b50, b'icy_metadata_packet\0'))
# libc: name -> (C prototype, the PLT symbol hciplayer imports it as)
LIBC = {
    'memset': ('void *', 'void *, int, unsigned', 'memset'), 'memcpy': ('void *', 'void *, const void *, unsigned', 'memcpy'),
    'memcmp': ('int', 'const void *, const void *, unsigned', 'memcmp'), 'strcmp': ('int', 'const char *, const char *', 'strcmp'),
    'strlen': ('unsigned', 'const char *', 'strlen'), 'calloc': ('void *', 'unsigned, unsigned', 'calloc'),
    'free': ('void', 'void *', 'free'), 'fopen': ('void *', 'const char *, const char *', 'fopen64'),
    'fread': ('unsigned', 'void *, unsigned, unsigned, void *', 'fread'), 'fclose': ('int', 'void *', 'fclose'),
    'fseek': ('int', 'void *, long, int', 'fseek'), 'fwrite': ('unsigned', 'const void *, unsigned, unsigned, void *', 'fwrite'),
    'clock_gettime': ('int', 'int, void *', 'clock_gettime'), 'strtol': ('long', 'const char *, char **, int', 'strtol'),
    'pow': ('double', 'double, double', '__pow_finite'), 'cos': ('double', 'double', 'cos'), 'sin': ('double', 'double', 'sin'),
}


def plt_slots(path):
    """name -> the .got.plt slot of each LIBC import (the MIPS PLT: .rel.plt's R_MIPS_JUMP_SLOT entries)."""
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        rel, syms = elf.get_section_by_name('.rel.plt'), elf.get_section_by_name('.dynsym')
        found = {syms.get_symbol(r['r_info_sym']).name: r['r_offset'] for r in rel.iter_relocations()}
    want = {imp for _, _, imp in LIBC.values()}
    missing = sorted(want - set(found))
    pod.check(not missing, f'hciplayer does not import {missing}')
    return {name: found[imp] for name, (_, _, imp) in LIBC.items()}


def word(b, a): return struct.unpack_from('<I', b, pod.fileoff(b, a))[0]


def check_stock(raw):
    pod.check(pod.sha(raw) == PLAYER_SHA, f'{REL} is not the pinned stock binary')
    got = tuple(word(raw, EQ_INFO + 4 * i) for i in range(6))
    pod.check(got == EQ_INFO_WORDS, f'equalizer af_info at {EQ_INFO:#x}: {[hex(w) for w in got]}')
    pod.check(word(raw, SETEQ_CALL) == SETEQ_STOCK, f'{SETEQ_CALL:#x}: mcl-seteq strtol call {word(raw, SETEQ_CALL):#010x}')
    for a, old, name in ICY_CALLS:
        pod.check(word(raw, a) == old, f'{a:#x} ({name}): {word(raw, a):#010x} != {old:#010x}')
    for a, old, _ in RATE_GATES:
        pod.check(word(raw, a) == old, f'{a:#x}: rate gate {word(raw, a):#010x} != {old:#010x}')
    for a, old, what in PINS:
        pod.check(word(raw, a) == old, f'{a:#x} ({what}): {word(raw, a):#010x} != pinned {old:#010x}')
    for a, s in ((NAME_AT, NAME), DSD_DRV, *ICY_STRS):
        off = pod.fileoff(raw, a)
        pod.check(raw[off:off + len(s)] == s, f'{a:#x}: not {s!r}')


def compile_payload(build, slots):
    header = ['/* generated by tools/mod_player.py: hciplayer libc through its own PLT slots */', '#pragma once']
    asm = ['.set noreorder', '.text']
    for name, (ret, args, _) in LIBC.items():
        header += [f'extern {ret} peq_lib_{name}({args});', f'#define {name} peq_lib_{name}']
        slot = slots[name]
        asm += [f'.section .text.peq_lib_{name},"ax",@progbits', f'.globl peq_lib_{name}', f'peq_lib_{name}:',
                f'lui $gp, {PLAYER_GP >> 16}', f'ori $gp, $gp, {PLAYER_GP & 0xffff}',
                f'lui $t8, {slot >> 16}', f'ori $t8, $t8, {slot & 0xffff}', 'lw $t9, 0($t8)', 'jr $t9', 'nop']
    asm += ['.globl memcpy', '.set memcpy, peq_lib_memcpy', '.globl memset', '.set memset, peq_lib_memset']   # the compiler's own struct copies
    (build / 'player.h').write_text('\n'.join(header) + '\n')
    (build / 'player_asm.S').write_text('\n'.join(asm) + '\n')
    objs = []
    for src in SOURCES:
        obj = build / (src + '.o')
        pod.run(pod.CLANG, *FLAGS, '-I', build, '-I', pod.PATCH, '-c', os.path.join(pod.PATCH, src), '-o', obj)
        objs.append(obj)
    pod.run(pod.CLANG, *FLAGS, '-c', build / 'player_asm.S', '-o', build / 'player_asm.o')
    script = build / 'player.ld'
    script.write_text(f'SECTIONS {{ . = {PLAYER_BASE:#x}; .text : {{ *(.text*) }} .rodata : {{ *(.rodata*) }} '
                      '.data : { *(.data*) *(.sdata*) } .bss : { *(.bss*) *(.sbss*) *(COMMON) } '
                      '/DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) *(.gnu.attributes) } }\n')
    pod.run(pod.LD, '-m', 'elf32ltsmip', '--gc-sections', '-T', script, '-e', 'peq_open', '-u', 'peq_seteq_flag',
            '-u', 'icy_mplayer_msg', '-u', 'icy_av_opt_set', *objs, build / 'player_asm.o', '-o', build / 'player.elf')
    pod.run(pod.OBJCOPY, '-O', 'binary', build / 'player.elf', build / 'player.bin')
    with open(build / 'player.elf', 'rb') as f:
        elf = ELFFile(f)
        for sec in elf.iter_sections():
            if sec.name in ('.bss', '.sbss') and sec['sh_size']:
                raise ValueError(f'player payload has non-empty {sec.name}: its state is per instance, on the heap')
        syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    return syms, (build / 'player.bin').read_bytes()


def patch(raw, payload, syms):
    image = bytearray(raw)
    entry = syms['peq_open']
    pod.check(PLAYER_BASE <= entry < PLAYER_BASE + len(payload), 'peq_open outside the payload')
    struct.pack_into('<I', image, pod.fileoff(image, EQ_OPEN_SLOT), entry)
    for a, _, new in RATE_GATES: struct.pack_into('<I', image, pod.fileoff(image, a), new)
    flag = syms['peq_seteq_flag']
    pod.check(PLAYER_BASE <= flag < PLAYER_BASE + len(payload), 'peq_seteq_flag outside the payload')
    struct.pack_into('<I', image, pod.fileoff(image, SETEQ_CALL), 0x0c000000 | flag >> 2)
    for a, _, name in ICY_CALLS:
        target = syms[name]
        pod.check(PLAYER_BASE <= target < PLAYER_BASE + len(payload), f'{name} outside the payload')
        struct.pack_into('<I', image, pod.fileoff(image, a), 0x0c000000 | target >> 2)
    seg_off = pod.append_payload(image, payload, PLAYER_BASE)
    return bytes(image), seg_off


def apply(out):
    path = os.path.join(out, 'rootfs', REL)
    raw = open(path, 'rb').read()
    check_stock(raw)
    build = pathlib.Path(out) / 'playerbuild'; build.mkdir(exist_ok=True)
    slots = plt_slots(path)
    pod.check(slots['strtol'] == 0xaf98e8, f'strtol slot {slots["strtol"]:#x}: not what the stub at 0xadae10 jumps through')
    syms, payload = compile_payload(build, slots)
    patched, seg_off = patch(raw, payload, syms)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(patched); os.chmod(path, mode)
    manifest = {'stock_sha256': PLAYER_SHA, 'patched_sha256': pod.sha(patched), 'base': PLAYER_BASE, 'gp': PLAYER_GP,
                'payload_len': len(payload), 'payload_sha256': pod.sha(payload), 'segment_file_off': seg_off,
                'open_slot': {'addr': EQ_OPEN_SLOT, 'stock': STOCK_OPEN, 'target': syms['peq_open']},
                'rate_gates': [[a, old, new] for a, old, new in RATE_GATES], 'libc_slots': slots,
                'seteq_call': {'addr': SETEQ_CALL, 'stock': SETEQ_STOCK, 'target': syms['peq_seteq_flag']},
                'icy_calls': [{'addr': a, 'stock': old, 'target': syms[name], 'name': name} for a, old, name in ICY_CALLS],
                'symbols': {n: syms[n] for n in sorted(syms) if re.fullmatch(r'(?:peq|icy)_\w+', n)}}
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'player: payload {len(payload)} bytes @ {PLAYER_BASE:#x}, equalizer open {EQ_OPEN_SLOT:#x} -> '
          f'{syms["peq_open"]:#x}, rate gates {", ".join(hex(a) for a, _, _ in RATE_GATES)}, '
          f'mcl-seteq flag {SETEQ_CALL:#x} -> {syms["peq_seteq_flag"]:#x}, '
          f'icy {", ".join(f"{a:#x}->{syms[n]:#x}" for a, _, n in ICY_CALLS)}')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
