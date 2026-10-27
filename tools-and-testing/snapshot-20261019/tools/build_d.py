#!/usr/bin/env python3
"""Build task D session directories outside the repository, and their prompts. The Stage 2 trial's builder
(validation/25-stage2/tools/build.py) with two arms and the rerun's inputs: start trees and materials under rerun/D/,
the frozen lean 8 tool under rerun/tools/brass-lean8/.

usage: build_d.py <out-dir> --cap N [--tag TEXT] LABEL:ARM [...]     ARM is P or KC

P: plain Python. KC: Brass with `brass` at lean 8: compact reference, the lean 8 brief and opening with the host
contract, the map, and `converters.txt`. Every arm has the same tools; the KC prompt asks for `apply` and the record
counts whether the session used it. --tag TEXT opens every prompt with "Session TEXT/LABEL.".
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "tools" / "brass-lean8"
MAT, START = ROOT / "D" / "materials", ROOT / "D" / "start"
CLOSING = ("When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task "
           "that caused the most unnecessary work; (3) every assumption you made that the task did not settle.")
ARM_LINE = {
    "P": "You may run `python3`, and write and run your own tests under that directory. The project has no tests of its own.",
    "KC": "Read the code you need with `bin/brass show` and `show --body` (several modules per call), then write every edit "
          "in one `bin/brass apply`, which runs the check. Fix anything it marks with another `apply`.",
}


def ignore(_, names):
    return [n for n in names if n == "__pycache__"]


def project(out, label, arm):
    lang = "python" if arm == "P" else "brass"
    p = out / label / "project"
    if p.exists():
        shutil.rmtree(p)
    shutil.copytree(START / lang / "src", p / "src", ignore=ignore)
    shutil.copy(MAT / f"README.{arm}.md", p / "README.md")
    if arm == "P":
        return p
    shutil.copy(START / "brass" / "converters.txt", p / "converters.txt")
    shutil.copy(MAT / "BRASS-REFERENCE.KC.md", p / "BRASS-REFERENCE.md")
    shutil.copy(MAT / "BRASS-REFERENCE-FULL.KC.md", p / "BRASS-REFERENCE-FULL.md")
    shutil.copy(MAT / "host-contract.txt", p / "host-contract.txt")
    shutil.copy(MAT / "BRASS.lean8.md", p / "BRASS.md")
    tools = out / "_tools"
    if not tools.exists():
        tools.mkdir(parents=True)
        shutil.copy(PROXY / "brass.py", tools / "brass.py")
        shutil.copy(PROXY / "brasseval.py", tools / "brasseval.py")
    base = out / "_baseline-brass"
    if not base.exists():
        shutil.copytree(START / "brass" / "src", base / "src", ignore=ignore)
    (p / "bin").mkdir()
    w = p / "bin" / "brass"
    w.write_text(f'#!/bin/sh\nBRASS_LEAN=8 BRASS_PROJECT="$(cd "$(dirname "$0")/.." && pwd)" BRASS_SRC=desk BRASS_BASELINE={base} '
                 f'exec python3 {tools}/brass.py "$@"\n')
    w.chmod(0o755)
    return p


def prompt(p, arm, cap, tag=""):
    parts = [(f"Session {tag}. " if tag else "") + f"Complete the task using the supplied project at `{p}`. Everything you may read is under that directory; "
             "do not read, search, or list anything outside it. " + ("Start with `README.md`. " if arm == "P" else "")
             + ARM_LINE[arm] + " Make the change by modifying files under that directory."
             + f" Budget: at most {cap} tool calls and sixty minutes. " + CLOSING]
    if arm == "KC":
        parts.append("The project's `BRASS-REFERENCE.md` is reproduced below so you know the language before you start.\n\n"
                     + (p / "BRASS-REFERENCE.md").read_text())
        parts.append((MAT / "OPENING.lean8.md").read_text().replace("@@CONTRACT@@", (p / "host-contract.txt").read_text().strip()))
        parts.append((MAT / "MAP.md").read_text())
    parts.append("TASK\n\n" + (MAT / "TASK-D.md").read_text())
    return "\n\n".join(parts)


def main(argv):
    out = Path(argv[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cap = int(argv[argv.index("--cap") + 1])
    tag = argv[argv.index("--tag") + 1] if "--tag" in argv else ""
    man_path = out / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    for spec in [a for a in argv[1:] if ":" in a and not a.startswith("--")]:
        label, arm = spec.split(":")
        p = project(out, label, arm)
        text = prompt(p, arm, cap, f"{tag}/{label}" if tag else "")
        (out / label / "prompt.md").write_text(text)
        man[label] = {"arm": arm, "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16], "prompt_chars": len(text)}
        print(f"{label:<8} {arm:<3} {len(text):>6} chars")
    man_path.write_text(json.dumps(man, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
