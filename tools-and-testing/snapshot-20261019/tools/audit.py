#!/usr/bin/env python3
"""Audit the rerun's inputs in one command: regenerate each from stage 1's frozen inputs, compare byte for byte, and
re-run every check. Exits 1 on any failure.

usage: audit.py [--freeze]        --freeze also prints the hash table for rerun/FROZEN.md

Checks, in order:
  1  reproducible: the six Brass trees, the grown references (patch then respell), and the materials regenerate identically
  2  Python trees and the case tables are byte-identical to stage 1's
  3  no retired spelling (`partial`, `private interface`, `has`, `.keel`) in any rerun Brass tree; bare `where` fields
     are the tool's to find, and 4 and 5 show it finds them
  4  the current brass check is clean on all six trees (lean 3, with the host contract)
  5  the current brass check rejects stage 1's grown tree for each old form (control)
  6  every tree holds every case table it should (22 runs)
  7  every planted-wrong variant is caught (22)
  8  respelling agrees with stage 2's hand respelling on exactly the 22 modules stage 2 left alone
  9  the ported evaluator, builder, and launcher differ from stage 1's by exactly the approved diff (hash asserted; a new
     diff is printed in full and fails until its hash is approved here)
  10 a built session of each arm and size has no old name in its prompt, and each KC project's own check is clean
  11 the frozen lean 8 tool is byte-identical to the live stand-in it was frozen from (or the README says it is not)
  12 task D: start trees, cases, task text, and materials identical to their trial sources; both references hold every case
     on all four tables; the 14 planted variants are caught; the D reference is the stage 2 reference under .brass names
"""
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RERUN = Path(__file__).resolve().parents[1]
PUB = RERUN.parent
V = PUB / "validation"
PY = sys.executable
BRASS = RERUN / "tools" / "brass-lean8" / "brass.py"   # the frozen copy every tool session runs
LIVE = V / "proxy" / "bin" / "brass"
OLD_TREES = {"baseline/small": V / "13-evolution-benchmark/baseline/keel", "baseline/grown": V / "14-scale/baseline/keel",
             "reference/C/small": V / "13-evolution-benchmark/reference/C/keel",
             "reference/C-alt/small": V / "14-scale/reference/C-alt/keel"}
REF_SRC = {"C": V / "13-evolution-benchmark/reference/C", "C-alt": V / "14-scale/reference/C-alt"}
TREES = ["baseline/small", "baseline/grown", "reference/C/small", "reference/C/grown", "reference/C-alt/small", "reference/C-alt/grown"]
CASES = [(t, c, n) for t, c, n in [
    ("baseline/small", "baseline.json", 82), ("baseline/grown", "baseline.json", 82), ("baseline/grown", "grown.json", 112),
    ("reference/C/small", "C.json", 122), ("reference/C/grown", "C.json", 122), ("reference/C/grown", "grown.json", 112),
    ("reference/C/grown", "baseline.json", 82), ("reference/C-alt/small", "C.json", 122), ("reference/C-alt/grown", "C.json", 122),
    ("reference/C-alt/grown", "grown.json", 112), ("reference/C-alt/grown", "baseline.json", 82)]]
OLD_FORM = re.compile(r"\bpartial fn\b|\bprivate interface\b|\bhas\s+[a-z_]+\s*:|\.keel\b")
STAGE2_SAME = ["desk/advances", "desk/allowances", "desk/budget", "desk/card_limits", "desk/cards", "desk/delegation", "desk/entities",
               "desk/exceptions", "desk/forecasting", "desk/host", "desk/ids", "desk/lines", "desk/purchasing", "desk/readiness",
               "desk/records", "desk/registry", "desk/reporting", "desk/reports", "desk/routing", "desk/staff", "desk/vendors", "system"]
# SHA-256 (first 16 hex) of `diff <stage 1 file> <rerun file>`, approved 2026-10-16 after review of every line.
APPROVED_DIFF = {"tools/evaluate.py": "58da770138ddaef0", "tools/build.py": "b79d452db5e28691", "tools/launch.sh": "8c4a18814c1aca38",
                 "tools/evaluate_d.py": "66adb55ae2d52230", "tools/variants_d.py": "7ae557ddae68d931", "tools/build_d.py": "269e9fbe546b950e"}

failures = []


