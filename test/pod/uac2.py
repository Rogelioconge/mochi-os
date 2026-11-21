"""USB DAC XRUN recovery in soc_aic.ko (tools/mod_uac2.py, docs/modules/uac2.md):
ELF integrity, Capstone disassembly, Unicorn MIPS32r2 execution of the patched
aic_dma_pcm_prepare across all guard paths, and ALSA ring-buffer simulation
(startup, sample-rate switch, XRUN recovery, and close during prefill)."""
import io, os, struct
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn import mips_const as MC
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_uac2 as mu
import mod_wpa as mw

CODE_BASE = 0x100000
DATA_BASE = 0x200000
RET_ADDR = 0x10f000

PCM_STATE_SETUP, PCM_STATE_PREPARED, PCM_STATE_RUNNING, PCM_STATE_XRUN, PCM_STATE_SUSPENDED = 1, 2, 3, 4, 7


def _exec_prepare(code, *, substream_valid=True, stream=0, runtime_valid=True,
                  start_thr=1, status_valid=True, pcm_state=PCM_STATE_XRUN,
                  buffer_size=16384, task_valid=True, task_flags=0x00200000):
    """Run patched aic_dma_pcm_prepare bytes in Unicorn MIPS32r2 LE; return (v0, new_start_thr, regs_ok)."""
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    uc.mem_map(CODE_BASE, 0x10000)
    uc.mem_map(DATA_BASE, 0x10000)
    uc.mem_write(CODE_BASE, code)

    sub_addr = DATA_BASE + 0x100 if substream_valid else 0
    rt_addr = DATA_BASE + 0x400 if runtime_valid else 0
    st_addr = DATA_BASE + 0x600 if status_valid else 0
    ti_addr = DATA_BASE + 0x800
    task_addr = DATA_BASE + 0xa00 if task_valid else 0

    if substream_valid:
        uc.mem_write(sub_addr + mu.SUBSTREAM_STREAM, struct.pack('<I', stream))
        uc.mem_write(sub_addr + mu.SUBSTREAM_RUNTIME, struct.pack('<I', rt_addr))
    if runtime_valid:
        uc.mem_write(rt_addr + mu.RUNTIME_BUFFER_SIZE, struct.pack('<I', buffer_size))
        uc.mem_write(rt_addr + mu.RUNTIME_START_THR, struct.pack('<I', start_thr))
        uc.mem_write(rt_addr + mu.RUNTIME_STATUS, struct.pack('<I', st_addr))
    if status_valid:
        uc.mem_write(st_addr, struct.pack('<I', pcm_state))
    uc.mem_write(ti_addr, struct.pack('<I', task_addr))
    if task_valid:
        uc.mem_write(task_addr + mu.TASK_FLAGS, struct.pack('<I', task_flags))

    # Seed callee-saved registers to verify leaf function preserves all of them
    saved = {MC.UC_MIPS_REG_S0: 0x11110000, MC.UC_MIPS_REG_S1: 0x22220001, MC.UC_MIPS_REG_S2: 0x33330002,
             MC.UC_MIPS_REG_S3: 0x44440003, MC.UC_MIPS_REG_S4: 0x55550004, MC.UC_MIPS_REG_S5: 0x66660005,
             MC.UC_MIPS_REG_S6: 0x77770006, MC.UC_MIPS_REG_S7: 0x88880007, MC.UC_MIPS_REG_FP: 0x99990008,
             MC.UC_MIPS_REG_SP: DATA_BASE + 0xf000, MC.UC_MIPS_REG_GP: ti_addr}
    for r, val in saved.items():
        uc.reg_write(r, val)
    uc.reg_write(MC.UC_MIPS_REG_A0, DATA_BASE + 0x40)   # component
    uc.reg_write(MC.UC_MIPS_REG_A1, sub_addr)           # substream
    uc.reg_write(MC.UC_MIPS_REG_RA, RET_ADDR)
    uc.reg_write(MC.UC_MIPS_REG_V0, 0xdeadbeef)

    uc.emu_start(CODE_BASE, RET_ADDR, count=100)
    v0 = uc.reg_read(MC.UC_MIPS_REG_V0)
    new_thr = struct.unpack('<I', uc.mem_read(rt_addr + mu.RUNTIME_START_THR, 4))[0] if runtime_valid else None
    regs_ok = all(uc.reg_read(r) == val for r, val in saved.items())
    return v0, new_thr, regs_ok


