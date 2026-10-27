#!/usr/bin/env python3
"""Planted-wrong variants of task D's references: each copies a reference tree, plants one defect, runs D.json, and
checks that every case named for it fails. A variant is caught when all of them do.

usage: variants_d.py [python|brass ...]      both languages when none is named
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "D"
D = ROOT / "cases" / "D.json"

PY = "src/desk/"
VARIANTS = {
    "python": [
        ("netting removed: an Approved trip counts its whole commitment", PY + "trips.py",
         "    return max(0, t.committed - covered)", "    return t.committed", ["D44", "D33", "D55"]),
        ("delegation checked for the trip's period, not today", PY + "trip_desk.py",
         "in_force(d, today)", "in_force(d, t.period)", ["D36"]),
        ("matched card transactions counted again", PY + "trip_desk.py",
         "if x.badge == t.badge and x.matched is None]", "if x.badge == t.badge]", ["D57"]),
        ("an unchanged repeat is audited", PY + "trip_desk.py",
         "if t.status is TripStatus.RECONCILED and t.reconciliation == rec:", "if False:", ["D68", "D67"]),
        ("the period is closed before its trips", PY + "payment.py",
         "    close_open_trips(store, who.badge, period)                # trips first, the period last: a retry finishes the job\n    store.close_period(period)",
         "    store.close_period(period)\n    close_open_trips(store, who.badge, period)", ["D75"]),
        ("an amendment keeps the approvals", PY + "trips.py",
         "    return replace(t, plan=plan, committed=committed, approvals=())", "    return replace(t, plan=plan, committed=committed)", ["D16"]),
        ("a Closed trip blocks a new filing", PY + "trip_desk.py",
         "t.badge == badge and t.status is not TripStatus.CLOSED", "t.badge == badge", ["D13"]),
    ],
    "brass": [
        ("netting removed: an Approved trip counts its whole commitment", PY + "trips.brass",
         "if t.committed > covered then t.committed - covered else 0", "t.committed", ["D44", "D33", "D55"]),
        ("delegation checked for the trip's period, not today", PY + "trip_desk.brass",
         "delegated(reg, required, who.badge, today)", "delegated(reg, required, who.badge, t.period)", ["D36"]),
        ("matched card transactions counted again", PY + "trip_desk.brass",
         "if x.badge == badge and x.matched == None then", "if x.badge == badge then", ["D57"]),
        ("an unchanged repeat is audited", PY + "trip_desk.brass",
         "if t.reconciliation == rec then", "if false then", ["D68", "D67"]),
        ("the period is closed before its trips", PY + "payment.brass",
         "        trip_desk.close_open_trips(store, who.badge, period)?          # trips first, the period last: a retry finishes the job\n        store.close_period(period)",
         "        store.close_period(period)?\n        trip_desk.close_open_trips(store, who.badge, period)", ["D75"]),
        ("an amendment keeps the approvals", PY + "trips.brass",
         "fn amend_requested(t, p, committed)   = t with { plan: p, committed: committed, approvals: [] }",
         "fn amend_requested(t, p, committed)   = t with { plan: p, committed: committed }", ["D16"]),
        ("a Closed trip blocks a new filing", PY + "trip_desk.brass",
         "t.badge == badge and not (t.status in {trips.TripStatus.Closed})", "t.badge == badge", ["D13"]),
    ],
}


def run(lang):
    caught = 0
    for what, rel, old, new, must in VARIANTS[lang]:
        tmp = Path(tempfile.mkdtemp())
        tree = tmp / "tree"
        shutil.copytree(ROOT / "reference" / lang, tree, ignore=shutil.ignore_patterns("__pycache__"))
        f = tree / rel
        text = f.read_text()
        n = text.count(old)
        if n < 1:
            print(f"  ✗ {lang}: {what}: the planted text is not in {rel}")
            continue
        f.write_text(text.replace(old, new))
        out = tmp / "eval.json"
        subprocess.run([sys.executable, str(HERE / "evaluate_d.py"), str(tree), lang, str(D), "--json", str(out)], capture_output=True, text=True)
        rows = {r["id"]: r for r in json.loads(out.read_text())["cases"]} if out.exists() else {}
        failed = [i for i in must if i in rows and not rows[i]["holds"]]
        ok = len(failed) == len(must)
        caught += ok
        others = sorted(i for i, r in rows.items() if not r["holds"] and i not in must)
        print(f"  {'✓' if ok else '✗'} {lang}: {what}: {len(failed)} of {len(must)} named cases fail" + (f"; also {', '.join(others)}" if others else ""))
        shutil.rmtree(tmp, ignore_errors=True)
    return caught, len(VARIANTS[lang])


if __name__ == "__main__":
    langs = sys.argv[1:] or ["python", "brass"]
    total = [run(l) for l in langs]
    print(f"variants caught: {sum(c for c, _ in total)} of {sum(n for _, n in total)}")
