#!/usr/bin/env python3
"""Copy each finished PC session into sessions/, score it, and print it beside stage 1's grown P and KC sessions.

usage: collect.py <out-dir>      the directory build.py made, after every session has finished
"""
import json
import re
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


def scores(project, lang, dst=None):
    out = []
    for name, table in TABLES:
        args = [sys.executable, str(V / "14-scale/tools/evaluate.py"), str(project), lang, str(table)]
        if dst:
            args += ["--json", str(dst / f"eval-{name}.json")]
        r = subprocess.run(args, capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if "cases hold" in l), "?")
        out.append(line.split(": ")[-1].split(" cases")[0].replace(" of ", "/"))
    return out


def tools_used(transcript):
    c = {}
    for line in open(transcript):
        d = json.loads(line)
        for x in (d.get("message", {}).get("content") or []) if isinstance(d.get("message"), dict) else []:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                k = x["name"]
                if k == "Bash":
                    cmd = x["input"].get("command", "")
                    m = re.search(r"(?:pytool|keelc)\s+(show --body|show|apply|check|info)", cmd)
                    k = m.group(0).split(None, 1)[1] if m else ("python3" if "python3" in cmd else "Bash")
                c[k] = c.get(k, 0) + 1
    return c


def row(label, arm, res, transcript, sc):
    u = res["usage"]; s = reasoning.session(transcript)
    t = tools_used(transcript)
    print(f"{label:<10} {arm:<3} ${res['total_cost_usd']:.2f}  read {u['cache_read_input_tokens']/1e6:4.2f}M  "
          f"reasoning {s['reasoning']/1e3:5.1f}k  turns {res['num_turns']:3}  cases C {sc[0]}, grown {sc[1]}, orig {sc[2]}  "
          + " ".join(f"{k}:{v}" for k, v in sorted(t.items(), key=lambda kv: -kv[1])))
    return {"label": label, "arm": arm, "cost": res["total_cost_usd"], "read": u["cache_read_input_tokens"],
            "reasoning": round(s["reasoning"]), "turns": res["num_turns"], "cases": sc, "tools": t}


def main(out):
    out = Path(out).resolve()
    man = json.loads((out / "manifest.json").read_text())
    shutil.copy(out / "manifest.json", ROOT / "manifest.json")
    rows = []
    for label in man:
        src, dst = out / label, ROOT / "sessions" / label
        res = json.loads((src / "result.json").read_text())
        t = next(Path.home().glob(f".claude/projects/*/{res['session_id']}.jsonl"))
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(t, dst / "transcript.jsonl")
        for f in ("result.json", "prompt.md"):
            shutil.copy(src / f, dst / f)
        shutil.copytree(src / "project" / "src", dst / "project" / "src", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        rows.append(row(label, "PC", res, dst / "transcript.jsonl", scores(dst / "project", "python", dst)))
    print("stage 1, grown, for comparison:")
    for arm, lang in (("P", "python"), ("KC", "keel")):
        for i in (1, 2, 3):
            d = V / f"14-scale/sessions/grown-{arm}{i}"
            rows.append(row(d.name, arm, json.loads((d / "result.json").read_text()), d / "transcript.jsonl", scores(d / "project", lang)))
    (ROOT / "summary.json").write_text(json.dumps(rows, indent=1))
    for arm in ("P", "PC", "KC"):
        a = [r for r in rows if r["arm"] == arm]
        m = lambda k: sum(r[k] for r in a) / len(a)
        print(f"mean {arm:<3} ${m('cost'):.2f}  read {m('read')/1e6:.2f}M  reasoning {m('reasoning')/1e3:.1f}k  turns {m('turns'):.0f}")


if __name__ == "__main__":
    main(sys.argv[1])