def elf_tests(ctx):
    expect = ctx.expect
    stock_path = os.path.join(mw.stock_root(), mu.REL)
    ours_path = os.path.join(WORK, 'rootfs', mu.REL)
    stock, ours = open(stock_path, 'rb').read(), open(ours_path, 'rb').read()

    # ---- stock input & determinism ----
    expect(mu.sha256(stock) == mu.STOCK_SHA and len(stock) == mu.STOCK_SIZE, 'stock soc_aic.ko matches pinned SHA-256 and size')
    expect(mu.patch(stock) == ours, 'mod_uac2.patch is deterministic and matches the built tree')
    s, o = os.stat(stock_path), os.stat(ours_path)
    expect((s.st_mode, int(s.st_mtime)) == (o.st_mode, int(o.st_mtime)), 'mode and mtime stay stock')

    # ---- ELF structure of patched module ----
    elf = ELFFile(io.BytesIO(ours))
    text = elf.get_section_by_name('.text')
    expect(text['sh_offset'] == mu.NEW_TEXT_OFF and text['sh_offset'] % 16 == 0 and text['sh_size'] == mu.NEW_TEXT_SIZE,
           'relocated .text is 16-byte aligned with expected size')
    expect(text.data()[:mu.TEXT_SIZE] == stock[mu.TEXT_OFF:mu.TEXT_OFF + mu.TEXT_SIZE],
           'original .text bytes are preserved verbatim')
    expect(text.data()[mu.NEW_PREPARE_VAL:mu.NEW_PREPARE_VAL + len(mu.PREPARE_CODE)] == mu.PREPARE_CODE,
           'new aic_dma_pcm_prepare sits at .text+0x22c0')
    expect(all(b == 0 for b in ours[mu.TEXT_OFF:mu.TEXT_OFF + mu.TEXT_SIZE]),
           'old .text hole is zeroed')

    symtab = elf.get_section_by_name('.symtab')
    prep = symtab.get_symbol(mu.PREPARE_SYM_IDX)
    expect(prep.name == 'aic_dma_pcm_prepare' and prep['st_value'] == mu.NEW_PREPARE_VAL
           and prep['st_size'] == len(mu.PREPARE_CODE) and prep['st_shndx'] == mu.TEXT_SHNDX,
           'aic_dma_pcm_prepare symbol points to new code with exact size')

    # Non-.text sections keep exact stock bytes and offsets
    stock_elf = ELFFile(io.BytesIO(stock))
    other_ok = True
    for idx in range(1, elf.num_sections()):
        if idx in (mu.TEXT_SHNDX, 28):   # .text and .symtab are the only edited sections
            continue
        a, b = stock_elf.get_section(idx), elf.get_section(idx)
        if (a.name, a['sh_offset'], a['sh_size']) != (b.name, b['sh_offset'], b['sh_size']):
            other_ok = False
        if a['sh_type'] != 'SHT_NOBITS' and a.data() != b.data():
            other_ok = False
    expect(other_ok, 'every section except .text and .symtab is byte-identical at its stock offset')

    # Capstone disassembles every instruction cleanly and ends with jr $ra; nop
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    insns = list(md.disasm(mu.PREPARE_CODE, mu.NEW_PREPARE_VAL))
    expect(len(insns) == len(mu.PREPARE_CODE) // 4 and insns[-2].mnemonic == 'jr' and insns[-2].op_str == '$ra'
           and insns[-1].mnemonic == 'nop', 'Capstone decodes all 30 instructions ending in jr $ra; nop')

    # ---- refusals ----
    for what, bad in (('the patched module', ours), ('a corrupted byte', stock[:0x100] + bytes([stock[0x100] ^ 1]) + stock[0x101:])):
        try: mu.patch(bad); refused = False
        except ValueError: refused = True
        expect(refused, f'mod_uac2 refuses {what}')


