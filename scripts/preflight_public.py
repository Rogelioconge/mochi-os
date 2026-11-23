#!/usr/bin/env python3
"""Conservative Git index public-release path checks for Mochi OS.

Does not replace a review of Git history, licenses, or secrets in file contents.
Known legitimate upstream files are allowlisted by their exact Git blob SHA.
"""
from pathlib import Path
import re
import subprocess
import sys

# Verified from imfing/m1plus-music on 2026-11-23. The exception applies
# ONLY if the staged Git blob and the working file match these exact SHA-1s.
PUBLIC_UPSTREAM_BLOBS = {
    "assets/cacert.pem": "c5818b24d021b6244cdc0ee865f997acd627f4fc",
    "firmware/README.md": "f7977c9108fae0eac62797a305958992a72de109",
}

BAD_ROOTS = re.compile(r"(^|/)(firmware|out|work|\.venv|\.mochi-backups)/", re.I)
BAD_NAMES = re.compile(r"(^|/)(update\.bin|\.env(?:\..*)?|id_rsa|id_ed25519)$", re.I)
BAD_EXTENSIONS = re.compile(r"\.(?:flac|mp3|wav|dsf|dff|ape|pem|key|p12|pfx)$", re.I)
MAX_FILE_BYTES = 15 * 1024 * 1024


def git(*args):
    return subprocess.run(["git", *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def main():
    if not Path(".git").exists() and not Path(".git").is_file():
        print("Run from your Git checkout.")
        return 2

    # Inspect index (what will be committed), not only working-tree file paths.
    entries = git("ls-files", "-s", "-z").split(b"\x00")
    issues = []
    count = 0
    trusted = []
    for entry in entries:
        if not entry:
            continue
        # e.g. "100644 abcd... 0\tassets/cacert.pem"
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, sha, stage = metadata.decode("ascii").split()
        name = path_bytes.decode("utf-8", "surrogateescape")
        count += 1
        if stage != "0":
            issues.append(f"{name} (unresolved merge stage {stage})")
            continue

        if name in PUBLIC_UPSTREAM_BLOBS:
            allowed_sha = PUBLIC_UPSTREAM_BLOBS[name]
            file_path = Path(name)
            if sha == allowed_sha and file_path.is_file() and \
                    git("hash-object", "--", name).decode().strip() == allowed_sha:
                trusted.append(name)
                continue
            issues.append(f"{name} (known upstream file modified; review contents)")
            continue

        if BAD_ROOTS.search(name) or BAD_NAMES.search(name) or BAD_EXTENSIONS.search(name):
            issues.append(f"{name} (risky filename)")
            continue
        try:
            size = int(git("cat-file", "-s", sha))
        except (subprocess.CalledProcessError, ValueError):
            issues.append(f"{name} (cannot inspect staged size)")
            continue
        if size > MAX_FILE_BYTES:
            issues.append(f"{name} (staged object larger than 15 MiB; review)")

    print(f"Staged/tracked index entries examined: {count}")
    for name in trusted:
        print(f"OK: reviewed upstream public file unchanged: {name}")
    for issue in issues:
        print(f"REVIEW: {issue}")
    print("Reminder: audit Git history and contents for secrets, licensing, and firmware blobs before publishing.")
    if issues:
        print("Preflight failed: do not publish until these findings are reviewed.")
        return 1
    print("No obvious risky staged paths found. This is NOT a complete security audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
