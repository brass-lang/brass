#!/usr/bin/env python3
"""The grammar repeats the spec's examples and tables; this checks that every copy is unchanged (C43).

usage: check-grammar-agreement.py        exits 1 and names each drift

Every ```brass block in brass-core-grammar.md is compared with the spec's code, line for line: each
non-comment line must appear in a spec code block with the same indentation, and the block's lines must
occur in the spec in the same order. Every grammar table row containing code must appear in the spec verbatim.
Full-line comments are skipped, since excerpt headers name their source. Run it after editing either file.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "brass-core-spec.md"
GRAMMAR = ROOT / "docs" / "brass-core-grammar.md"
BLOCK = re.compile(r"```brass[^\n]*\n(.*?)```", re.S)


def code_lines(block: str) -> list[str]:
    return [l.rstrip() for l in block.splitlines() if l.strip() and not l.lstrip().startswith("#")]


def in_order(lines: list[str], spec: list[str]) -> bool:
    pos = 0
    for line in lines:
        try:
            pos = spec.index(line, pos) + 1
        except ValueError:
            return False
    return True


def main() -> int:
    spec_text = SPEC.read_text()
    spec_code = [l for b in BLOCK.findall(spec_text) for l in code_lines(b)]
    spec_set = set(spec_code)
    spec_rows = {l.rstrip() for l in spec_text.splitlines() if l.startswith("|")}
    grammar = GRAMMAR.read_text()
    drift = []
    for n, block in enumerate(BLOCK.findall(grammar), 1):
        lines = code_lines(block)
        drift += [f"block {n}: not in spec code: {l}" for l in lines if l not in spec_set]
        if all(l in spec_set for l in lines) and not in_order(lines, spec_code):
            drift.append(f"block {n}: lines are not in the spec's order")
    for row in grammar.splitlines():
        if row.startswith("|") and "`" in row and row.rstrip() not in spec_rows:
            drift.append(f"table row not in spec: {row.rstrip()}")
    for d in drift:
        print(d)
    print(f"{len(drift)} drifts between grammar and spec")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