def emu_tests(ctx):
    expect = ctx.expect
    ours = open(os.path.join(WORK, 'rootfs', mu.REL), 'rb').read()
    elf = ELFFile(io.BytesIO(ours))
    prep = elf.get_section_by_name('.symtab').get_symbol(mu.PREPARE_SYM_IDX)
    code = elf.get_section_by_name('.text').data()[prep['st_value']:prep['st_value'] + prep['st_size']]

    # f_uac2 XRUN recovery PCM (S32_LE stereo, 128 KiB ring = 16,384 frames): start_threshold 1 -> 6,144 (49,152 B)
    v0, thr, ok = _exec_prepare(code, stream=0, start_thr=1, pcm_state=PCM_STATE_XRUN, buffer_size=16384, task_flags=0x00200000)
    expect(v0 == 0 and thr == 6144 and ok, 'f_uac2 XRUN PCM: start_threshold 1 -> 6144 frames (49,152 B), regs preserved')

    # f_uac2 XRUN recovery DSD (S16_LE stereo, 128 KiB ring = 32,768 frames): start_threshold 1 -> 12,288 (49,152 B)
    v0, thr, ok = _exec_prepare(code, stream=0, start_thr=1, pcm_state=PCM_STATE_XRUN, buffer_size=32768, task_flags=0x00208040)
    expect(v0 == 0 and thr == 12288 and ok, 'f_uac2 XRUN DSD: start_threshold 1 -> 12288 frames (49,152 B)')

    # Non-XRUN states (initial open SETUP, sample-rate switch reopen SETUP, PREPARED, RUNNING, SUSPENDED): untouched!
    for name, st in (('SETUP (initial open / rate switch)', PCM_STATE_SETUP),
                     ('PREPARED', PCM_STATE_PREPARED),
                     ('RUNNING', PCM_STATE_RUNNING),
                     ('SUSPENDED', PCM_STATE_SUSPENDED)):
        v0, thr, ok = _exec_prepare(code, stream=0, start_thr=1, pcm_state=st, buffer_size=16384, task_flags=0x00200000)
        expect(v0 == 0 and thr == 1 and ok, f'non-XRUN state {name} keeps start_threshold == 1')

    # Subsequent XRUN prepare (start_threshold already 6144): untouched
    v0, thr, ok = _exec_prepare(code, stream=0, start_thr=6144, pcm_state=PCM_STATE_XRUN, buffer_size=16384, task_flags=0x00200000)
    expect(v0 == 0 and thr == 6144 and ok, 'subsequent XRUN prepare keeps already-raised start_threshold')

    # Userspace playback (hciplayer / aplay / bluealsa, PF_KTHREAD == 0): untouched even on XRUN with start_threshold == 1
    v0, thr, ok = _exec_prepare(code, stream=0, start_thr=1, pcm_state=PCM_STATE_XRUN, buffer_size=16384, task_flags=0x00400100)
    expect(v0 == 0 and thr == 1 and ok, 'userspace process (PF_KTHREAD=0) is untouched even on XRUN')

    # Capture stream (stream == 1): untouched even from kworker on XRUN
    v0, thr, ok = _exec_prepare(code, stream=1, start_thr=1, pcm_state=PCM_STATE_XRUN, buffer_size=16384, task_flags=0x00200000)
    expect(v0 == 0 and thr == 1 and ok, 'capture stream is untouched')

    # Caller that explicitly set SW_PARAMS (start_threshold != 1): untouched
    v0, thr, ok = _exec_prepare(code, stream=0, start_thr=2048, pcm_state=PCM_STATE_XRUN, buffer_size=16384, task_flags=0x00200000)
    expect(v0 == 0 and thr == 2048 and ok, 'explicit SW_PARAMS start_threshold is untouched')

    # Guard edge cases: NULL pointers and tiny buffer_size
    for label, kw in (
        ('NULL substream', dict(substream_valid=False)),
        ('NULL runtime', dict(runtime_valid=False)),
        ('NULL status', dict(status_valid=False)),
        ('NULL current', dict(task_valid=False)),
        ('tiny buffer_size=4', dict(buffer_size=4)),
        ('zero buffer_size', dict(buffer_size=0)),
    ):
        v0, thr, ok = _exec_prepare(code, **kw)
        expect(v0 == 0 and (thr is None or thr == 1) and ok, f'guard handles {label} safely')

    # ---- ALSA + f_uac2 lifecycle model using the emulated aic_dma_pcm_prepare ----
    buf_pcm = 16384
    chunk_init, chunk_steady = 64000 // 8, 48000 // 8   # 8000 frames, 6000 frames

    class FakeAlsa:
        """Minimal model of pcm_open / write / XRUN / close driven by the real emulated prepare bytes."""
        def __init__(self):
            self.open()
        def open(self):
            self.state, self.thr, self.queued, self.started_count = PCM_STATE_SETUP, 1, 0, 0
            self.prepare()
        def prepare(self):
            v0, new_thr, ok = _exec_prepare(code, stream=0, start_thr=self.thr, pcm_state=self.state,
                                            buffer_size=buf_pcm, task_flags=0x00200000)
            assert v0 == 0 and ok
            self.thr, self.state, self.queued = new_thr, PCM_STATE_PREPARED, 0
        def write(self, frames):
            assert self.state in (PCM_STATE_PREPARED, PCM_STATE_RUNNING)
            assert self.queued + frames <= buf_pcm
            self.queued += frames
            if self.state == PCM_STATE_PREPARED and self.queued >= self.thr:
                self.state = PCM_STATE_RUNNING
                self.started_count += 1
        def close(self):
            # snd_pcm_release -> snd_pcm_drop: valid in PREPARED or RUNNING, clears stream state
            assert self.state in (PCM_STATE_SETUP, PCM_STATE_PREPARED, PCM_STATE_RUNNING, PCM_STATE_XRUN)
            self.state, self.queued = 0, 0

    # 1. Initial open (SETUP): 64 KB starts immediately with start_threshold == 1
    pcm = FakeAlsa()
    expect(pcm.thr == 1 and pcm.state == PCM_STATE_PREPARED, 'initial open keeps start_threshold == 1')
    pcm.write(chunk_init)
    expect(pcm.state == PCM_STATE_RUNNING and pcm.queued == chunk_init, 'initial 64 KB chunk starts DMA immediately')

    # 2. Sample-rate switch while USB stream stays open (reopen -> SETUP, steady 48 KB chunk):
    #    must start immediately on the first 48 KB chunk (no extra 125 ms wait, never stranded on early close)
    pcm.close()
    pcm.open()
    expect(pcm.thr == 1, 'sample-rate switch reopen (SETUP) keeps start_threshold == 1')
    pcm.write(chunk_steady)
    expect(pcm.state == PCM_STATE_RUNNING and pcm.queued == chunk_steady,
           'sample-rate switch starts DMA on the very first 48 KB chunk without waiting for a second chunk')

    # 3. XRUN recovery: prepare in XRUN raises start_threshold to 6144; first 48 KB chunk holds in PREPARED,
    #    second 48 KB chunk starts DMA with 96 KB queued (48 KB cushion after 1 chunk plays)
    pcm.state, pcm.queued = PCM_STATE_XRUN, 0
    pcm.prepare()
    expect(pcm.thr == 6144 and pcm.state == PCM_STATE_PREPARED, 'XRUN recovery raises start_threshold to 6144')
    pcm.write(chunk_steady)
    expect(pcm.state == PCM_STATE_PREPARED and pcm.queued == chunk_steady,
           'first 48 KB chunk after XRUN holds in PREPARED (prefilling)')
    pcm.write(chunk_steady)
    expect(pcm.state == PCM_STATE_RUNNING and pcm.queued == 2 * chunk_steady <= buf_pcm,
           'second 48 KB chunk starts DMA with 96 KB queued (48 KB cushion after one 125 ms chunk drains)')

    # 4. Close during XRUN prefill (only 1st 48 KB chunk written, still PREPARED), then reopen on next stream:
    #    close drops cleanly and next open starts fresh with start_threshold == 1
    pcm.state, pcm.queued = PCM_STATE_XRUN, 0
    pcm.prepare()
    pcm.write(chunk_steady)
    expect(pcm.state == PCM_STATE_PREPARED and pcm.thr == 6144, 'stream is in PREPARED during XRUN prefill')
    pcm.close()
    pcm.open()
    expect(pcm.thr == 1 and pcm.state == PCM_STATE_PREPARED,
           'closing during XRUN prefill and reopening resets cleanly to start_threshold == 1')
    pcm.write(chunk_steady)
    expect(pcm.state == PCM_STATE_RUNNING, 'reopened stream plays first chunk immediately')


def run(ctx):
    elf_tests(ctx)
    emu_tests(ctx)
