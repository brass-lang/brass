#!/usr/bin/env python3
"""Build sessions for the settled-puzzle test: stage 1's grown task C, unchanged, with SETTLED.md placed before the task.

usage: build.py <out-dir> --cap N LABEL:ARM [...]     ARM is K or KC (grown size only)

Everything else is stage 1's builder and frozen materials, so the prompt differs from stage 1's grown prompt for the
same arm only in the project path and the added pattern.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "14-scale" / "tools"))
import build as s1


def main(argv):
    out = Path(argv[0]).resolve(); out.mkdir(parents=True, exist_ok=True)
    cap = int(argv[argv.index("--cap") + 1])
    pattern = (ROOT / "SETTLED.md").read_text().strip()
    man = {}
    for spec in [a for a in argv[1:] if ":" in a]:
        label, arm = spec.split(":")
        if arm not in ("K", "KC"):
            sys.exit(f"{spec}: arm must be K or KC")
        p = s1.project(out, label, "grown", arm)
        head, task = s1.prompt(p, "grown", arm, cap).rsplit("TASK\n\n", 1)
        text = head + pattern + "\n\nTASK\n\n" + task
        (out / label / "prompt.md").write_text(text)
        man[label] = {"arm": arm, "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16], "prompt_chars": len(text)}
        print(f"{label:<6} {arm:<3} {len(text):>6} chars")
    (out / "manifest.json").write_text(json.dumps(man, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
