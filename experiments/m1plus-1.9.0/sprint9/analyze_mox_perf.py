#!/usr/bin/env python3
"""Analyse optional Mochi UI timing file (v1). Never writes to the source file."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

PHASES = ("total", "database", "index", "paint", "cover", "scroll")


def parse(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as stream:
        for lineno, row in enumerate(csv.reader(stream), 1):
            if not row:
                continue
            if len(row) != 9 or row[0] != "mox1" or row[1] not in {"albums", "songs"} or row[3] not in PHASES:
                raise ValueError(f"Invalid mox1 row at {lineno}: {row!r}")
            try:
                entries, count, total, peak, over16, over33 = map(int, [row[2], row[4], row[5], row[6], row[7], row[8]])
            except ValueError as exc:
                raise ValueError(f"Invalid integer in row {lineno}: {row!r}") from exc
            if any(n < 0 for n in (entries, count, total, peak, over16, over33)) or over33 > over16 or over16 > count:
                raise ValueError(f"Invalid counters at {lineno}")
            rows.append((row[1], entries, row[3], count, total, peak, over16, over33))
    return rows


def summary(rows):
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for page, entries, phase, count, total, peak, over16, over33 in rows:
        s = agg[page, phase]
        s[0] += count
        s[1] += total
        s[2] = max(s[2], peak)
        s[3] += over16
        s[4] += over33
        s[5] = max(s[5], entries)
    return agg


def format_report(rows):
    if not rows:
        return "El archivo no contiene registros Mochi.\n"
    agg = summary(rows)
    lines = ["# Mochi OS — medición de latencia de UI", "", "*Tiempos medidos por funciones; NO son FPS ni latencia completa del dedo a la pantalla.*", ""]
    for page in ("albums", "songs"):
        found = [(phase, agg[page, phase]) for phase in PHASES if (page, phase) in agg]
        if not found:
            continue
        lines += [f"## {page.title()}", "", "| Fase | Muestras | Media (ms) | Máx. (ms) | >16 ms | >33 ms |", "|---|---:|---:|---:|---:|---:|"]
        for phase, (cnt, total, peak, c16, c33, entries) in found:
            lines.append(f"| {phase} | {cnt} | {(total / cnt / 1000) if cnt else 0:.2f} | {peak / 1000:.2f} | {c16} | {c33} |")
        lines += ["", "Interpretación: `database` y `index` contribuyen al tiempo de apertura de Songs; `paint`, `cover` y `scroll` son partes separadas de la experiencia táctil. No sumes sus medias como si fueran FPS.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path, help="/mnt/mmc/mochi-performance.csv copiado al Mac")
    parser.add_argument("--out", type=Path, help="Guardar informe Markdown; por defecto imprimir")
    args = parser.parse_args()
    report = format_report(parse(args.csv))
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"Report: {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
