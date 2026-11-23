#!/usr/bin/env python3
"""Execute the stock V2.1 grid builder's MIPS instructions under Unicorn.

AWTK calls are redirected to executable MIPS return stubs. This preserves
original jalr/bal instructions, branch delay slots and return addresses while
exercising MIPS control flow, PIC, loop counts and early failure paths;
it does NOT prove real AWTK widget construction or safe late re-entry.

READ ONLY: no firmware writes, no launcher patches, no bypass authorisation.
"""
import argparse
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_sibling(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = load_sibling('mox_rebuild_contract')
cut = rc.cut
ENTRY = 0x534064
END = 0x5341F4
STOP = 0x01000100
STACK = 0x70018000
HOME = 0x30001000
SLIDE = 0x30002000
MOCK_BASE = 0x01001000
HELPER = 0x533D8C
JR_RA_NOP = struct.pack('<II', 0x03E00008, 0)

# Caller in original V2.1: $a0=Home, $a1=1, $t9=builder.
# Only these exact calls can be mocked; all other calls abort the probe.
SITES = {
    0x5340AC: 'lookup_root',
    0x5340CC: 'lookup_slide',
    0x5340F4: 'setup_root',
    0x534110: 'item_count',
    0x534154: 'set_page_count',
    0x53417C: 'create_page',
    0x534190: 'populate_page',  # bal to original 0x533d8c, intercepted
    0x5341AC: 'setup_without_flag',
    0x5341C0: 'set_page_index',
}


def sections(blob):
    """File-backed ELF32 little-endian load segments, no dynamic linker."""
    if len(blob) < 52 or blob[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected ELF32 little endian demo')
    phoff = struct.unpack_from('<I', blob, 28)[0]
    entsize, count = struct.unpack_from('<HH', blob, 42)
    if entsize != 32 or count < 1 or count > 256 or phoff + count * entsize > len(blob):
        raise ValueError('Invalid ELF program headers')
    out = []
    for i in range(count):
        ptype, off, va, _, fsize, msize, _, _ = struct.unpack_from('<8I', blob, phoff + i * entsize)
        if ptype != 1:
            continue
        if fsize > msize or off + fsize > len(blob) or va + msize > 0xFFFFFFFF:
            raise ValueError('Invalid PT_LOAD at index ' + str(i))
        if msize:
            out.append((va, blob[off:off+fsize], msize))
    if not out:
        raise ValueError('ELF lacks PT_LOAD')
    return out


def preflight(blob):
    contract = rc.inspect(blob)  # verified stock V2.1 instructions, including $a1 and PIC
    for site, name in SITES.items():
        off = cut.elf_offset(blob, site)
        word = struct.unpack_from('<I', blob, off)[0]
        if site == 0x534190:
            if cut.direct_call_target(word, site) != 0x533D8C:
                raise ValueError('Wrong bal destination at populate_page')
        elif (word >> 26) != 0 or (word & 0x3F) != 9 or ((word >> 21) & 31) != 25:
            raise ValueError(f'Unexpected {name} callsite at {site:#x}: {word:#x}')
    loads = sections(blob)
    assert any(va <= ENTRY < va + size for va, _, size in loads)
    return {'contract': contract, 'segments': len(loads), 'mocked_sites': len(SITES)}


def execute(blob, *, first_ok=True, second_ok=True, items=7, backend=None):
    """Run actual MIPS jalr/bal/return flow with AWTK *bodies* mocked.

    Older Sprint 11 skipped the jalr instruction and its delay slot by
    rewriting PC at UC_HOOK_CODE. On MIPS this can invalidate branch state
    and the page-count computation. Here we let the CPU execute the real
    call/delay-slot, return through a MIPS jr $ra stub, and preserve the
    original PIC/global-pointer and saved-register behavior.
    """
    from unicorn import Uc, UcError, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2,
                                    UC_MIPS_REG_A3, UC_MIPS_REG_PC, UC_MIPS_REG_GP,
                                    UC_MIPS_REG_RA, UC_MIPS_REG_SP, UC_MIPS_REG_T9,
                                    UC_MIPS_REG_V0, UC_MIPS_REG_S0, UC_MIPS_REG_S1,
                                    UC_MIPS_REG_S2, UC_MIPS_REG_S3, UC_MIPS_REG_S4,
                                    UC_MIPS_REG_S5, UC_MIPS_REG_S6)
    if not 0 <= items <= 120:
        raise ValueError('Mock item count must be between 0 and 120')
    machine = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    page = 0x1000
    for va, data, msize in sections(blob):
        start = va & ~(page-1)
        end = (va + msize + page - 1) & ~(page-1)
        machine.mem_map(start, end-start)
        if data:
            machine.mem_write(va, data)
    machine.mem_map(0x70000000, 0x20000)
    machine.mem_map(STOP & ~(page-1), page)
    machine.mem_map(MOCK_BASE, page)

    # Only in the Unicorn memory copy: replace the helper body at the exact
    # original BAL target. Its BAL and delay slot remain unmodified and run.
    machine.mem_write(HELPER, JR_RA_NOP)
    call_stubs = {site: MOCK_BASE + i*16 for i, site in enumerate(
        site for site in SITES if site != 0x534190)}
    reverse_stubs = {addr: SITES[site] for site, addr in call_stubs.items()}
    for addr in reverse_stubs:
        machine.mem_write(addr, JR_RA_NOP)
    stub_delay_slots = {addr + 4 for addr in reverse_stubs} | {HELPER + 4}

    machine.reg_write(UC_MIPS_REG_A0, HOME)
    machine.reg_write(UC_MIPS_REG_A1, 1)
    machine.reg_write(UC_MIPS_REG_T9, ENTRY)
    machine.reg_write(UC_MIPS_REG_RA, STOP)
    machine.reg_write(UC_MIPS_REG_SP, STACK)
    preserved = (UC_MIPS_REG_S0, UC_MIPS_REG_S1, UC_MIPS_REG_S2,
                 UC_MIPS_REG_S3, UC_MIPS_REG_S4, UC_MIPS_REG_S5, UC_MIPS_REG_S6)
    saved = {reg: 0x0A000000 + i * 0x100 for i, reg in enumerate(preserved)}
    for reg, val in saved.items():
        machine.reg_write(reg, val)
    calls = []
    observed_gp = []
    page_idx = 0
    unexpected = []
    trace = []

    def state(u, address):
        return {'pc': hex(address), 'v0': u.reg_read(UC_MIPS_REG_V0),
                's0': u.reg_read(UC_MIPS_REG_S0),
                'ra': hex(u.reg_read(UC_MIPS_REG_RA))}

    def on_code(u, address, size, _):
        nonlocal page_idx
        if address == STOP or address in stub_delay_slots:
            # The return stub's NOP *also executes* as a MIPS delay slot.
            return
        if address in call_stubs:
            # Keep the original jalr instruction and its delay slot. Only
            # substitute the callee address; the stub runs `jr $ra; nop`.
            u.reg_write(UC_MIPS_REG_T9, call_stubs[address])
            return
        if address in reverse_stubs or address == HELPER:
            name = 'populate_page' if address == HELPER else reverse_stubs[address]
            a0 = u.reg_read(UC_MIPS_REG_A0)
            a1 = u.reg_read(UC_MIPS_REG_A1)
            a2 = u.reg_read(UC_MIPS_REG_A2)
            a3 = u.reg_read(UC_MIPS_REG_A3)
            ra = u.reg_read(UC_MIPS_REG_RA)
            site = 0x534190 if address == HELPER else next(
                site for site, dst in call_stubs.items() if dst == address)
            if ra != site+8:
                unexpected.append(f'{name} called with wrong return address {ra:#x}')
                u.emu_stop()
                return
            calls.append({'site': hex(site), 'function': name, 'a0': hex(a0),
                          'a1': a1, 'a2': a2, 'a3': a3})
            ret = 0
            if backend is not None:
                # Stateful fake AWTK: retain widget side effects across MIPS
                # invocations. It is *not* the real device's AWTK runtime.
                try:
                    ret = backend.call(name, a0, a1, a2, a3)
                    if not isinstance(ret, int) or not 0 <= ret <= 0xFFFFFFFF:
                        raise ValueError('non-integer/out-of-range fake AWTK return')
                except Exception as exc:
                    unexpected.append(f'Stateful AWTK {name}: {exc}')
                    u.emu_stop()
                    return
            elif name == 'lookup_root':
                ret = HOME + 0x100 if first_ok else 0
            elif name == 'lookup_slide':
                ret = SLIDE if second_ok else 0
            elif name == 'item_count':
                ret = items
            elif name == 'create_page':
                ret = 0x30010000 + page_idx * 0x1000
                page_idx += 1
            elif name == 'populate_page':
                if a0 != 0x30010000 + (page_idx-1)*0x1000 or page_idx == 0:
                    unexpected.append('Populate did not receive the newly created widget')
                    u.emu_stop()
                    return
            u.reg_write(UC_MIPS_REG_V0, ret)
            # The MIPS stub's own jr $ra and NOP delay slot finish the call.
            return
        if not ENTRY <= address < END:
            unexpected.append(f'Unexpected branch to {address:#x}')
            u.emu_stop()
            return
        if address == 0x534070:
            observed_gp.append(u.reg_read(UC_MIPS_REG_GP))
        if address in (0x534118, 0x534128, 0x534138, 0x53413C, 0x534168):
            trace.append(state(u, address))
        op = struct.unpack('<I', u.mem_read(address, 4))[0]
        # Abort on any unlisted jalr or bal, rather than executing unknown
        # stock code or reaching the device's actual AWTK implementation.
        if (((op >> 26) == 0 and (op & 0x3F) == 9)
                or cut.direct_call_target(op, address) is not None) and address not in SITES:
            unexpected.append(f'Unmocked call at {address:#x}')
            u.emu_stop()

    machine.hook_add(UC_HOOK_CODE, on_code)
    try:
        machine.emu_start(ENTRY, STOP, timeout=1000000, count=30000)
    except UcError as exc:
        raise RuntimeError('MIPS simulation stopped: ' + str(exc) +
                           '; trace=' + repr(trace[-12:])) from exc
    if unexpected:
        raise AssertionError('; '.join(unexpected) + '; trace=' + repr(trace[-12:]))
    pc = machine.reg_read(UC_MIPS_REG_PC)
    if pc != STOP:
        raise AssertionError(f'Builder did not return to its caller; PC={pc:#x}; trace={trace[-12:]}')
    gp_want = 0xA03ED0
    if observed_gp != [gp_want]:
        raise AssertionError(f'Incorrect stock PIC $gp: {observed_gp!r}')
    if machine.reg_read(UC_MIPS_REG_SP) != STACK:
        raise AssertionError('Stack not balanced')
    if machine.reg_read(UC_MIPS_REG_RA) != STOP:
        raise AssertionError('Return address corrupted')
    for reg, val in saved.items():
        if machine.reg_read(reg) != val:
            raise AssertionError('Callee-saved register corrupted')
    result = machine.reg_read(UC_MIPS_REG_V0)
    expected = 0 if first_ok and second_ok else 0x10
    if result != expected:
        raise AssertionError(f'Expected result {expected:#x}, got {result:#x}; trace={trace[-12:]}')
    names = [c['function'] for c in calls]
    if not first_ok or not second_ok:
        if names != ['lookup_root', 'lookup_slide']:
            raise AssertionError('Unexpected side effect on failed lookup: ' + str(names))
    elif backend is None:
        want_pages = (items+5)//6
        if names.count('create_page') != want_pages or names.count('populate_page') != want_pages:
            raise AssertionError(f'Wrong page build calls: {names}; trace={trace[-12:]}')
        if names.count('set_page_count') != 1 or names.count('set_page_index') != 1:
            raise AssertionError('Expected stock page count and index setup')
        if names.count('setup_without_flag'):
            raise AssertionError('Wrong flag=0 branch')
    else:
        # A stateful backend validates the actual widget graph rather than
        # relying on count-only checks. Keep checking the call type and flag.
        if names.count('setup_without_flag'):
            raise AssertionError('Wrong flag=0 branch during late recovery')
    return {'returned': hex(result), 'mips_gp': hex(gp_want), 'calls': calls,
            'created_page_calls': names.count('create_page'),
            'populated_page_calls': names.count('populate_page'),
            'trace': trace}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--demo', type=Path, default=ROOT/'work/check/release/work/mod-release/rootfs/release/bin/demo')
    ap.add_argument('--report', type=Path, default=ROOT/'out/mox-cutover/builder-mips-emulation.json')
    ap.add_argument('--preflight', action='store_true', help='Check binary anchors without Unicorn')
    args = ap.parse_args()
    if not args.demo.is_file():
        ap.error(f'Built demo missing: {args.demo}; run make test TEST=home')
    blob = args.demo.read_bytes()
    check = preflight(blob)
    print('OK: verified V2.1 ABI and', check['mocked_sites'], 'MIPS callsites')
    report = {'binary_sha256': check['contract']['binary_sha256'],
              'format': 'MIPS32 little-endian, intercepted AWTK calls',
              'tested': [] if args.preflight else None, 'native_bypass_authorized': False,
              'late_recovery_proven': False, 'hardware_tested': False}
    if not args.preflight:
        cases = [('missing_root', False, True, 7),
                 ('missing_slide', True, False, 7),
                 ('one_page', True, True, 5),
                 ('two_pages', True, True, 7)]
        report['tested'] = []
        for label, r1, r2, count in cases:
            try:
                result = execute(blob, first_ok=r1, second_ok=r2, items=count)
            except Exception as exc:
                # Keep the failed scenario on disk for diagnosis, but still
                # fail the command. Never misrepresent a failed test as OK.
                report['failed_scenario'] = label
                report['error'] = str(exc)
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, indent=2) + '\n')
                raise
            result['scenario'] = label
            report['tested'].append(result)
            print('OK:', label, 'MIPS returned', result['returned'], 'pages:', result['created_page_calls'])
        print('MOX: 4/4 real MIPS control-flow cases (AWTK MOCKED)')
    else:
        print('PRECHECK only: no MIPS instructions were executed')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('BLOCKED: actual late AWTK recovery and native launcher bypass still unproven')
    print('Report:', args.report)


if __name__ == '__main__':
    main()
