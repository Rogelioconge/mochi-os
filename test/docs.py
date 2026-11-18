#!/usr/bin/env python3
"""Freshness and size checks for the agent instructions and the docs (docs/recipes.md "Keeping
instructions current").

  uv run python -I test/docs.py

- Every relative link in README.md, AGENTS.md and docs/ resolves.
- Every module doc is linked from the module index (docs/architecture.md).
- The instruction files (AGENTS.md, docs/workflow.md, docs/recipes.md) name only paths, code
  symbols and commits that still exist.
- Size budgets: the instruction files and every doc stay under a byte cap, so that new rules
  replace or merge into old ones instead of piling up.
"""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS = ('AGENTS.md', 'docs/workflow.md', 'docs/recipes.md')
BUDGET = {"AGENTS.md": 6500, 'docs/workflow.md': 8500, 'docs/recipes.md': 10000}
DOC_CAP = 40000   # any other doc
# Headings and header lines that only belong to an implementation in progress (AGENTS.md "Rules").
# Known limitations, gaps and "Possible improvements" are allowed.
# Only markers that cannot be a feature's own topic: headings, never prose.
PLANNING = re.compile(r'^#{2,} .*\b(handover|phase \d+[a-z]?|todo|not done|next steps|open (device )?questions|device checks( still open)?|decisions \(final\))\b'
                      r'|^#{2,} (tests|validation)\s*$|^\*\*Tests?:\*\*', re.I)
CODE_DIRS = ('patch', 'tools', 'test')

ok = fail = 0


def expect(name, cond):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print(f'FAIL {name}')


def docs():
    return [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'docs').rglob('*.md'))]


def links(path):
    text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
    for target in re.findall(r'\]\(([^)\s]+)\)', text):
        if not re.match(r'[a-z]+:', target) and not target.startswith('#'):
            yield target.split('#')[0]


def code_text():
    files = subprocess.run(['git', '-C', str(ROOT), 'ls-files', *CODE_DIRS, 'Makefile'], capture_output=True, text=True, check=True).stdout.split()
    return '\n'.join((ROOT / f).read_text(errors='replace') for f in files if (ROOT / f).is_file() and not f.endswith(('.png', '.bin', '.ttf', '.otf')))


def spans(path):
    """The inline code spans of a doc, outside fenced blocks."""
    text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
    return re.findall(r'`([^`\n]+)`', text)


def is_path(s): return re.fullmatch(r'[\w.-]+(/[\w.-]+)+/?|[\w-]+\.(py|c|h|md|inc)', s) is not None and not s.endswith('.json')


def path_exists(s, code, sections):
    if re.fullmatch(r'\w+/\w+_tests', s): return s in sections   # a test section
    if '/' not in s:   # a bare file name: anywhere in the code dirs, or a generated file the code names
        return any((ROOT / d).rglob(s) for d in CODE_DIRS) or s in code
    return (ROOT / s.rstrip('/')).exists() or (ROOT / 'docs' / s).exists()
def is_symbol(s): return re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{3,}', s) is not None and ('_' in s or s != s.lower())


def main():
    for d in docs():
        for target in links(d):
            expect(f'{d.relative_to(ROOT)}: link {target} resolves', (d.parent / target).exists())
    index = (ROOT / 'docs/architecture.md').read_text()
    for m in sorted((ROOT / 'docs/modules').glob('*.md')):
        expect(f'docs/modules/{m.name} is listed in docs/architecture.md', f'modules/{m.name})' in index)
    code = code_text()
    sys.path.insert(0, str(ROOT / 'tools'))
    import check
    sections = {t.removeprefix('patch:') for t in check.ALL_TESTS}
    for name in INSTRUCTIONS:
        p = ROOT / name
        for s in spans(p):
            s = s.strip()
            if '_/' in s or '<' in s: continue   # an abbreviation or a placeholder
            if is_path(s) and not s.startswith(('/', 'out/', 'work/', 'tree/')):
                expect(f'{name}: path `{s}` exists', path_exists(s, code, sections))
            elif is_symbol(s):
                expect(f'{name}: symbol `{s}` is still in {"/".join(CODE_DIRS)}', re.search(r'\b' + re.escape(s) + r'\b', code) is not None)
        for sha in re.findall(r'git show (?:--stat )?([0-9a-f]{7,40})', p.read_text()):
            r = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', sha + '^{commit}'], capture_output=True)
            expect(f'{name}: commit {sha} exists', r.returncode == 0)
    branch = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True).stdout.strip()
    strict = branch == 'main' or bool(os.environ.get('M1_DOCS_STRICT'))   # feature branches may carry a handover until the squash merge
    for d in sorted((ROOT / 'docs/modules').glob('*.md')):
        for n, line in enumerate(d.read_text().splitlines(), 1):
            if PLANNING.search(line):
                msg = f'docs/modules/{d.name}:{n}: planning left in a module doc ({line.strip()[:60]})'
                if strict: expect(msg, False)
                else: print('note:', msg, '(fails on main)')
    for d in docs():
        rel = str(d.relative_to(ROOT)); cap = BUDGET.get(rel, DOC_CAP)
        expect(f'{rel}: {d.stat().st_size} bytes within the {cap} byte budget (merge or prune instead of adding)', d.stat().st_size <= cap)
    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__': main()
