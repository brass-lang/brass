#!/usr/bin/env python3
"""Build PC sessions: stage 1's grown task C in Python, with `bin/pytool` and the same prompt material the KC arm had.

usage: build.py <out-dir> --cap N LABEL [...]

The prompt is stage 1's, arm by arm: P's opening and README, KC's tool line, tool notes, host contract, and map, each
rewritten for Python (materials/). The tool is copied beside the sessions, so nothing names the repository.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S1 = ROOT.parent / "14-scale"
sys.path.insert(0, str(S1 / "tools"))
import build as s1

MAT = ROOT / "materials"
ARM_LINE = (s1.ARM_LINE["P"] + " Read the code you need with `bin/pytool show` and `show --body` (several modules per call), "
            "then write every edit in one `bin/pytool apply`. Fix anything it marks with another `apply`.")


def project(out, label):
    p = out / label / "project"
    if p.exists():
        shutil.rmtree(p)
    shutil.copytree(S1 / "baseline" / "python" / "src", p / "src", ignore=s1.ignore)
    shutil.copy(MAT / "README.PC.grown.md", p / "README.md")
    shutil.copy(MAT / "contract.grown.txt", p / "host-contract.txt")
    t = out / "_tools"; t.mkdir(exist_ok=True)
    shutil.copy(ROOT / "tools" / "pytool.py", t / "pytool.py")
    (p / "bin").mkdir()
    w = p / "bin" / "pytool"
    w.write_text(f'#!/bin/sh\nPYTOOL_PROJECT="$(cd "$(dirname "$0")/.." && pwd)" exec python3 {t}/pytool.py "$@"\n')
    w.chmod(0o755)
    return p


def prompt(p, cap):
    parts = [f"Complete the task using the supplied project at `{p}`. Everything you may read is under that directory; "
             "do not read, search, or list anything outside it. " + ARM_LINE + " Make the change by modifying files under that directory."
             + f" Budget: at most {cap} tool calls and sixty minutes. " + s1.CLOSING,
             (MAT / "OPENING.PC.md").read_text().replace("@@CONTRACT@@", (p / "host-contract.txt").read_text().strip()),
             (MAT / "MAP.grown.md").read_text(),
             "TASK\n\n" + (S1 / "materials" / "TASK-C.md").read_text()]
    return "\n\n".join(parts)


def main(argv):
    out = Path(argv[0]).resolve(); out.mkdir(parents=True, exist_ok=True)
    cap = int(argv[argv.index("--cap") + 1])
    man = {}
    for label in [a for a in argv[1:] if a.startswith("PC")]:
        p = project(out, label)
        text = prompt(p, cap)
        (out / label / "prompt.md").write_text(text)
        man[label] = {"arm": "PC", "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16], "prompt_chars": len(text)}
        print(f"{label:<5} {len(text):>6} chars")
    (out / "manifest.json").write_text(json.dumps(man, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
