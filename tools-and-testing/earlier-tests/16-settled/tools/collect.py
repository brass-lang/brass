#!/usr/bin/env python3
"""Copy each finished session into sessions/, score it, and print reasoning beside stage 1's grown numbers.

usage: collect.py <out-dir>      the directory build.py made, after every session has finished
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT.parent
sys.path.insert(0, str(V / "15-trivial" / "tools"))
import reasoning

TABLES = [("C", V / "13-evolution-benchmark/cases/C.json"), ("grown", V / "14-scale/cases/grown.json"),
          ("orig", V / "13-evolution-benchmark/cases/baseline.json")]


def main(out):
    out = Path(out).resolve()
    man = json.loads((out / "manifest.json").read_text())
    shutil.copy(out / "manifest.json", ROOT / "manifest.json")
    for label, m in man.items():
        src, dst = out / label, ROOT / "sessions" / label
        sid = json.loads((src / "result.json").read_text())["session_id"]
        t = next(Path.home().glob(f".claude/projects/*/{sid}.jsonl"))
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(t, dst / "transcript.jsonl")
        for f in ("result.json", "prompt.md"):
            shutil.copy(src / f, dst / f)
        shutil.copytree(src / "project" / "src", dst / "project" / "src", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        scores = []
        for name, table in TABLES:
            r = subprocess.run([sys.executable, str(V / "14-scale/tools/evaluate.py"), str(dst / "project"), "keel", str(table),
                                "--json", str(dst / f"eval-{name}.json")], capture_output=True, text=True)
            line = next((l for l in r.stdout.splitlines() if "cases hold" in l), "no summary")
            scores.append(f"{name} {line.split(': ')[-1].split(' cases')[0]}")
        s = reasoning.session(dst / "transcript.jsonl")
        print(f"{label:<4} {m['arm']:<3} {', '.join(scores):<40} reasoning {s['reasoning']/1e3:5.1f}k  largest {s['largest']/1e3:5.1f}k")
    print("stage 1, grown, same estimator: K 60.6k mean (57.8 to 63.7), KC 68.9k mean (one session holds a 64k capped turn), P 26.9k mean")


if __name__ == "__main__":
    main(sys.argv[1])
