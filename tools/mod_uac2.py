#!/usr/bin/env python3
"""USB DAC XRUN recovery in soc_aic.ko (docs/modules/uac2.md).

Stock's built-in f_uac2 driver opens /dev/snd/pcmC0D0p from a kernel worker
(PF_KTHREAD) with HW_PARAMS only (no SW_PARAMS, leaving ALSA's default
start_threshold = 1 frame) and writes 64,000 B on stream start, then 48,000 B
chunks into a 128 KiB DMA ring (16,384 frames S32_LE stereo, 32,768 frames
S16_LE stereo). After a single XRUN (clock drift or a transient CPU stall),
f_uac2 calls SNDRV_PCM_IOCTL_PREPARE and writes one 48,000 B chunk; with
start_threshold = 1 DMA starts at once with zero cushion, so every later chunk
that arrives slightly late hits -EPIPE and is dropped whole (125 ms at 48 kHz)
until the host restarts the stream.

This step replaces soc_aic.ko's empty aic_dma_pcm_prepare (currently `return 0`)
with a 30-instruction leaf function appended to .text. Only during XRUN recovery
(runtime->status->state == SNDRV_PCM_STATE_XRUN) of a kernel-thread playback
stream that left start_threshold == 1 (f_uac2 alone; userspace players have
PF_KTHREAD == 0 and set their own SW_PARAMS), it raises runtime->start_threshold
to 3/8 of runtime->buffer_size (49,152 B = 6,144 frames PCM / 12,288 frames
DSD). Normal startup and sample-rate switches (state == SETUP) keep stock's
start_threshold == 1 with zero extra latency; XRUN recovery buffers two 48,000 B
chunks (96,000 B <= 131,072 B) before restarting DMA, restoring a 48,000 B
(125 ms at 48 kHz) cushion.

The kernel image (xImage) stays untouched stock. A kernel module edit, not a
demo hook: the kill switch does not restore it.

Usage: mod_uac2.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, sha256, write_keep_mode

REL = 'module_driver/soc_aic.ko'
STOCK_SHA = 'd4d9011f214b982cdc8db2fd672e27a72885d7a5b5343f35f354f20b901488de'
STOCK_SIZE = 26448

# Pinned stock ELF layout of module_driver/soc_aic.ko (ET_REL, EM_MIPS, LE)
E_SHOFF = 0x6278
E_SHNUM = 31
E_SHENTSIZE = 40
TEXT_SHNDX = 3
TEXT_OFF = 0x0070
TEXT_SIZE = 0x22c0
TEXT_ALIGN = 16
SYMTAB_OFF = 0x36f0
PREPARE_SYM_IDX = 120
PREPARE_STOCK_VAL = 0x1ab8
PREPARE_STOCK_SIZE = 8
PREPARE_STOCK_BYTES = struct.pack('<2I', 0x03e00008, 0x00001025)   # jr $ra; move $v0, $zero
REL_DATA_OFF = 0x5ef8
REL_DATA_PREPARE_R_OFF = 0x310
DATA_OFF = 0x2cb0

# Linux 5.10.21+ MIPS32r2 kernel struct offsets (verified in stock vmlinux)
SUBSTREAM_STREAM = 0x30     # 0 = SNDRV_PCM_STREAM_PLAYBACK
SUBSTREAM_RUNTIME = 0x70    # struct snd_pcm_runtime *
RUNTIME_BUFFER_SIZE = 0x5c  # snd_pcm_uframes_t
RUNTIME_START_THR = 0x88    # snd_pcm_uframes_t
RUNTIME_STATUS = 0xb4       # struct snd_pcm_mmap_status * (state at +0x00)
PCM_STATE_XRUN = 4          # SNDRV_PCM_STATE_XRUN (pre_prepare leaves state intact until post_prepare)
TASK_FLAGS = 0x0c           # PF_KTHREAD = bit 21 (0x00200000)
PF_KTHREAD_BIT = 21

NEW_TEXT_OFF = 0x6280       # 16-byte aligned right after .shstrtab (0x6158..0x6277)
NEW_PREPARE_VAL = TEXT_SIZE # appended right after original .text (0x22c0)


def _i(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xffff)


def _r(rs, rt, rd, sh, fn):
    return (rs << 21) | (rt << 16) | (rd << 11) | (sh << 6) | fn


def _ext(rs, rt, pos, size):
    return (0x1f << 26) | (rs << 21) | (rt << 16) | ((size - 1) << 11) | (pos << 6) | 0x00


# MIPS32r2 GPR numbers (caller-saved only: $v0, $v1, $a1, $t0, $t1; read-only $gp, $ra)
_ZERO, _V0, _V1, _A1, _T0, _T1, _GP, _RA = 0, 2, 3, 5, 8, 9, 28, 31


def build_prepare_code():
    """Position-independent leaf aic_dma_pcm_prepare(component=$a0, substream=$a1).

    Sets runtime->start_threshold = (buffer_size >> 2) + (buffer_size >> 3) (3/8 of buffer_size)
    iff substream != NULL, playback stream (0), runtime != NULL, start_threshold == 1,
    runtime->status != NULL with state == SNDRV_PCM_STATE_XRUN (4), current != NULL with
    PF_KTHREAD set, and computed threshold >= 2. Always returns 0.
    """
    words = [
        _i(0x04, _A1, _ZERO, 27),                        # 0x00: beqz  $a1, .Lret (0x70)
        _r(_ZERO, _ZERO, _V0, 0, 0x25),                  # 0x04: move  $v0, $zero
        _i(0x23, _A1, _T0, SUBSTREAM_STREAM),            # 0x08: lw    $t0, 0x30($a1)
        _i(0x05, _T0, _ZERO, 24),                        # 0x0c: bnez  $t0, .Lret (0x70)
        _i(0x23, _A1, _T1, SUBSTREAM_RUNTIME),           # 0x10: lw    $t1, 0x70($a1)
        _i(0x04, _T1, _ZERO, 22),                        # 0x14: beqz  $t1, .Lret (0x70)
        _i(0x09, _ZERO, _V1, 1),                         # 0x18: addiu $v1, $zero, 1
        _i(0x23, _T1, _T0, RUNTIME_START_THR),           # 0x1c: lw    $t0, 0x88($t1)
        _i(0x05, _T0, _V1, 19),                          # 0x20: bne   $t0, $v1, .Lret (0x70)
        _i(0x23, _T1, _T0, RUNTIME_STATUS),              # 0x24: lw    $t0, 0xb4($t1)   (runtime->status)
        _i(0x04, _T0, _ZERO, 17),                        # 0x28: beqz  $t0, .Lret (0x70)
        _i(0x09, _ZERO, _V1, PCM_STATE_XRUN),            # 0x2c: addiu $v1, $zero, 4    (XRUN)
        _i(0x23, _T0, _T0, 0),                           # 0x30: lw    $t0, 0x00($t0)   (status->state)
        _i(0x05, _T0, _V1, 14),                          # 0x34: bne   $t0, $v1, .Lret (0x70)
        _i(0x23, _GP, _T0, 0),                           # 0x38: lw    $t0, 0($gp)      (current)
        _i(0x04, _T0, _ZERO, 12),                        # 0x3c: beqz  $t0, .Lret (0x70)
        0x00000000,                                      # 0x40: nop
        _i(0x23, _T0, _T0, TASK_FLAGS),                  # 0x44: lw    $t0, 0x0c($t0)   (current->flags)
        _ext(_T0, _T0, PF_KTHREAD_BIT, 1),               # 0x48: ext   $t0, $t0, 21, 1  (PF_KTHREAD)
        _i(0x04, _T0, _ZERO, 8),                         # 0x4c: beqz  $t0, .Lret (0x70)
        _i(0x23, _T1, _T0, RUNTIME_BUFFER_SIZE),         # 0x50: lw    $t0, 0x5c($t1)   (buffer_size)
        _r(0, _T0, _V1, 2, 0x02),                        # 0x54: srl   $v1, $t0, 2      (buf >> 2)
        _r(0, _T0, _T0, 3, 0x02),                        # 0x58: srl   $t0, $t0, 3      (buf >> 3)
        _r(_V1, _T0, _T0, 0, 0x21),                      # 0x5c: addu  $t0, $v1, $t0    (3/8 * buf)
        _i(0x0b, _T0, _V1, 2),                           # 0x60: sltiu $v1, $t0, 2
        _i(0x05, _V1, _ZERO, 2),                         # 0x64: bnez  $v1, .Lret (0x70)
        0x00000000,                                      # 0x68: nop
        _i(0x2b, _T1, _T0, RUNTIME_START_THR),           # 0x6c: sw    $t0, 0x88($t1)
        _r(_RA, 0, 0, 0, 0x08),                          # 0x70: jr    $ra              (.Lret)
        0x00000000,                                      # 0x74: nop
    ]
    return struct.pack(f'<{len(words)}I', *words)


PREPARE_CODE = build_prepare_code()
PREPARE_PADDED = PREPARE_CODE + b'\x00' * ((TEXT_ALIGN - len(PREPARE_CODE) % TEXT_ALIGN) % TEXT_ALIGN)
NEW_TEXT_SIZE = TEXT_SIZE + len(PREPARE_PADDED)


def _check_pins(data):
    if sha256(data) != STOCK_SHA or len(data) != STOCK_SIZE:
        raise ValueError(f'{REL}: not the pinned stock module')
    if data[:4] != b'\x7fELF':
        raise ValueError(f'{REL}: not an ELF')
    e_type, e_machine, _, _, _, e_shoff, _, _, _, _, e_shentsize, e_shnum = struct.unpack_from('<HHIIIIIHHHHH', data, 16)
    if (e_type, e_machine, e_shoff, e_shentsize, e_shnum) != (1, 8, E_SHOFF, E_SHENTSIZE, E_SHNUM):
        raise ValueError(f'{REL}: unexpected ELF header')
    sh_off = E_SHOFF + TEXT_SHNDX * E_SHENTSIZE
    _, sh_type, sh_flags, _, sec_off, sec_size, _, _, sh_align, _ = struct.unpack_from('<10I', data, sh_off)
    if (sh_type, sh_flags, sec_off, sec_size, sh_align) != (1, 6, TEXT_OFF, TEXT_SIZE, TEXT_ALIGN):
        raise ValueError(f'{REL}: unexpected .text section header')
    if data[TEXT_OFF + PREPARE_STOCK_VAL:TEXT_OFF + PREPARE_STOCK_VAL + PREPARE_STOCK_SIZE] != PREPARE_STOCK_BYTES:
        raise ValueError(f'{REL}: aic_dma_pcm_prepare bytes mismatch')
    sym_off = SYMTAB_OFF + PREPARE_SYM_IDX * 16
    _, st_value, st_size, st_info, _, st_shndx = struct.unpack_from('<IIIBBH', data, sym_off)
    if (st_value, st_size, st_info, st_shndx) != (PREPARE_STOCK_VAL, PREPARE_STOCK_SIZE, 0x12, TEXT_SHNDX):
        raise ValueError(f'{REL}: aic_dma_pcm_prepare symbol mismatch')
    # Verify .rel.data has R_MIPS_32 (2) against sym 120 at .data+0x310 with addend 0
    found_rel = False
    rel_end = REL_DATA_OFF + 0x170
    for o in range(REL_DATA_OFF, rel_end, 8):
        r_off, r_info = struct.unpack_from('<II', data, o)
        if r_off == REL_DATA_PREPARE_R_OFF and r_info == ((PREPARE_SYM_IDX << 8) | 2):
            found_rel = True
            break
    if not found_rel or struct.unpack_from('<I', data, DATA_OFF + REL_DATA_PREPARE_R_OFF)[0] != 0:
        raise ValueError(f'{REL}: aic_component.prepare relocation mismatch')


def patch(data):
    """The stock soc_aic.ko bytes -> ours; ValueError on anything but the pinned stock file."""
    _check_pins(data)
    orig_text = data[TEXT_OFF:TEXT_OFF + TEXT_SIZE]
    shdrs = bytearray(data[E_SHOFF:E_SHOFF + E_SHNUM * E_SHENTSIZE])

    # Keep everything before e_shoff (all non-.text sections stay at their exact offsets),
    # zero the old .text range so squashfs compresses it away, pad to NEW_TEXT_OFF,
    # append extended .text, then the updated section header table.
    body = bytearray(data[:E_SHOFF])
    body[TEXT_OFF:TEXT_OFF + TEXT_SIZE] = b'\x00' * TEXT_SIZE

    # Update sym[120] (aic_dma_pcm_prepare) st_value and st_size in .symtab
    sym_off = SYMTAB_OFF + PREPARE_SYM_IDX * 16
    struct.pack_into('<II', body, sym_off + 4, NEW_PREPARE_VAL, len(PREPARE_CODE))

    # Pad body to 16-byte aligned NEW_TEXT_OFF
    if len(body) > NEW_TEXT_OFF:
        raise ValueError(f'{REL}: body exceeds NEW_TEXT_OFF')
    body += b'\x00' * (NEW_TEXT_OFF - len(body))

    # Append relocated + extended .text
    new_text = orig_text + PREPARE_PADDED
    assert len(new_text) == NEW_TEXT_SIZE
    body += new_text

    # Update .text section header (sh_offset, sh_size) and ELF e_shoff
    new_shoff = len(body)
    struct.pack_into('<I', body, 32, new_shoff)
    struct.pack_into('<II', shdrs, TEXT_SHNDX * E_SHENTSIZE + 16, NEW_TEXT_OFF, NEW_TEXT_SIZE)
    body += shdrs
    return bytes(body)


def apply(out):
    path = os.path.join(out, 'rootfs', REL)
    write_keep_mode(path, patch(open(path, 'rb').read()))
    print(f'uac2: soc_aic.ko aic_dma_pcm_prepare start_threshold=3/8 buffer ({len(PREPARE_CODE)} B at .text+{NEW_PREPARE_VAL:#x})')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
