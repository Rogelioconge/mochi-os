# Validation

Use `make test` for feature branches, `make dev` for a tested package and `make check` for
integration. Commands, receipts and golden acceptance are in [workflow](../workflow.md).

`make test` skips cost and stress-scale checks (instruction budgets, big-library and fuzz loops;
`PERF` in `test/pod/harness.py`, from `M1_PERF=1`). `make dev`, `check` and `accept` always run
them, so receipts and goldens cover the full suite.

## Test boundaries

| Test | Evidence |
|---|---|
| `test/patch.py`, `test/pod/*.py` | Execute the compiled MIPS payload under Unicorn with stock calls and libc mocked; selected tests also run stock constructors, layout and pointer code |
| `test/pod/harness.py` | Verify final binary/source identity and ELF symbols; model widgets, stock services and watched memory. Counting is opt-in (`m.count()`); `icount` without counting errors. Uncounted calls have no step limit but stay under check.py's test timeout |
| `test/coverflow.py` | Compile the renderer/cache helpers for the host; check geometry, compositing, sampling and filters |
| `test/demo_diff.py` | Limit stock-binary changes to the pinned edits, program header and appended payload |
| `test/awtk_fill.py` | Exercise stock fill, image-scaling and transparency code |
| `test/tools.py` | Check package validation, completion/golden gates, receipts, counters, locks, signals/timeouts and screenshot collisions |
| `test/cdefs.py` | Check the shared `#define` reader (`tools/cdefs.py`) and that it agrees with `harness.O` |
| `test/consts.py` | Check that Python asset-builder constants agree with their `offsets.inc` defines |
| `fwtool verify` / `diff` | Check package members, checksums and changes; packing also checks metadata and rootfs size |

Find feature cases in module notes and test sources; `check.py --list` lists runnable sections.
Keep assertion counts and exhaustive inventories out of docs: they go stale.

## C constants

`tools/cdefs.py` (`defines(path, names=None, known=None, strings=False)`, `parse(text, ...)`) reads
the integer `#define`s of a C file; every reader of C constants in `tools/` and `test/` uses it. A
requested name that is not a define raises `CDefError`. Values are integer expressions evaluated
by an ast walker, not `eval`; function-like macros and non-integer defines are skipped, `#if`
branches are not evaluated. `known={name: int}` seeds outside names; `strings=True` also returns a
one-string-literal define.

Tests write expected draw output as literals. C reads are for cross-checks only (a relation
between two sources, such as "fits within"), never the expected value of what the C code draws:
that would pass if the constant changed. `test/consts.py` (`make test TEST=consts`) is the table
of Python constants that must equal an `offsets.inc` define; add a row for each new one (`XFAIL`
lists known mismatches, `SKIPPED` literals with no C twin).

## Required outcomes

Every task must finish; missing inputs/results, process errors, native signals and timeouts fail.
Logs and failed trees remain. Installation rechecks the dev receipt's recorded inputs, tree,
package and full test scope (not the current source or environment: a built package stays
installable after later edits). Golden acceptance needs both packages and the full suite, or
matching retained evidence.

Emulation proves only the modelled paths. Playback, real frame timing, panel appearance and
hardware behaviour still need the device. A preview is approximate; a successful golden
comparison proves byte identity, not hardware correctness.
