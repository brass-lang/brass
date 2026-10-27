#!/usr/bin/env python3
"""Build rerun session directories outside the repository, and their prompts. Stage 1's builder
(validation/14-scale/tools/build.py) ported to current Brass: same arms, prompt, budget, and closing; the inputs come
from rerun/ (respelled trees, r33 materials) and the tool is the rerun's frozen copy of the lean 8 stand-in.

usage: build.py <out-dir> --cap N [--tag TEXT] LABEL:SIZE:ARM [...]     SIZE is small or grown; ARM is P, K, or KC

Task C on either baseline. P: plain Python. K: Brass without the tool. KC: Brass with `brass` at lean 8: compact
reference, the lean 8 brief and opening with the host contract, and the map in the prompt. Every arm has the same
tools; the KC prompt asks for `apply` and the record counts whether the session used it.
--tag TEXT opens every prompt with "Session TEXT/LABEL." so no two sessions share a prompt prefix.
The brass stand-in and the baseline it diffs against are copied beside the sessions, so nothing names the repository.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "tools" / "brass-lean8"   # the rerun's frozen copy of the lean 8 stand-in
MAT = ROOT / "materials"
BASE = {"small": ROOT / "baseline" / "small", "grown": ROOT / "baseline" / "grown"}

CLOSING = ("When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task "
           "that caused the most unnecessary work; (3) every assumption you made that the task did not settle.")
ARM_LINE = {
    "P": "You may run `python3`, and write and run your own tests under that directory. The project has no tests of its own.",
    "K": "Nothing compiles, checks, or runs in this project.",
    "KC": "Read the code you need with `bin/brass show` and `show --body` (several modules per call), then write every edit "
          "in one `bin/brass apply`, which runs the check. Fix anything it marks with another `apply`.",
}


def ignore(_, names):
    return [n for n in names if n == "__pycache__"]


def brass_copy(out, size):
    t = out / "_tools"
    t.mkdir(parents=True, exist_ok=True)
    shutil.copy(PROXY / "brass.py", t / "brass.py")
    shutil.copy(PROXY / "brasseval.py", t / "brasseval.py")
    b = out / f"_baseline-brass-{size}"
    if not b.exists():
        shutil.copytree(BASE[size] / "brass" / "src", b / "src", ignore=ignore)
    return t, b


def project(out, label, size, arm):
    lang = "python" if arm == "P" else "brass"
    p = out / label / "project"
    if p.exists():
        shutil.rmtree(p)
    shutil.copytree(BASE[size] / lang / "src", p / "src", ignore=ignore)
    shutil.copy(MAT / f"README.{arm}.{size}.md", p / "README.md")
    if lang == "brass":
        shutil.copy(MAT / f"BRASS-REFERENCE.{arm}.md", p / "BRASS-REFERENCE.md")
        shutil.copy(MAT / f"BRASS-REFERENCE-FULL.{arm}.md", p / "BRASS-REFERENCE-FULL.md")
    if arm == "KC":
        tools, base = brass_copy(out, size)
        shutil.copy(MAT / f"contract.{size}.txt", p / "host-contract.txt")
        shutil.copy(MAT / "BRASS.lean8.md", p / "BRASS.md")
        (p / "bin").mkdir()
        w = p / "bin" / "brass"
        w.write_text(f'#!/bin/sh\nBRASS_LEAN=8 BRASS_PROJECT="$(cd "$(dirname "$0")/.." && pwd)" BRASS_SRC=desk BRASS_BASELINE={base} '
                     f'exec python3 {tools}/brass.py "$@"\n')
        w.chmod(0o755)
    return p


def prompt(p, size, arm, cap, tag=""):
    parts = [(f"Session {tag}. " if tag else "") + f"Complete the task using the supplied project at `{p}`. Everything you may read is under that directory; "
             "do not read, search, or list anything outside it. " + ("" if arm == "KC" else "Start with `README.md`. ")
             + ARM_LINE[arm] + " Make the change by modifying files under that directory."
             + f" Budget: at most {cap} tool calls and sixty minutes. " + CLOSING]
    if arm in ("K", "KC"):
        parts.append("The project's `BRASS-REFERENCE.md` is reproduced below so you know the language before you start.\n\n"
                     + (p / "BRASS-REFERENCE.md").read_text())
    if arm == "KC":
        parts.append((MAT / "OPENING.lean8.md").read_text().replace("@@CONTRACT@@", (p / "host-contract.txt").read_text().strip()))
        parts.append((MAT / f"MAP.{size}.md").read_text())
    parts.append("TASK\n\n" + (MAT / "TASK-C.md").read_text())
    return "\n\n".join(parts)


def main(argv):
    out = Path(argv[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cap = int(argv[argv.index("--cap") + 1])
    tag = argv[argv.index("--tag") + 1] if "--tag" in argv else ""
    specs = [a for a in argv[1:] if ":" in a and not a.startswith("--")]
    man_path = out / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    for spec in specs:
        label, size, arm = spec.split(":")
        p = project(out, label, size, arm)
        text = prompt(p, size, arm, cap, f"{tag}/{label}" if tag else "")
        (out / label / "prompt.md").write_text(text)
        man[label] = {"size": size, "arm": arm, "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16], "prompt_chars": len(text)}
        print(f"{label:<14} {size:<6} {arm:<3} {len(text):>6} chars")
    man_path.write_text(json.dumps(man, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
