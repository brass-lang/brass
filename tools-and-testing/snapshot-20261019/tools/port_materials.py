#!/usr/bin/env python3
"""Build the rerun's task C materials from frozen sources, and the two references task D's materials share.
Exits 1 if any asserted replacement misses.

usage: port_materials.py <out-dir>        writes a fresh task C materials folder; also writes
                                          BRASS-REFERENCE.KC.md and BRASS-REFERENCE-FULL.KC.md into <out-dir>/../D/materials/

Sources, all inside pub-repo:
  validation/14-scale/materials/             stage 1's task C materials: READMEs, maps, host contracts, task text (names renamed)
  validation/29-range-proof/materials/       the newest compact reference (r33's content under an r31 header, corrected here) and
                                             the lean 8 brief and opening, which both tasks share
  validation/reference/BRASS-REFERENCE.md    the full reference, r33; one copy per arm with that arm's run line
Each compact edition gets its arm's run line: the no-tool line for K, the tool line as the newest compact states it for KC.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "validation" / "14-scale" / "materials"
NEW = ROOT / "validation" / "29-range-proof" / "materials"
FULL = ROOT / "validation" / "reference" / "BRASS-REFERENCE.md"

NAMES = [("KEEL-REFERENCE-FULL.md", "BRASS-REFERENCE-FULL.md"), ("KEEL-REFERENCE.md", "BRASS-REFERENCE.md"),
         ("KEELC.md", "BRASS.md"), ("bin/keelc", "bin/brass"), ("keelc", "brass"), ("system.keel", "system.brass"),
         (".keel", ".brass"), ("```keel", "```brass"), ("Keel", "Brass")]
LINE_K = "**What checks your work in this run.** Nothing compiles, checks, or runs. Your patch is evaluated after you finish."
HEADER_OLD = "Compact edition of the editing reference, r31, 2026-10-17: r30 with C46's section on a field for states of several machines."
HEADER_NEW = ("Compact edition of the editing reference, r33, 2026-10-18: r31 with `std.text`'s `of` beside `++` (r32) and the facts that "
              "prove a range (C47, r33). r31, 2026-10-17: r30 with C46's section on a field for states of several machines.")


def renamed(text):
    for a, b in NAMES:
        text = text.replace(a, b)
    return text


def rep(text, old, new, label, misses):
    if text.count(old) != 1:
        misses.append(f"{label}: expected once, found {text.count(old)}: {old[:60]!r}")
        return text
    return text.replace(old, new)


def main(out_s):
    out = Path(out_s)
    if out.exists():
        sys.exit(f"{out} exists; write a fresh folder")
    out.mkdir(parents=True)
    misses = []
    for f in sorted(OLD.iterdir()):                       # stage 1's task-specific files, renamed
        if f.name.startswith("KEEL") or f.name.startswith("OPENING"):
            continue
        text = f.read_text()
        (out / f.name).write_text(text if ".P." in f.name or f.name == "TASK-C.md" else renamed(text))
    for f in ("BRASS.lean8.md", "OPENING.lean8.md"):      # the lean 8 brief and opening, shared with task D
        shutil.copy(NEW / f, out / f)
    compact = NEW.joinpath("BRASS-REFERENCE.KC.md").read_text()
    compact = rep(compact, HEADER_OLD, HEADER_NEW, "compact header", misses)
    lines = compact.split("\n")
    kc_line = [l for l in lines if l.startswith("**What checks your work in this run.**")]
    if len(kc_line) != 1:
        misses.append("compact: run line not found once")
        kc_line = [LINE_K]
    d_mat = out.parent / "D" / "materials"
    for arm, line in (("K", LINE_K), ("KC", kc_line[0])):
        text = "\n".join(line if l.startswith("**What checks your work in this run.**") else l for l in lines)
        (out / f"BRASS-REFERENCE.{arm}.md").write_text(text)
        if arm == "KC" and d_mat.is_dir():
            (d_mat / "BRASS-REFERENCE.KC.md").write_text(text)
    full = FULL.read_text()
    if "Revision r33, 2026-10-18" not in full[:40]:
        misses.append("full: the source is not r33")
    start = full.find("**What checks your work in this run.**")
    end = full.find("\n\n", full.find("- *brass:*"))
    if start < 0 or end < 0:
        misses.append("full: run-line block not found")
    else:
        for arm, line in (("K", LINE_K), ("KC", kc_line[0])):
            text = full[:start] + line + full[end:]
            text = rep(text, "Status: source; a run freezes a copy.", f"Frozen 2026-10-19 for the rerun, arm {arm}.", f"full {arm} status", misses)
            (out / f"BRASS-REFERENCE-FULL.{arm}.md").write_text(text)
            if arm == "KC" and d_mat.is_dir():
                (d_mat / "BRASS-REFERENCE-FULL.KC.md").write_text(text)
    for m in misses:
        print("MISS", m)
    print(f"{out}: {len(list(out.iterdir()))} files, {len(misses)} misses")
    return 1 if misses else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
