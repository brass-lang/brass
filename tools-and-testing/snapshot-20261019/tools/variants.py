#!/usr/bin/env python3
"""Planted-wrong variants for the rerun: each copies a tree, plants one defect, and runs a case table.
A variant is caught when every case it must fail fails. This is the negative control for the respelled trees and the
ported evaluator: a pass rate alone would not show that the evaluator still sees a wrong program.

usage: variants.py [--json out.json]

The variants are stage 1's (benchmark 13's task C set and 14-scale's grown-subsystem set), with the Brass patch text
respelled where the old text used a form C25 to C34 changed (one line: `where it.status`). The Python text is unchanged.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# tree, language, kind, what, file, old, new, cases, must fail
TASK_C = [
    ("python", "missed site", "a report's approval ignores advances in the budget", "review.py",
     "    within = within_budget(store, r.department, r.period, lines.budgeted_total(r.lines))\n",
     "    from .budget import spend_of\n    within = spend_of(store.reports_for(r.department, r.period), ()) + lines.budgeted_total(r.lines) <= store.department(r.department).budget\n",
     ["V17", "V40"]),
    ("brass", "missed site", "a report's approval ignores advances in the budget", "review.brass",
     "let spent: Int = budget.department_spend(store, r.department, r.period)?",
     "let spent: Int = budget.spend_of(store.reports_for(r.department, r.period)?, [])", ["V17", "V40"]),
    ("python", "broken invariant", "a settled advance still counts against the budget", "advances.py",
     "return a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID)",
     "return a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID, AdvanceStatus.SETTLED)", ["V18", "V20"]),
    ("brass", "broken invariant", "a settled advance still counts against the budget", "advances.brass",
     "type Counted     = Advance where it.status in {AdvanceStatus.Approved, AdvanceStatus.Paid}",
     "type Counted     = Advance where it.status in {AdvanceStatus.Approved, AdvanceStatus.Paid, AdvanceStatus.Settled}", ["V18", "V20"]),
    ("python", "superficial", "the advance is settled; the payment is not reduced", "payment.py",
     "due = lines.total(r.lines) - a.amount", "due = lines.total(r.lines)", ["V27", "V28"]),
    ("brass", "superficial", "the advance is settled; the payment is not reduced", "payment.brass",
     "let due: Int = lines.total(r.lines) - a.amount", "let due: Int = lines.total(r.lines)", ["V27", "V28"]),
]

GROWN = [
    ("brass", "missed site", "commitments count a received PO's full amount", "records.brass",
     "else if p.status in {PoStatus.Received, PoStatus.Closed} then sum = sum + p.received",
     "else if p.status in {PoStatus.Received, PoStatus.Closed} then sum = sum + p.amount", ["P19", "P33"]),
    ("brass", "broken invariant", "a revoked delegation still counts", "records.brass",
     "fn in_force(d, period) = not d.revoked and d.first <= period and period <= d.last",
     "fn in_force(d, period) = d.first <= period and period <= d.last", ["P11"]),
    ("brass", "superficial", "a card match ignores the line's category", "cards.brass",
     "where l.category == t.category and l.amount == t.amount", "where l.amount == t.amount", ["K09"]),
    ("brass", "missed site", "over_limit counts disputed charges", "card_limits.brass",
     "if t.badge == badge and not (t.status in {records.CardStatus.Disputed}) then", "if t.badge == badge then", ["C05"]),
    ("brass", "broken invariant", "readiness ignores requested POs", "readiness.brass",
     "ready: not closed and open == 0 and requested == 0 and waiting == 0", "ready: not closed and open == 0 and waiting == 0", ["Q04"]),
    ("python", "missed site", "commitments count a received PO's full amount", "records.py",
     "    if po.status in (PoStatus.RECEIVED, PoStatus.CLOSED):\n        return po.received",
     "    if po.status in (PoStatus.RECEIVED, PoStatus.CLOSED):\n        return po.amount", ["P19", "P33"]),
    ("python", "broken invariant", "a revoked delegation still counts", "records.py",
     "    return not d.revoked and d.first <= period <= d.last", "    return d.first <= period <= d.last", ["P11"]),
    ("python", "superficial", "a card match ignores the line's category", "cards.py",
     "l.category is t.category and l.amount == t.amount", "l.amount == t.amount", ["K09"]),
    ("python", "missed site", "over_limit counts disputed charges", "card_limits.py",
     "        if t.status is not CardStatus.DISPUTED:\n            spent", "        if True:\n            spent", ["C05"]),
    ("python", "broken invariant", "readiness ignores requested POs", "readiness.py",
     "not closed and open_txns == 0 and requested == 0 and submitted == 0", "not closed and open_txns == 0 and submitted == 0", ["Q04"]),
]

SETS = [(f"reference/C/{size}", "C.json", v) for size in ("small", "grown") for v in TASK_C] + \
       [("baseline/grown", "grown.json", v) for v in GROWN]


def run(tree_rel, lang, fname, old, new, cases):
    tmp = Path(tempfile.mkdtemp())
    tree = tmp / lang
    shutil.copytree(ROOT / tree_rel / lang, tree, ignore=shutil.ignore_patterns("__pycache__"))
    f = tree / "src" / "desk" / fname
    s = f.read_text()
    if s.count(old) != 1:
        shutil.rmtree(tmp)
        return None, f"patch text found {s.count(old)} times in {fname}"
    f.write_text(s.replace(old, new))
    out = tmp / "r.json"
    subprocess.run([sys.executable, str(ROOT / "tools" / "evaluate.py"), str(tree), lang, str(ROOT / "cases" / cases),
                    "--json", str(out)], capture_output=True, text=True)
    res = json.loads(out.read_text()) if out.exists() else None
    shutil.rmtree(tmp)
    return res, None


def main(argv):
    rows, ok = [], True
    for tree_rel, cases, (lang, kind, what, fname, old, new, must) in SETS:
        res, err = run(tree_rel, lang, fname, old, new, cases)
        if err or res is None:
            print(f"{tree_rel:<20} {lang:<6} {kind:<16} ERROR {err or 'no result'}"); ok = False
            rows.append({"tree": tree_rel, "language": lang, "kind": kind, "what": what, "caught": False, "error": err})
            continue
        failed = sorted(c["id"] for c in res["cases"] if not c["holds"])
        missing = [m for m in must if m not in failed]
        ok &= not missing
        rows.append({"tree": tree_rel, "language": lang, "kind": kind, "what": what, "must_fail": must, "failed": failed,
                     "caught": not missing})
        print(f"{tree_rel:<20} {lang:<6} {kind:<16} {'caught' if not missing else 'MISSED ' + ','.join(missing):<8}  {what}: {len(failed)} fail")
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(rows, indent=1))
    print(f"{sum(r['caught'] for r in rows)} of {len(SETS)} variants caught")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