def check(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def same_tree(a, b):
    fa = sorted(str(p.relative_to(a)) for p in a.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    fb = sorted(str(p.relative_to(b)) for p in b.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    if fa != fb:
        return False, f"file lists differ: {sorted(set(fa) ^ set(fb))[:5]}"
    bad = [f for f in fa if (a / f).read_bytes() != (b / f).read_bytes()]
    return not bad, f"{len(bad)} files differ: {bad[:5]}" if bad else f"{len(fa)} files identical"


def run(cmd, env=None, cwd=None, stdin=None):
    return subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=cwd, input=stdin)


def brass_check(tree, size):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(tree, tmp / "p")
    shutil.copy(RERUN / "materials" / f"contract.{size}.txt", tmp / "p" / "host-contract.txt")
    r = run([PY, str(BRASS), "check"], {"BRASS_PROJECT": str(tmp / "p"), "BRASS_SRC": "desk", "BRASS_LEAN": "8",
                                         "BRASS_NO_LOG": "1", "BRASS_BASELINE": str(tmp / "p")})
    shutil.rmtree(tmp)
    return r.stdout + r.stderr


def digest(p):
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    h = hashlib.sha256()
    for f in sorted(f for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts):
        h.update(str(f.relative_to(p)).encode()); h.update(f.read_bytes())
    return h.hexdigest()[:16]


def main(argv):
    tmp = Path(tempfile.mkdtemp())
    print("1  reproducible from stage 1")
    for rel, old in OLD_TREES.items():
        out = tmp / "re" / rel
        r = run([PY, str(RERUN / "tools/respell.py"), str(old), str(out)])
        check(r.returncode == 0, f"respell {rel} runs clean", r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
        ok, d = same_tree(out, RERUN / rel / "brass"); check(ok, f"{rel}/brass regenerates identically", d)
    for ref, src in REF_SRC.items():
        for lang in ("keel", "python"):
            g = tmp / "grown" / f"{ref}-{lang}"
            shutil.copytree(V / "14-scale/baseline" / lang, g, ignore=shutil.ignore_patterns("__pycache__"))
            patch = run(["diff", "-ruN", ".", str(src / lang)], cwd=V / "13-evolution-benchmark/baseline" / lang).stdout
            r = run(["patch", "-p1", "--no-backup-if-mismatch"], cwd=g, stdin=patch)
            hunks = patch.count("\n@@")
            check(r.returncode == 0 and "FAILED" not in r.stdout, f"{ref} {lang} patch applies to the grown tree", f"{hunks} hunks")
            if lang == "keel":
                out = tmp / "re" / f"reference/{ref}/grown"
                run([PY, str(RERUN / "tools/respell.py"), str(g), str(out)])
                ok, d = same_tree(out, RERUN / f"reference/{ref}/grown/brass"); check(ok, f"reference/{ref}/grown/brass regenerates identically", d)
            else:
                ok, d = same_tree(g, RERUN / f"reference/{ref}/grown/python"); check(ok, f"reference/{ref}/grown/python regenerates identically", d)
    mat = tmp / "materials"
    r = run([PY, str(RERUN / "tools/port_materials.py"), str(mat)])
    check(r.returncode == 0, "port_materials runs with no misses", r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    ok, d = same_tree(mat, RERUN / "materials"); check(ok, "materials regenerate identically", d)

    print("2  unchanged inputs")
    for rel, old in [("baseline/small/python", V / "13-evolution-benchmark/baseline/python"), ("baseline/grown/python", V / "14-scale/baseline/python"),
                     ("reference/C/small/python", V / "13-evolution-benchmark/reference/C/python"),
                     ("reference/C-alt/small/python", V / "14-scale/reference/C-alt/python")]:
        ok, d = same_tree(old, RERUN / rel); check(ok, f"{rel} identical to stage 1", d)
    for c, old in [("baseline.json", V / "13-evolution-benchmark/cases/baseline.json"), ("C.json", V / "13-evolution-benchmark/cases/C.json"),
                   ("grown.json", V / "14-scale/cases/grown.json")]:
        check(filecmp.cmp(old, RERUN / "cases" / c, shallow=False), f"cases/{c} identical to stage 1")
    for m in ("TASK-C.md", "README.P.small.md", "README.P.grown.md"):
        check(filecmp.cmp(V / "14-scale/materials" / m, RERUN / "materials" / m, shallow=False), f"materials/{m} identical to stage 1")

    print("3  no retired spelling in the rerun's Brass")
    hits, stray = [], []
    for t in TREES:
        stray += [str(f.relative_to(RERUN)) for f in (RERUN / t).rglob("*")
                  if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".brass", ".py", ".txt", ".json")]
        for f in (RERUN / t / "brass").rglob("*.brass"):
            for n, line in enumerate(f.read_text().split("\n"), 1):
                if OLD_FORM.search(line.split("#", 1)[0]):
                    hits.append(f"{f.relative_to(RERUN)}:{n}")
    check(not hits, "no `partial`, `private interface`, `has`, or `.keel` in the six trees", ", ".join(hits[:5]))
    check(not stray, "no file of another kind (a stray .keel, for one) in the six trees", ", ".join(stray[:5]))

    print("4  current check clean")
    for t in TREES:
        out = brass_check(RERUN / t / "brass", t.split("/")[-1])
        ok = "done        nothing else to run" in out and "rejection" not in out.split("done")[0]
        check(ok, f"brass check {t}", re.search(r"examples\s+(.*)", out).group(1) if re.search(r"examples\s+(.*)", out) else out[-160:])

    print("5  control: the old grown tree is rejected")
    out = brass_check(V / "14-scale/baseline/keel", "grown")
    counts = {k: len(re.findall(p, out)) for k, p in [("partial", r"`partial` on fn"), ("private interface", r"`private interface` is now"),
                                                     ("has", r"`where … has` is now"), ("bare where field", r"in a `where` names a field")]}
    check(all(counts.values()), "each old form is rejected by the current tool", json.dumps(counts))

    print("6  cases")
    for t, c, n in CASES:
        for lang in ("brass", "python"):
            r = run([PY, str(RERUN / "tools/evaluate.py"), str(RERUN / t / lang), lang, str(RERUN / "cases" / c)])
            last = (r.stdout.strip().splitlines() or [r.stderr[-120:]])[-1]
            check(f"{n} of {n} cases hold" in last, f"{t} {lang} {c}", last.strip())

    print("7  planted-wrong variants")
    r = run([PY, str(RERUN / "tools/variants.py")])
    last = r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:]
    check(r.returncode == 0 and last.startswith("22 of 22"), "every variant caught", last)

    print("8  agreement with stage 2's hand respelling")
    s2 = V / "14-scale/stage2/start/keel/src"
    mine = RERUN / "reference/C/grown/brass/src"
    diffs, missing = [], []
    for name in STAGE2_SAME:
        f, o = mine / f"{name}.brass", s2 / f"{name}.keel"
        if not f.exists() or not o.exists():
            missing.append(name)
            continue
        a = [re.sub(r"\.keel\b", ".brass", l) for l in o.read_text().split("\n")]
        if a != f.read_text().split("\n"):
            diffs.append(name)
    check(not missing, f"all {len(STAGE2_SAME)} comparable modules present on both sides", ", ".join(missing))
    check(not diffs, f"each of the {len(STAGE2_SAME)} matches line for line", f"{len(diffs)} differ: {diffs[:5]}")

    print("9  ported tools: the diff from the source is the approved one")
    for new, old in [("tools/evaluate.py", V / "14-scale/tools/evaluate.py"), ("tools/build.py", V / "14-scale/tools/build.py"),
                     ("tools/launch.sh", V / "13-evolution-benchmark/tools/launch.sh"), ("tools/evaluate_d.py", V / "14-scale/stage2/tools/evaluate.py"),
                     ("tools/variants_d.py", V / "14-scale/stage2/tools/variants_d.py"), ("tools/build_d.py", V / "25-stage2/tools/build.py")]:
        d = run(["diff", str(old), str(RERUN / new)]).stdout
        h = hashlib.sha256(d.encode()).hexdigest()[:16]
        ok = APPROVED_DIFF.get(new) == h
        check(ok, f"{new} diff hash {h}", "approved" if ok else f"not the approved diff ({APPROVED_DIFF.get(new)}); review every line below, then approve the new hash")
        if not ok:
            for l in d.split("\n"):
                if l[:1] in "<>":
                    print("       " + l[:170])

    print("10 built sessions")
    build_dir = Path(tempfile.mkdtemp(prefix="rerun-"))
    specs = [f"{s}-{a}1:{s}:{a}" for s in ("small", "grown") for a in ("P", "K", "KC")]
    r = run([PY, str(RERUN / "tools/build.py"), str(build_dir / "C"), "--cap", "150", "--tag", "audit/C", *specs])
    check(r.returncode == 0, "build.py builds all six task C sessions", r.stderr[-200:])
    r = run([PY, str(RERUN / "tools/build_d.py"), str(build_dir / "D"), "--cap", "150", "--tag", "audit/D", "P1:P", "KC1:KC"])
    check(r.returncode == 0, "build_d.py builds both task D sessions", r.stderr[-200:])
    for task, label in [("C", s.split(":")[0]) for s in specs] + [("D", "P1"), ("D", "KC1")]:
        text = (build_dir / task / label / "prompt.md").read_text().replace(str(build_dir), "")
        check(not re.search(r"(?i)keel|partial fn|private interface", text), f"{task}/{label} prompt has no old name or form")
        check(text.startswith(f"Session audit/{task}/{label}. "), f"{task}/{label} prompt opens with its session tag")
    for task, label in [("C", "small-KC1"), ("C", "grown-KC1"), ("D", "KC1")]:
        r = run([str(build_dir / task / label / "project/bin/brass"), "check"], {"BRASS_NO_LOG": "1"})
        check("done        nothing else to run" in r.stdout, f"{task}/{label} project's own bin/brass check is clean", r.stdout[-120:] if "done" not in r.stdout else "")
    shutil.rmtree(build_dir)

    print("11 the frozen tool")
    for f in ("brass.py", "brasseval.py"):
        same = (RERUN / "tools/brass-lean8" / f).read_bytes() == (LIVE.parent / ("brass" if f == "brass.py" else f)).read_bytes()
        check(same, f"brass-lean8/{f} is byte-identical to validation/proxy/bin", "" if same else "the live tool moved on; the README must say which the run used")

    print("12 task D")
    ok, d = same_tree(V / "25-stage2/start", RERUN / "D/start"); check(ok, "D/start identical to the Stage 2 trial's start trees", d)
    for c in ("D.json", "baseline.json", "C.json", "grown.json"):
        check(filecmp.cmp(V / "14-scale/stage2/cases" / c, RERUN / "D/cases" / c, shallow=False), f"D/cases/{c} identical to stage 2's")
    check(filecmp.cmp(V / "14-scale/stage2/TASK.md", RERUN / "D/materials/TASK-D.md", shallow=False), "D task text is stage 2's TASK.md (with the D33 rule)")
    for m in ("README.P.md", "README.KC.md", "BRASS.lean8.md", "OPENING.lean8.md", "host-contract.txt", "MAP.md"):
        check(filecmp.cmp(V / "29-range-proof/materials" / m, RERUN / "D/materials" / m, shallow=False), f"D/materials/{m} identical to trial 29's")
    for m in ("BRASS-REFERENCE.KC.md", "BRASS-REFERENCE-FULL.KC.md"):
        check(filecmp.cmp(RERUN / "materials" / m, RERUN / "D/materials" / m, shallow=False), f"D/materials/{m} identical to task C's KC edition")
    ok, d = same_tree(V / "14-scale/stage2/reference/python", RERUN / "D/reference/python"); check(ok, "D/reference/python identical to stage 2's", d)
    src2, mine = V / "14-scale/stage2/reference/keel", RERUN / "D/reference/brass"
    diffs = []
    for f in sorted(src2.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        rel = str(f.relative_to(src2))
        g = mine / (rel[:-5] + ".brass" if rel.endswith(".keel") else rel)
        if not g.exists() or re.sub(r"\.keel\b", ".brass", f.read_text()) != g.read_text():
            diffs.append(rel)
    check(not diffs, "D/reference/brass is stage 2's reference under .brass names, nothing else changed", ", ".join(diffs[:5]))
    for lang in ("brass", "python"):
        for c, n in (("D.json", 81), ("baseline.json", 82), ("C.json", 122), ("grown.json", 112)):
            r = run([PY, str(RERUN / "tools/evaluate_d.py"), str(RERUN / "D/reference" / lang), lang, str(RERUN / "D/cases" / c)])
            last = (r.stdout.strip().splitlines() or [r.stderr[-120:]])[-1]
            check(f"{n} of {n} cases hold" in last, f"D reference {lang} {c}", last.strip())
    r = run([PY, str(RERUN / "tools/variants_d.py")])
    last = r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:]
    check(r.returncode == 0 and last.startswith("variants caught: 14 of 14"), "task D planted variants", last)
    shutil.rmtree(tmp)

    if "--freeze" in argv:
        print("\nFreeze table")
        items = [("live stand-in", V / "proxy/bin/brass"), ("live evaluator", V / "proxy/bin/brasseval.py"),
                 ("case evaluator", RERUN / "tools/evaluate.py"), ("session builder", RERUN / "tools/build.py"),
                 ("launcher", RERUN / "tools/launch.sh"), ("runner", RERUN / "tools/run.py"), ("variants", RERUN / "tools/variants.py"),
                 ("respeller", RERUN / "tools/respell.py"), ("material port", RERUN / "tools/port_materials.py"),
                 ("frozen tool lean 8", RERUN / "tools/brass-lean8"), ("task d builder", RERUN / "tools/build_d.py"),
                 ("task d evaluator", RERUN / "tools/evaluate_d.py"), ("task d variants", RERUN / "tools/variants_d.py"),
                 ("cases", RERUN / "cases"), ("materials", RERUN / "materials"), ("baselines", RERUN / "baseline"),
                 ("references", RERUN / "reference"), ("task d inputs", RERUN / "D")]
        for what, p in items:
            print(f"| {what} | `{p.relative_to(PUB)}` | `{digest(p)}` |")

    print(f"\n{'PASS' if not failures else 'FAIL'}: {len(failures)} failures" + (f": {failures}" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
