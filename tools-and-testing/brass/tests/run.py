"""The brass stand-in's suite. Run: python3 tests/run.py

Fixture tree under tests/fixtures (park), copied to a temp dir per section. Covers: `info`'s use-finder (aliases,
refinements, constructors, strings and comments, scopes, `--in`, `--at`, unknown names); `check` level 1 with planted
faults and the program summary; `example` lines (C15) and `any`/`all` (C16); scenarios against a scripted host; guided
mode; `changes` and `propagate` against a baseline; lean mode 1 to 3 (one-call check, declarations-only and bare show,
example counting, effect order on six shapes, host contract, `apply` all-or-nothing, dry run, new file); and the
evaluator's regression examples in park/evalcheck.brass. Every section states what must and must not appear."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
BRASS = HERE.parent / "bin" / "brass"

def info(root, target):
    env = dict(os.environ, BRASS_PROJECT=str(root), BRASS_INFO_ONLY="1")
    return subprocess.run([sys.executable, str(BRASS), "info", target], env=env, capture_output=True, text=True).stdout

def main():
    tmp = Path(tempfile.mkdtemp()); shutil.copytree(HERE / "fixtures", tmp / "p")
    root = tmp / "p"
    fails = []
    n = [0]
    def expect(target, must, must_not=()):
        n[0] += 1
        out = info(root, target)
        for m in must:
            if m not in out: fails.append(f"{target}: missing {m!r}\n{out}")
        for m in must_not:
            if m in out: fails.append(f"{target}: unexpected {m!r}\n{out}")
    # alias-qualified use across modules, as let type and access parameter type
    expect("staff.Staff", ["desk.open", "let type", "desk.Store.load", "return type", "desk.Store.save", "parameter type"])
    # refinement base in the same module, body test through an alias
    expect("staff.Staff", ["staff.OnShift", "refinement base"])
    expect("staff.OnShift", ["desk.open", "body test", "if s is staff.OnShift"])
    # a call through an alias
    expect("staff.clock_in", ["desk.open", "call", "store.save(staff.clock_in(s))"])
    # a comment and a string literal naming a declaration do not count
    expect("staff.clock_in", [], must_not=["desk.note", "already on shift"])
    expect("staff.OnShift", [], must_not=["desk.note"])
    # a private declaration is marked
    expect("staff.badge_of", ["none in src/park/"])
    expect("ids.BadgeId", ["staff.badge_of", "(private)"])
    # a local named like an access operation does not count as a use
    expect("desk.Store.load", ["desk.open", "call", "store.load(id)"], must_not=["desk.note"])
    expect("desk.Store", ["desk.open", "parameter type", "store.load(id)"], must_not=["desk.note"])
    # constructors and machine states
    expect("staff.Shift", ["staff.Staff", "record field type", "staff.OnShift", "refinement condition", "staff.clock_in", "constructor"])
    # coverage line and short unknown
    expect("staff.Staff", ["searched     src/park/*.brass (4 modules"])
    expect("staff.Staf", ["unknown     staff.Staf", "nearest: staff.Staff"])
    # a binding name is not a use, but its initializer is
    expect("desk.helper", ["desk.probe", "call", "let helper: Int = helper()"], must_not=["unclassified"])
    # uses before a binding, in the other branch, and after a loop count; the hidden ones do not
    out = info(root, "desk.helper")
    for line in ("let a: Int = helper()", "else helper()", "helper()                                    # not hidden after the loop".split("#")[0].strip()):
        if line not in out: fails.append(f"desk.helper: missing {line!r}\n{out}")
    for line in ("let helper: Int = 2", "a = a + helper"):
        if line in out: fails.append(f"desk.helper: unexpected {line!r}\n{out}")
    if "desk.scopes" not in out or "5 lines" not in out: fails.append(f"desk.helper: expected 5 use lines, 3 from desk.scopes\n{out}")
    # one level of expansion: a body site shows its enclosing declaration and path; a signature site its contracts
    expect("staff.OnShift", ["in       fn open(store: Store, id: ids.BadgeId) -> Outcome<Done>", "on path  no enclosing test"])
    expect("staff.Staff", ["before s.shift in {Shift.Off}"])
    # grouped by relationship; --in prints every line in one module
    expect("staff.Staff", ["parameter type", "desk.Store.save", "refinement base", "staff.OnShift"])
    out_in = subprocess.run([sys.executable, str(BRASS), "info", "desk.Store", "--in", "desk"], env=dict(os.environ, BRASS_PROJECT=str(root), BRASS_INFO_ONLY="1"), capture_output=True, text=True).stdout
    if "source omitted" in out_in or "store.load(id)" not in out_in or ", in desk" not in out_in: fails.append(f"--in: {out_in}")
    # a missing declaration in a scanned module, and a missing module, are both reported
    f = root / "src/park/desk.brass"; f.write_text(f.read_text().replace("import park.staff as staff\n", "import park.staff as staff\nimport park.missing as missing\n").replace("  fn helper() -> Int\n", "  fn helper() -> Int\n  fn gone(x: staff.Nope) -> missing.Nope\n"))
    expect("desk.helper", ["1 import unresolved: desk: park.missing", "2 qualified names unresolved: desk: staff.Nope  desk: missing.Nope"])
    # an edited file is seen on the next call
    f = root / "src/park/desk.brass"; f.write_text(f.read_text().replace("  fn note(n: Int) -> Int\n", "  fn note(n: Int) -> Int\n  fn again(s: staff.OnShift) -> Int\n"))
    expect("staff.OnShift", ["desk.again", "parameter type"])
    # C11: `not` is a keyword, never a name or a use; `?` does not disturb call recognition
    expect("desk.quiet", ["direct uses  none in src/park/"], must_not=["unresolved: desk: not"])
    expect("desk.helper", ["desk.quiet", "call", "not helper() == n"])
    expect("desk.Store.load", ["store.load(id)?"])
    # C13: `is` narrows for `--at`; a state test with `in {…}` is not taken as a type
    f = root / "src/park/desk.brass"; f.write_text(f.read_text().replace("  fn quiet(n: Int) -> Bool\n", "  fn quiet(n: Int) -> Bool\n  fn gate(s: staff.Staff) -> Int\n")
        + "  fn gate(s) =\n    if s is staff.OnShift and s.shift in {staff.Shift.On} then\n      1\n    else 0\n")
    at = str(f.read_text().split("\n").index("      1") + 1)
    out_at = subprocess.run([sys.executable, str(BRASS), "info", "desk.gate", "--at", at], env=dict(os.environ, BRASS_PROJECT=str(root)), capture_output=True, text=True).stdout
    n[0] += 1
    if "narrowed from staff.Staff" not in out_at or "{staff.Shift.On}" in out_at.split("narrowed")[0].split("bindings")[-1]: fails.append(f"is narrowing: {out_at}")
    expect("staff.OnShift", ["desk.gate", "body test", "if s is staff.OnShift"])
    # C15: `example` lines run; a wrong one fails, a right one holds
    f = root / "src/park/desk.brass"; f.write_text(f.read_text().replace("  fn note(n: Int) -> Int\n", "  fn note(n: Int) -> Int\n    example note(1) == 2\n    example note(1) == 3\n", 1))
    out_ex = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=dict(os.environ, BRASS_PROJECT=str(root)), capture_output=True, text=True).stdout
    n[0] += 1
    if "11 found, 10 hold, 1 fail" not in out_ex or "FAILS    desk.note" not in out_ex: fails.append(f"examples: {out_ex}")
    # C16: `any` and `all`, empty arrays, short-circuit, narrowing inside the predicate
    (root / "src/park/q.brass").write_text("""# park/q.brass
module park.q
interface
  type Cert = { badge: Int, valid: Bool }
  type Valid = Cert where it.valid == true
  fn holds(certs: Array<Cert> where it.length in 0 to 10, badge: Int) -> Bool
    example holds([{ badge: 1, valid: false }, { badge: 1, valid: true }], 1) == true
    example holds([{ badge: 1, valid: false }], 1) == false
    example holds([], 1) == false
  fn small(xs: Array<Int> where it.length in 0 to 10) -> Bool
    example small([]) == true
    example small([1, 20]) == false
body
  fn holds(certs, badge) = any c in certs where c is Valid and c.badge == badge
  fn small(xs) = all x in xs where x < 10
""")
    out_q = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=dict(os.environ, BRASS_PROJECT=str(root)), capture_output=True, text=True).stdout
    n[0] += 1
    if "16 found, 15 hold, 1 fail" not in out_q: fails.append(f"any/all: {out_q}")
    out_at = subprocess.run([sys.executable, str(BRASS), "info", "q.holds", "--at", "14"], env=dict(os.environ, BRASS_PROJECT=str(root)), capture_output=True, text=True).stdout
    n[0] += 1
    for want in ("c: Cert", "false when certs is empty", "length at most 10", "c: Valid", "none allowed"):
        if want not in out_at: fails.append(f"any --at: missing {want!r}\n{out_at}")
    (root / "src/park/q.brass").unlink()
    # audit 2026-10-03: a record refinement whose condition holds a set; `#` inside a text literal; 64-bit overflow;
    # a chained comparison and mixed and/or are faults, not Python's reading
    (root / "src/park/a.brass").write_text("""# park/a.brass
module park.a
import park.staff as staff
import std.text as text
interface
  type Lit = { id: Int, shift: staff.Shift } where it.shift in {staff.Shift.On}
  fn is_lit(l: Lit) -> Bool
    example is_lit({ id: 1, shift: staff.Shift.Off }) == false
  fn tag(t: Text) -> Text
    example tag("a") == "a#"
  fn big(n: Int) -> Int
    example big(9223372036854775807) == 0
  fn chain(a: Int, b: Int, c: Int) -> Bool
    example chain(3, 2, 1) == false
  fn mixed(a: Bool, b: Bool, c: Bool) -> Bool
    example mixed(true, false, false) == false
  type Shiftly = { id: Int, shift: staff.Shift, since: Int when it.shift in {staff.Shift.On} }
  fn any_shiftly(s: Shiftly) -> Bool
    example any_shiftly({ id: 1, shift: staff.Shift.Off }) == true
  fn tier(n: Int) -> Int
    example tier(600000) == 3
  const cap: Int = 3
  fn under(n: Int) -> Bool
    example under(2) == true
    example under(3) == false
  machine Tri
    states  A, B, C
    initial A
    A enters B
    B enters C | A
  type Rec = { s: Tri, x: Int when it.s in {Tri.B, Tri.C} }
  fn enter_x(r: Rec) -> Int
    example enter_x({ s: Tri.A }) == 1
  fn enter_bare(r: Rec) -> Int
    example enter_bare({ s: Tri.A }) == 0
  fn stay_x(r: Rec) -> Int
    example stay_x({ s: Tri.B, x: 7 }) == 7
  fn leave_x(r: Rec) -> Int
    example leave_x({ s: Tri.B, x: 7 }) == 0
  fn leave_named(r: Rec) -> Int
    example leave_named({ s: Tri.B, x: 7 }) == 0
  fn outside(r: Rec) -> Int
    example outside({ s: Tri.A }) == 0
  fn ends() -> Int
    example ends() == 6
  fn empty_range() -> Int
    example empty_range() == 0
  fn nested() -> Int
    example nested() == 12
  type Other = { s: Tri, note: Text }
  fn other_moves(o: Other) -> Text
    example other_moves({ s: Tri.A, note: "n" }) == "n"
  fn bad_ctrl(r: Rec) -> Int
    example bad_ctrl({ s: Tri.A }) == 0
  type Assign = { who: staff.Staff, n: Int } where it.who.shift in {staff.Shift.On}
  fn assigned(a: Assign) -> Int
    example assigned({ who: { badge: "b", shift: staff.Shift.On }, n: 4 }) == 4
  fn label(n: Int) -> Text
    example label(-12) == "p-12"
body
  fn is_lit(l) = l is Lit
  fn tag(t) = t ++ "#"
  fn big(n) = n + 1
  fn chain(a, b, c) = a < b < c
  fn mixed(a, b, c) = a or b and c
  fn any_shiftly(s) = s is Shiftly
  fn tier(n) = if n <= 50000 then 1 else if n <= 500000 then 2 else 3
  fn under(n) = n < cap
  fn enter_x(r) =
    let n: Rec = r with { s enters Tri.B, x: 1 }
    n.x
  fn enter_bare(r) =
    let n: Rec = r with { s enters Tri.B }
    0
  fn stay_x(r) =
    let n: Rec = r with { s enters Tri.C }
    n.x
  fn leave_x(r) =
    let n: Rec = r with { s enters Tri.A }
    n.x
  fn leave_named(r) =
    let n: Rec = r with { s enters Tri.A, x: 1 }
    0
  fn outside(r) =
    let n: Rec = r with { x: 2 }
    0
  fn ends() =
    let total: Int = 0
    for i in 1 to 3
      total = total + i
    total
  fn empty_range() =
    let total: Int = 0
    for i in 3 to 1
      total = total + 1
    total
  fn nested() =
    let count: Int = 0
    for i in 1 to 3
      for j in 1 to 10
        if j > 4 then break
        count = count + 1
    count
  fn other_moves(o) =
    let p: Other = o with { s enters Tri.B }
    p.note
  fn bad_ctrl(r) =
    let n: Rec = r with { s: 1 }
    0
  fn assigned(a) = a.n
  fn label(n) = "p" ++ text.of(n)
""")
    out_a = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=dict(os.environ, BRASS_PROJECT=str(root)), capture_output=True, text=True).stdout
    n[0] += 1
    for want in ("holds    a.is_lit", "holds    a.tag", "integer overflow", "a chained comparison", "mixed at one level",
                 "holds    a.any_shiftly", "holds    a.tier", "holds    a.under",
                 "holds    a.enter_x", "requires x", "holds    a.stay_x", "no field x", "this update leaves", "x exists only when s in {B, C}",
                 "holds    a.ends", "holds    a.empty_range", "holds    a.nested",
                 "holds    a.other_moves", "must hold a state of Tri", "holds    a.assigned", "holds    a.label"):
        if want not in out_a: fails.append(f"audit examples: missing {want!r}\n{out_a}")
    (root / "src/park/a.brass").unlink()
    # level 1, structure: a clean tree passes; each planted fault is rejected on its line, with a fix
    def check(root_):
        return subprocess.run([sys.executable, str(BRASS), "check"], env=dict(os.environ, BRASS_PROJECT=str(root_)), capture_output=True, text=True).stdout
    root3 = tmp / "structure"; shutil.copytree(HERE / "fixtures", root3)
    n[0] += 1
    if "no rejections at this level" not in check(root3): fails.append(f"check, clean: {check(root3)}")
    # a refinement of an access is still an access: its grant and its calls resolve
    fp = root3 / "src/park/desk.brass"; txt = fp.read_text()
    fp.write_text(txt.replace("  fn open(store: Store,", "  type Narrow = Store where it.budget_ms in 0 to 10\n  fn open(store: Narrow,", 1))
    n[0] += 1
    if "no rejections at this level" not in check(root3): fails.append(f"check, narrowed access: {check(root3)}")
    fp.write_text(txt)
    # C28: a declaration spans lines while a bracket is open; later lines holding a record are not parameters
    fp.write_text(txt.replace("  fn note(n: Int) -> Int\n", "  fn note(n: Int,\n          m: Int) -> Int\n    after result == { a: n, b: m }\n", 1)
                  .replace("  fn note(n) =", "  fn note(n, m) =", 1)
                  .replace("    allow save(s: staff.Staff) -> Outcome<Done>\n", "    allow save(s: staff.Staff,\n               n: Int) -> Outcome<Done>\n", 1)
                  .replace("store.save(staff.clock_in(s))", "store.save(staff.clock_in(s), 1)", 1))
    n[0] += 1
    if "no rejections at this level" not in check(root3): fails.append(f"check, multi-line declarations: {check(root3)}")
    fp.write_text(txt)
    faults = [
        ("src/park/desk.brass", "store.save(staff.clock_in(s))", "store.save(staff.clock_in(s, s))", "takes 1 argument (s); 2 given"),
        ("src/park/desk.brass", "store.save(staff.clock_in(s))", "store.nope(staff.clock_in(s))", "Store declares no operation nope"),
        ("src/park/staff.brass", "\nprivate\n", "\nprivate interface\n", "`private interface` is now `private` (C31)"),
        ("src/park/desk.brass", "  fn helper() -> Int\n", "  data cap: Int = 5\n  fn helper() -> Int\n", "`data cap` is now `const cap` (C32)"),
        ("src/park/staff.brass", "Staff where it.shift in {Shift.On}", "Staff where shift in {Shift.On}", "`shift` in a `where` names a field of the value; write `it.shift`"),
        ("src/park/staff.brass", "shift: Shift }", "shift: Shift }\n    where it.shift in {Shift.On} has since: Int", "`where … has` is now a field with `when` (C34)"),
        ("src/park/staff.brass", "shift: Shift }", "shift: Shift, since: Int where it > 0 when it.shift in {Shift.On} }", "has a presence condition and an unnamed refined type"),
        ("src/park/staff.brass", "shift: Shift }", "shift: Shift, a: Int when it.shift in {Shift.On}, b: Int when it.a in {Shift.On} }", "`a` is itself conditional"),
        ("src/park/staff.brass", "shift: Shift }", "shift: Shift, a: Int when it.shift in {On} }", "names a state without its machine"),
        ("src/park/staff.brass", "Staff where it.shift in {Shift.On}", "Staff where it.shift in {Shift.On} and badge != badge", "`badge` in a `where` names a field of the value; write `it.badge`"),
        ("src/park/desk.brass", "  fn quiet(n) = not (n > 0) and not helper() == n", "  fn quiet(n) = n < helper() < 3", "a chained comparison"),
        ("src/park/desk.brass", "  fn quiet(n) = not (n > 0) and not helper() == n", "  fn quiet(n) = n > 0 or n < 0 and helper() == n", "`and` and `or` mixed at one level"),
        ("src/park/desk.brass", "  fn helper() = 1\n", "  fn helper() = 1\n  fn stray(x) = x\n", "fn stray has a body and no declaration"),
        ("src/park/desk.brass", "  fn helper() -> Int\n", "  fn helper() -> Int\n  fn lonely(x: Int) -> Int\n", "fn lonely is declared and has no body"),
        ("src/park/desk.brass", "  fn note(n) =", "  fn note(m) =", "body names (m); its declaration has (n)"),
        ("src/park/desk.brass", "  fn open(", "  partial fn open(", "`partial` on fn open: Brass has no `partial` (C25)"),
        ("src/park/desk.brass", "    let load: Int = n + 1", "    let load = n + 1", "let load has no type"),
        ("src/park/desk.brass", "  fn helper() = 1", "  fn helper() = @@one", "hole @@one is unfilled"),
        ("src/park/desk.brass", "    helper\n", "    return helper\n", "`return` is not a Brass form"),
        ("src/park/desk.brass", "  fn helper() -> Int\n", "  data t: Int from \"t.json\"\n  fn helper() -> Int\n", "`from` is not a Brass form"),
        ("src/park/desk.brass", "    let load: Int = n + 1", "    let load: Int = store.load(n)?", "`?` in fn note, which returns Int, not Outcome<…>"),
        ("src/system.brass", "grants park.desk.open: store = Store", "grants park.desk.open: none", "access parameter store is not granted"),
        ("src/system.brass", "grants park.desk.open:", "grants park.desk.opened:", "grants park.desk.opened: no such function"),
    ]
    for f, old_, new_, want in faults:
        shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
        fp = root3 / f; txt = fp.read_text()
        if old_ not in txt:
            fails.append(f"check fault setup: {old_!r} not in {f}"); continue
        fp.write_text(txt.replace(old_, new_, 1))
        out_c = check(root3); n[0] += 1
        if want not in out_c or "fix:" not in out_c: fails.append(f"check fault {want!r}:\n{out_c}")
    # a clean check ends with the program summary: the entry point, its refusals in check order, its calls
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    out_s = check(root3); n[0] += 1
    for want in ("summary", "desk.open", "holds store", "call     store.load(id)", "refuse   Conflict", "when s is staff.OnShift", "store.save(staff.clock_in(s))   its result is the branch's value"):
        if want not in out_s: fails.append(f"check summary: missing {want!r}\n{out_s}")
    # usage under the trial gate lists only allowed verbs
    out_u = subprocess.run([sys.executable, str(BRASS)], env=dict(os.environ, BRASS_PROJECT=str(root3), BRASS_INFO_ONLY="1"), capture_output=True, text=True).stdout
    n[0] += 1
    if "--effects" in out_u or "brass check" in out_u or "brass info <module>.<name>" not in out_u or "Several targets" not in out_u: fails.append(f"usage gate: {out_u}")
    # audit cases: a removed word is a legal name; a one-line if/else refusal keeps its condition; a helper's
    # access is found by type; `is Ok` and `?` evaluate; a one-line body is read after its `=`
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    (root3 / "src/park/q.brass").write_text("""# park/q.brass
module park.q
import park.staff as staff
interface
  access Store
    allow load(id: ids.BadgeId) -> Outcome<Int>
    allow save(v: Int) -> Outcome<Done>
  fn pick(o: Outcome<Int>, max: Int) -> Int
    example pick(Ok(3), 9) == 1
    example pick(Err(FailureCode.Other, "x"), 9) == 9
  fn go(store: Store, id: ids.BadgeId, n: Int) -> Outcome<Done>
private
  fn helper(s: Store, v: Int) -> Outcome<Done>
body
  fn pick(o, max) = if o is Ok then 1 else max
  fn go(store, id, n) =
    let v: Int = if n > 5 then store.load(id)? else Err(FailureCode.Conflict, "small")
    if v > 0 then
      helper(store, v)
    else
      Err(FailureCode.InvalidInput, "not positive")
  fn helper(s, v) = s.save(v)
""")
    (root3 / "src/park/q.brass").write_text((root3 / "src/park/q.brass").read_text().replace("import park.staff as staff\n", "import park.ids as ids\n"))
    sysf = root3 / "src/system.brass"; sysf.write_text(sysf.read_text().replace("  grants park.desk.open: store = Store\n", "  grants park.desk.open: store = Store\n  grants park.q.go: store = Store\n"))
    out_q = check(root3); n[0] += 1
    for want in ("no rejections", 'refuse   Conflict       "small"   when not n > 5', 'refuse   InvalidInput   "not positive"   when not v > 0',
                 "via      q.helper", "s.save(v)   its result is the branch's value"):
        if want not in out_q: fails.append(f"audit summary: missing {want!r}\n{out_q}")
    out_e = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=dict(os.environ, BRASS_PROJECT=str(root3)), capture_output=True, text=True).stdout
    n[0] += 1
    if "11 found, 11 hold" not in out_e: fails.append(f"is Ok examples: {out_e}")
    # review feedback: every action carries its enclosing condition; inline and block forms report alike;
    # moving an effect under a condition changes its guard; a stored error is reported, a reassigned seed is not
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    (root3 / "src/park/g.brass").write_text("""# park/g.brass
module park.g
interface
  access Store
    allow save(v: Int) -> Outcome<Done>
  fn a(store: Store, ok: Bool, v: Int) -> Outcome<Done>
  fn b(store: Store, ok: Bool, v: Int) -> Outcome<Done>
  fn c(store: Store, v: Int) -> Outcome<Done>
  fn d(store: Store, v: Int) -> Outcome<Done>
body
  fn a(store, ok, v) =
    if ok then
      store.save(v)
    else Err(FailureCode.Unauthorized, "denied")
  fn b(store, ok, v) =
    if ok then store.save(v) else Err(FailureCode.Unauthorized, "denied")
  fn c(store, v) =
    let outcome: Outcome<Done> = Err(FailureCode.Conflict, "blocked")
    outcome
  fn d(store, v) =
    let last: Outcome<Done> = Err(FailureCode.Unavailable, "not tried")
    for attempt in 1 to 3
      last = store.save(v)
      if last is Ok then break
    last
""")
    sysf = root3 / "src/system.brass"
    sysf.write_text(sysf.read_text() + "".join(f"  grants park.g.{f}: store = Store\n" for f in "abcd"))
    out_g = check(root3); n[0] += 1
    def section(name):
        part = out_g.split(f"g.{name} ", 1)[1] if f"g.{name} " in out_g else ""
        return part.split("\ng.", 1)[0]
    norm = lambda sec: [re.sub(r"^\s*\d+\s+", "", x.strip()) for x in sec.splitlines() if re.match(r"\s+\d+\s", x)]
    if norm(section("a")) != norm(section("b")): fails.append(f"inline and block forms differ:\n{section('a')}\n--\n{section('b')}")
    if "within ok" not in section("a") or "store.save(v)   its result is the branch's value, failure included" not in section("a"): fails.append(f"guard on action: {section('a')}")
    if "stores   Conflict" not in section("c") or "refuse" in section("c"): fails.append(f"stored error: {section('c')}")
    if "stores" in section("d") or "refuse" in section("d") or "repeated: for … in 1 to 3" not in section("d"): fails.append(f"seeded retry: {section('d')}")
    # the evaluator: a handled error, and an unselected branch holding a failing expression
    (root3 / "src/park/e.brass").write_text("""# park/e.brass
module park.e
interface
  fn handled(o: Outcome<Int>) -> Int
    example handled(Err(FailureCode.Other, "x")) == 0
    example handled(Ok(4)) == 4
  fn lazy(flag: Bool, d: Int) -> Int
    example lazy(true, 0) == 1
    example lazy(false, 2) == 5
body
  fn handled(o) = if o is Err then 0 else 4
  fn lazy(flag, d) = if flag then 1 else 10 / d
""")
    out_e2 = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=dict(os.environ, BRASS_PROJECT=str(root3)), capture_output=True, text=True).stdout
    n[0] += 1
    if "13 found, 13 hold" not in out_e2: fails.append(f"evaluator cases: {out_e2}")
    # scenarios: a scripted host; a right program holds, a planted fault fails on the step that differs
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    prog = """# park/s.brass
module park.s
import park.ids as ids
interface
  access Store
    allow load(id: ids.BadgeId) -> Outcome<Int>
    allow save(v: Int) -> Outcome<Done>
    allow audit(v: Int) -> Outcome<Done>
  fn go(store: Store, id: ids.BadgeId, ok: Bool) -> Outcome<Int>
body
  fn go(store, id, ok) =
    if not ok then Err(FailureCode.Unauthorized, "no")
    else
      let last: Outcome<Int> = Err(FailureCode.Unavailable, "not tried")
      for attempt in 1 to 3
        last = store.load(id)
        if last is Ok then break
      if last is Err then Err(FailureCode.Unavailable, "gave up")
      else
        let v: Int = last?
        store.save(v)?
        store.audit(v)?
        Ok(v)
"""
    (root3 / "src/park/s.brass").write_text(prog)
    sysf = root3 / "src/system.brass"; sysf.write_text(sysf.read_text() + "  grants park.s.go: store = Store\n")
    scen = root3 / "scenarios"; scen.mkdir()
    import json
    (scen / "retry.json").write_text(json.dumps({"entry": "s.go", "args": {"id": '"b"', "ok": "true"},
        "replies": {"store.load": ['Err(FailureCode.Unavailable, "x")', "Ok(7)"], "store.save": ["Ok(Done)"], "store.audit": ["Ok(Done)"]},
        "expect": {"result": "Ok(7)", "trace": ['store.load("b")', 'store.load("b")', "store.save(7)", "store.audit(7)"]}}))
    (scen / "refused.json").write_text(json.dumps({"entry": "s.go", "args": {"id": '"b"', "ok": "false"}, "replies": {},
        "expect": {"result": "Err(Unauthorized)", "trace": []}}))
    (scen / "save_fails.json").write_text(json.dumps({"entry": "s.go", "args": {"id": '"b"', "ok": "true"},
        "replies": {"store.load": ["Ok(7)"], "store.save": ['Err(FailureCode.Conflict, "busy")']},
        "expect": {"result": "Err(Conflict)", "trace": ["store.load", "store.save"]}}))
    def scenarios(root_):
        return subprocess.run([sys.executable, str(BRASS), "check", "--scenarios"], env=dict(os.environ, BRASS_PROJECT=str(root_)), capture_output=True, text=True).stdout
    out_sc = scenarios(root3); n[0] += 1
    if "3 scenarios, 3 hold, 0 fail" not in out_sc: fails.append(f"scenarios on a right program: {out_sc}")
    # planted: audit before save -> the trace differs at step 3; retry only once -> Unavailable where Ok(7) was expected
    (root3 / "src/park/s.brass").write_text(prog.replace("        store.save(v)?\n        store.audit(v)?\n", "        store.audit(v)?\n        store.save(v)?\n"))
    out_p = scenarios(root3); n[0] += 1
    if "FAILS    retry" not in out_p or "step 3: expected store.save(7); got store.audit(7)" not in out_p: fails.append(f"planted order fault: {out_p}")
    (root3 / "src/park/s.brass").write_text(prog.replace("for attempt in 1 to 3", "for attempt in 1 to 1"))
    out_p2 = scenarios(root3); n[0] += 1
    if "result   expected Ok(7); got Err(FailureCode.Unavailable)" not in out_p2: fails.append(f"planted retry fault: {out_p2}")
    # guided mode: four commands only; a bare name resolves; every answer ends with a next step; check is terminal
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    def guided(*a):
        return subprocess.run([sys.executable, str(BRASS), *a], env=dict(os.environ, BRASS_PROJECT=str(root3), BRASS_GUIDED="1", BRASS_BASELINE=str(HERE / "fixtures")), capture_output=True, text=True).stdout
    n[0] += 1
    u = guided()
    if "brass info <Name>" not in u or "--effects" in u or "brass run" in u: fails.append(f"guided usage: {u}")
    n[0] += 1
    i = guided("info", "OnShift")
    if "declaration type OnShift" not in i or "next        " not in i or "brass propagate" not in i or "--in" in i: fails.append(f"guided info: {i}")
    n[0] += 1
    c = guided("check")
    if "✓ names and imports" not in c or "done        nothing else to run" not in c or "summary" in c: fails.append(f"guided check: {c}")
    n[0] += 1
    if "brass info <Name>" not in guided("info", "--holds"): fails.append("guided mode accepted a flag")
    # a module missing its `body` section is a rejection, not a crash
    shutil.rmtree(root3); shutil.copytree(HERE / "fixtures", root3)
    (root3 / "src/park/half.brass").write_text("module park.half\ninterface\n  fn f() -> Int\n")
    out_b = check(root3); n[0] += 1
    if "half.brass:1" not in out_b or "no `body` section" not in out_b: fails.append(f"check, broken module: {out_b}")
    # the change report, against a pristine copy
    base = tmp / "base"; shutil.copytree(HERE / "fixtures", base)
    root2 = tmp / "edit"; shutil.copytree(HERE / "fixtures", root2)
    def changes(r):
        env = dict(os.environ, BRASS_PROJECT=str(r), BRASS_INFO_ONLY="1", BRASS_BASELINE=str(base))
        return subprocess.run([sys.executable, str(BRASS), "changes"], env=env, capture_output=True, text=True).stdout
    def cexpect(must, must_not=()):
        n[0] += 1
        out = changes(root2)
        for m in must:
            if m not in out: fails.append(f"changes: missing {m!r}\n{out}")
        for m in must_not:
            if m in out: fails.append(f"changes: unexpected {m!r}\n{out}")
    cexpect(["changes     none against $BRASS_BASELINE"])
    st = root2 / "src/park/staff.brass"; s0 = st.read_text()
    st.write_text(s0.replace("fn clock_in(s: Staff) -> OnShift", "fn clock_in(s: Staff, by: ids.BadgeId) -> OnShift"))
    cexpect(["staff.clock_in", "parameter added: by: ids.BadgeId", "staff.clock_in: call sites", "store.save(staff.clock_in(s))", "[call; unchanged]"])
    st.write_text(s0.replace("shift: Shift }", "shift: Shift, since: Int when it.shift in {Shift.On} }"))
    cexpect(["when field added: since", "expressions entering Shift.On (must supply since)", "s with { shift enters Shift.On }", "[enters; unchanged]"],
            must_not=["staff.Staff: declarations and lines that use it"])
    st.write_text(s0.replace("fn badge_of(s) = s.badge", "fn badge_of(s) = s.badge  "))
    cexpect(["changes     none"])
    st.write_text(s0.replace("  fn clock_in(s) = s with { shift enters Shift.On }", "  fn clock_in(s) =\n    s with { shift enters Shift.On }"))
    cexpect(["changes     none"])                          # reflowing whitespace is not a change
    st.write_text(s0.replace("  fn badge_of(s) = s.badge", "  fn badge_of(s) =\n    let b: ids.BadgeId = s.badge\n    b"))
    cexpect(["staff.badge_of", "body changed only; interface unchanged"], must_not=["sites to inspect"])
    st.write_text(s0.replace("  fn badge_of(s: Staff) -> ids.BadgeId\n", "").replace("  fn badge_of(s) = s.badge\n", ""))
    cexpect(["staff.badge_of", "removed"])
    # propagate: a parameter added writes a hole at the call; a when field added writes a hole at the entering expression; idempotent
    root3 = tmp / "prop"; shutil.copytree(HERE / "fixtures", root3)
    def prop(*flags):
        n[0] += 1
        env = dict(os.environ, BRASS_PROJECT=str(root3), BRASS_INFO_ONLY="1", BRASS_BASELINE=str(base))
        return subprocess.run([sys.executable, str(BRASS), "propagate", *flags], env=env, capture_output=True, text=True).stdout
    out = prop()
    if "no interface change" not in out: fails.append(f"propagate clean: {out}")
    st3 = root3 / "src/park/staff.brass"; s3 = st3.read_text()
    st3.write_text(s3.replace("fn clock_in(s: Staff) -> OnShift", "fn clock_in(s: Staff, by: ids.BadgeId) -> OnShift")
                     .replace("shift: Shift }", "shift: Shift, since: Int when it.shift in {Shift.On} }"))
    out = prop("--dry")
    for m_ in ["planned     3 edits", "store.save(staff.clock_in(s, @@by))", "fn clock_in(s, by) = s with { shift enters Shift.On, since: @@since }", "@@by : ids.BadgeId", "@@since : Int", "dry run"]:
        if m_ not in out: fails.append(f"propagate --dry: missing {m_!r}\n{out}")
    if "@@by" in (root3 / "src/park/desk.brass").read_text(): fails.append("--dry wrote to disk")
    out = prop()
    for m_ in ["written     3 edits, 3 applied", "holes       2", "changes     against"]:
        if m_ not in out: fails.append(f"propagate: missing {m_!r}\n{out}")
    if "staff.clock_in(s, @@by)" not in (root3 / "src/park/desk.brass").read_text(): fails.append("hole not written to desk.brass")
    if "fn clock_in(s, by) = s with { shift enters Shift.On, since: @@since }" not in st3.read_text(): fails.append("body line or hole not written to staff.brass")
    out = prop()
    if "mechanical  nothing" not in out: fails.append(f"propagate second run not idempotent: {out}")
    # lean mode: one-call check ending in done, declarations-only show, no query trailer
    env_l = dict(os.environ, BRASS_PROJECT=str(root), BRASS_NO_LOG="1", BRASS_LEAN="1")
    out_l = subprocess.run([sys.executable, str(BRASS), "check"], env=env_l, capture_output=True, text=True).stdout
    clean = "examples" in out_l and "done        nothing else to run" in out_l
    rejecting = re.search(r"^check       \d+ rejections?", out_l, re.M) and "next        fix these" in out_l
    if not (clean or rejecting) or "query" in out_l:
        fails.append(f"lean check: {out_l}")
    out_s = subprocess.run([sys.executable, str(BRASS), "show", "staff", "desk"], env=env_l, capture_output=True, text=True).stdout
    if "declarations, lines 1 to" not in out_s or out_s.count("file        ") != 2 or re.search(r"^\s*\d+\s+body\s*$", out_s, re.M):
        fails.append(f"lean show: {out_s[:400]}")
    out_b = subprocess.run([sys.executable, str(BRASS), "show", "staff", "--body"], env=env_l, capture_output=True, text=True).stdout
    if "lines 1 to" not in out_b or "declarations," in out_b:
        fails.append(f"lean show --body: {out_b[:300]}")
    # "10 found" is not "0 found": the lean check must count examples, not match a substring
    import re as _re
    if _re.search(r"examples\s+none", out_l) and _re.search(r"\bexample\b", "".join(p.read_text() for p in (root / "src").rglob("*.brass"))):
        fails.append(f"lean check reported no examples in a tree that has them: {out_l}")
    # lean v2: bare show prints every module's declarations; check reports effect order and ends in done
    env_2 = dict(os.environ, BRASS_PROJECT=str(root), BRASS_NO_LOG="1", BRASS_LEAN="2")
    out_2 = subprocess.run([sys.executable, str(BRASS), "show"], env=env_2, capture_output=True, text=True).stdout
    if out_2.count("declarations, lines 1 to") < 3:
        fails.append(f"lean2 bare show: {out_2[:300]}")
    out_2c = subprocess.run([sys.executable, str(BRASS), "check"], env=env_2, capture_output=True, text=True).stdout
    if "effects" not in out_2c and "rejection" not in out_2c:
        fails.append(f"lean2 check: {out_2c}")
    # effect order: a write, then a refusing helper on the same path, is a warning; the same write in an else branch is not
    root4 = tmp / "p4"; shutil.copytree(HERE / "fixtures", root4)
    (root4 / "src/park/effects.brass").write_text("""# park/effects.brass
module park.effects

interface
  access Box
    allow save(n: Int) -> Outcome<Done>
    allow read(n: Int) -> Outcome<Int>
  fn bad(box: Box, n: Int) -> Outcome<Done>
  fn good(box: Box, n: Int) -> Outcome<Done>
  fn branch(box: Box, n: Int) -> Outcome<Done>
  fn guard(n: Int) -> Outcome<Done>
body
  fn bad(box, n) =
    box.save(n)?
    guard(n)

  fn good(box, n) =
    guard(n)?
    box.save(n)

  fn branch(box, n) =
    if n > 0 then box.save(n)
    else Err(FailureCode.InvalidInput, "n must be positive")

  fn guard(n) = if n > 5 then Ok(Done) else Err(FailureCode.Conflict, "too small")
""")
    env_4 = dict(os.environ, BRASS_PROJECT=str(root4), BRASS_NO_LOG="1", BRASS_LEAN="2")
    out_4 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_4, capture_output=True, text=True).stdout
    warn = [l for l in out_4.splitlines() if "warning" in l and "effects.brass" in l]
    if len(warn) != 1 or "box.save" not in warn[0] or "guard" not in warn[0]:
        fails.append(f"effect order: expected exactly one warning, on bad: {out_4}")
    # host contract: an allow the contract does not list is rejected; with it listed, clean
    (root4 / "host-contract.txt").write_text("Box.save\n")
    out_c = subprocess.run([sys.executable, str(BRASS), "check"], env=env_4, capture_output=True, text=True).stdout
    if "Box.read is not a host operation" not in out_c or "done        nothing else" in out_c:
        fails.append(f"host contract, missing op: {out_c}")
    (root4 / "host-contract.txt").write_text("Box.save\nBox.read\n" + "".join(f"{a}\n" for a in ("Store.load", "Store.save", "Store.list", "Clock.now", "Gate.open", "Gate.close", "Vet.prescribe", "Pager.page")))
    out_c2 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_4, capture_output=True, text=True).stdout
    if "Box." in out_c2.split("host")[1].split("\n")[1] if "host        ✗" in out_c2 else False:
        fails.append(f"host contract, all listed: {out_c2}")
    # lean v3 apply: all or nothing; dry writes nothing; a written patch ends in the full check
    env_3 = dict(os.environ, BRASS_PROJECT=str(root4), BRASS_NO_LOG="1", BRASS_LEAN="3")
    ef = root4 / "src/park/effects.brass"; before = ef.read_text()
    good = "@@@ edit src/park/effects.brass\n@@@ find\n  fn good(box, n) =\n@@@ replace\n  fn good(box, n) =\n@@@ end\n"
    two = good + "@@@ edit src/park/effects.brass\n@@@ find\nthis text is not there\n@@@ replace\nx\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_3, input=two, capture_output=True, text=True).stdout
    if "nothing was written" not in r or "block 2   ✗" not in r or ef.read_text() != before:
        fails.append(f"apply all-or-nothing: {r}")
    r = subprocess.run([sys.executable, str(BRASS), "apply", "--dry"], env=env_3, input=good, capture_output=True, text=True).stdout
    if "dry run: all 1 blocks match" not in r or ef.read_text() != before:
        fails.append(f"apply --dry: {r}")
    twice = good + "@@@ edit ./src/park/effects.brass\n@@@ find\n  fn bad(box, n) =\n@@@ replace\n  fn bad(box, n) =\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_3, input=twice, capture_output=True, text=True).stdout
    n[0] += 1
    if "2 blocks written to 1 file" not in r:
        fails.append(f"apply, one file two spellings: {r}")
    env_log = dict(env_3); env_log.pop("BRASS_NO_LOG")
    subprocess.run([sys.executable, str(BRASS), "apply"], env=env_log, input=good, capture_output=True, text=True)
    qid = (root4.parent / "brass-logs" / (root4.name + ".log")).read_text().splitlines()[-1].split("\t")[-1]
    r = subprocess.run([sys.executable, str(BRASS), "verify", qid], env=env_log, input=good, capture_output=True, text=True).stdout
    n[0] += 1
    if "refused" not in r or "writes files" not in r:
        fails.append(f"verify refuses apply: {r}")
    new = "@@@ new src/park/extra.brass\n# park/extra.brass\nmodule park.extra\n\ninterface\n  fn one() -> Int\nbody\n  fn one() = 1\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_3, input=new, capture_output=True, text=True).stdout
    if "written to 1 file" not in r or not (root4 / "src/park/extra.brass").exists() or "check " not in r:
        fails.append(f"apply new file and check: {r}")
    # lean v4: bare show is the index; a find at the wrong indent is shifted and said; `new` on a file that exists
    # replaces it and says so; a long answer stops at a module boundary and names the rest. Lean 3 is unchanged.
    env_4l = dict(os.environ, BRASS_PROJECT=str(root4), BRASS_NO_LOG="1", BRASS_LEAN="4")
    out_i = subprocess.run([sys.executable, str(BRASS), "show"], env=env_4l, capture_output=True, text=True).stdout
    n[0] += 1
    if not out_i.startswith("index") or "declarations, lines 1 to" in out_i or "effects" not in out_i or " lines   " not in out_i:
        fails.append(f"lean4 bare show: {out_i[:300]}")
    out_s4 = subprocess.run([sys.executable, str(BRASS), "show", "staff", "effects"], env=env_4l, capture_output=True, text=True).stdout
    n[0] += 1
    if out_s4.count("file        ") != 2 or "declarations, lines 1 to" not in out_s4 or "not shown" in out_s4:
        fails.append(f"lean4 show two modules: {out_s4[:300]}")
    before4 = ef.read_text()
    wrong = "@@@ edit src/park/effects.brass\n@@@ find\n      box.save(n)?\n      guard(n)\n@@@ replace\n      box.save(n)?\n      guard(n)\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_4l, input=wrong, capture_output=True, text=True).stdout
    n[0] += 1
    if "indented 2 spaces more than the file" not in r or "1 block written" not in r or ef.read_text() != before4:
        fails.append(f"lean4 apply, wrong indent: {r[:400]}")
    r3 = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_3, input=wrong, capture_output=True, text=True).stdout
    n[0] += 1
    if "nothing was written" not in r3 or ef.read_text() != before4:
        fails.append(f"lean3 apply must still refuse a wrong indent: {r3[:300]}")
    shift = "@@@ edit src/park/effects.brass\n@@@ find\n      box.save(n)?\n      guard(n)\n@@@ replace\n      box.save(n)?\n      # moved\n      guard(n)\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_4l, input=shift, capture_output=True, text=True).stdout
    n[0] += 1
    if "    box.save(n)?\n    # moved\n    guard(n)" not in ef.read_text():
        fails.append(f"lean4 apply, shifted replacement: {r[:400]}")
    again = "@@@ new src/park/extra.brass\n# park/extra.brass\nmodule park.extra\n\ninterface\n  fn two() -> Int\nbody\n  fn two() = 2\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_4l, input=again, capture_output=True, text=True).stdout
    n[0] += 1
    extra = (root4 / "src/park/extra.brass").read_text()
    if "replaced in full" not in r or "fn two() = 2" not in extra or "fn one()" in extra:
        fails.append(f"lean4 apply, new on an existing file: {r[:400]}")
    env_pg = dict(env_4l, BRASS_ANSWER_LIMIT="600")
    out_p = subprocess.run([sys.executable, str(BRASS), "show", "--body", "staff", "desk", "effects"], env=env_pg, capture_output=True, text=True).stdout
    n[0] += 1
    if out_p.count("file        ") != 1 or "not shown   desk, effects" not in out_p or "show --body desk effects" not in out_p:
        fails.append(f"lean4 paging: {out_p[-400:]}")
    # lean v4 features: a state of the wrong machine is rejected; a function entering one machine and passing another's
    # state is warned about; `@@@ decl` replaces or adds a declaration by name; a partial apply writes what matches and
    # counts declarations changed; `show --for` prints a declaration and its users with bodies
    root6 = tmp / "p6"; shutil.copytree(HERE / "fixtures", root6)
    mix = root6 / "src/park/mix.brass"
    mix.write_text("""# park/mix.brass
module park.mix

interface
  machine Gate
    states  Shut, Open
    initial Shut
    Shut enters Open
  machine Lamp
    states  Off, On
    initial Off
    Off enters On
  type Note = { gate: Gate, lamp: Lamp }
  fn note_gate(g: Gate) -> Note
  fn wrong() -> Note
  fn mixed(n: Note) -> Note
body
  fn note_gate(g) = { gate: g, lamp: Lamp.Off }
  fn wrong() = note_gate(Lamp.On)
  fn mixed(n) = note_gate(Gate.Open) with { lamp enters Lamp.On }
""")
    env_6 = dict(os.environ, BRASS_PROJECT=str(root6), BRASS_NO_LOG="1", BRASS_LEAN="4")
    out_m = subprocess.run([sys.executable, str(BRASS), "check"], env=env_6, capture_output=True, text=True).stdout
    n[0] += 1
    if "g takes a state of mix.Gate; `Lamp.On` is a state of mix.Lamp" not in out_m or "mix.brass:19" not in out_m:
        fails.append(f"lean4 wrong-machine state not rejected: {out_m[:500]}")
    mix.write_text(mix.read_text().replace("  fn wrong() -> Note\n", "").replace("  fn wrong() = note_gate(Lamp.On)\n", ""))
    out_m2 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_6, capture_output=True, text=True).stdout
    n[0] += 1
    if "machines    ⚠ 1 call" not in out_m2 or "mixed enters states of mix.Lamp and passes a state of mix.Gate to note_gate" not in out_m2 or "read the ⚠ lines" not in out_m2:
        fails.append(f"lean4 machine mix not warned: {out_m2[:700]}")
    env_3b = dict(env_6, BRASS_LEAN="3")
    out_m3 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_3b, capture_output=True, text=True).stdout
    n[0] += 1
    if "machines" in out_m3 or "done        nothing else to run" not in out_m3:
        fails.append(f"lean3 must not carry the machine warning: {out_m3[-300:]}")
    decl = ("@@@ decl src/park/effects.brass guard\n@@@ interface\n  fn guard(n: Int) -> Outcome<Done>\n@@@ body\n"
            "  fn guard(n) = if n > 4 then Ok(Done) else Err(FailureCode.Conflict, \"too small\")\n@@@ end\n"
            "@@@ decl src/park/effects.brass extra_fn\n@@@ interface\n  fn extra_fn() -> Int\n@@@ body\n  fn extra_fn() = 7\n@@@ end\n")
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_4l, input=decl, capture_output=True, text=True).stdout
    n[0] += 1
    et = ef.read_text()
    if "2 blocks written" not in r or "n > 4" not in et or "n > 5" in et or "fn extra_fn() -> Int" not in et.split("body")[0] or "fn extra_fn() = 7" not in et or "declared and" not in r:
        fails.append(f"lean4 decl block: {r[:500]}\n{et}")
    r3 = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_3, input=decl, capture_output=True, text=True).stdout
    n[0] += 1
    if "is a lean 4 form" not in r3 or "nothing was written" not in r3:
        fails.append(f"lean3 must refuse decl blocks: {r3[:300]}")
    env_pb = dict(env_4l, BRASS_BASELINE=str(HERE / "fixtures"))
    two4 = ("@@@ edit src/park/effects.brass\n@@@ find\n  fn extra_fn() = 7\n@@@ replace\n  fn extra_fn() = 8\n@@@ end\n"
            "@@@ edit src/park/effects.brass\n@@@ find\nthis text is not there\n@@@ replace\nx\n@@@ end\n")
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_pb, input=two4, capture_output=True, text=True).stdout
    n[0] += 1
    if "1 of 2 blocks written" not in r or "fn extra_fn() = 8" not in ef.read_text() or "not written 1 block" not in r or "changed     " not in r or "against the baseline" not in r:
        fails.append(f"lean4 partial apply: {r[:700]}")
    out_f = subprocess.run([sys.executable, str(BRASS), "show", "--for", "staff.Staff"], env=env_4l, capture_output=True, text=True).stdout
    n[0] += 1
    if not out_f.startswith("for         staff.Staff: used by") or "user        " not in out_f or out_f.count("file        ") < 2:
        fails.append(f"lean4 show --for: {out_f[:400]}")
    # lean v5: verbatim reads; the index with imports and a bulk next line; one ✓ line in check and apply; touched by
    # resolved callee, not bare name, with "calls changed" when only a callee changed
    root7 = tmp / "p7"; shutil.copytree(HERE / "fixtures", root7)
    env_5 = dict(os.environ, BRASS_PROJECT=str(root7), BRASS_NO_LOG="1", BRASS_LEAN="5", BRASS_BASELINE=str(HERE / "fixtures"))
    out_i5 = subprocess.run([sys.executable, str(BRASS), "show"], env=env_5, capture_output=True, text=True).stdout
    n[0] += 1
    if "← ids staff" not in out_i5 or not out_i5.rstrip().splitlines()[-1].startswith("next        brass show --body"):
        fails.append(f"lean5 index: {out_i5[:500]}")
    out_b5 = subprocess.run([sys.executable, str(BRASS), "show", "--body", "staff"], env=env_5, capture_output=True, text=True).stdout
    n[0] += 1
    src = (root7 / "src/park/staff.brass").read_text().rstrip("\n")
    if src not in out_b5:
        fails.append(f"lean5 show --body is not verbatim: {out_b5[:300]}")
    out_c5 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_5, capture_output=True, text=True).stdout
    n[0] += 1
    if not out_c5.startswith("check       ✓ structure") or "scenarios   none" in out_c5 or "not checked" in out_c5 or "effects     ✓" in out_c5:
        fails.append(f"lean5 quiet check: {out_c5[:500]}")
    ev = root7 / "src/park/evalcheck.brass"
    ev.write_text(ev.read_text().replace("  fn label(note: Maybe<Text>) -> Text\n", "  fn label(note: Maybe<Text>) -> Text\n  fn clock_in(n: Int) -> Int\n")
                  .replace("  fn label(note) =", "  fn clock_in(n) = n + 1\n  fn label(note) ="))
    env_4t = dict(env_5, BRASS_LEAN="4")
    out_t4 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_4t, capture_output=True, text=True).stdout
    out_t5 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_5, capture_output=True, text=True).stdout
    n[0] += 1
    if "desk.open" not in out_t4 or "desk.open" in out_t5:
        fails.append(f"lean5 touched by bare name: lean4 should list desk.open, lean5 should not\n{out_t4}\n---\n{out_t5}")
    st7 = root7 / "src/park/staff.brass"
    st7.write_text(st7.read_text().replace("  fn badge_of(s) = s.badge", "  fn badge_of(s) = s.badge\n").replace("fn clock_in(s) = s with { shift enters Shift.On }", "fn clock_in(s) = s with { shift enters Shift.On }  # touched"))
    out_t5b = subprocess.run([sys.executable, str(BRASS), "check"], env=env_5, capture_output=True, text=True).stdout
    n[0] += 1
    if "calls changed staff.clock_in" not in out_t5b:
        fails.append(f"lean5 touched via a changed callee: {out_t5b}")
    edit5 = "@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = 2\n@@@ end\n@@@ edit src/park/desk.brass\n@@@ find\n  fn quiet(n) =\n@@@ replace\n  fn quiet(n) =\n@@@ end\n"
    r5 = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_5, input=edit5, capture_output=True, text=True).stdout
    n[0] += 1
    if "  written   desk ×2" not in r5 or "block 1   ✓" in r5:
        fails.append(f"lean5 quiet apply: {r5[:400]}")
    # lean v6: `try` checks a fragment as a scratch module (by fragment line, examples evaluated) and a patch in a copy;
    # nothing is written; absent below level 6
    root8 = tmp / "p8"; shutil.copytree(HERE / "fixtures", root8)
    env_6t = dict(os.environ, BRASS_PROJECT=str(root8), BRASS_NO_LOG="1", BRASS_LEAN="6", BRASS_BASELINE=str(HERE / "fixtures"))
    frag_ok = "  fn twice(n: Int) -> Int\n    example twice(2) == 4\n    example twice(2) == 5\nbody\n  fn twice(n) = n * 2\n"
    r = subprocess.run([sys.executable, str(BRASS), "try"], env=env_6t, input=frag_ok, capture_output=True, text=True).stdout
    n[0] += 1
    if "try         ✓ the fragment passes" not in r or "1 of 2 hold" not in r or "fragment line 3" not in r:
        fails.append(f"lean6 try, fragment: {r}")
    frag_bad = "  fn wrong_state(s: staff.Staff) -> staff.OnShift\nbody\n  fn wrong_state(s) = staff.clock_in(s, 1)\n"
    r = subprocess.run([sys.executable, str(BRASS), "try"], env=env_6t, input=frag_bad, capture_output=True, text=True).stdout
    n[0] += 1
    if "✗ 1 rejection in the fragment" not in r or "fragment line 3" not in r or "takes 1 argument" not in r:
        fails.append(f"lean6 try, rejected fragment: {r}")
    before8 = (root8 / "src/park/desk.brass").read_text()
    r = subprocess.run([sys.executable, str(BRASS), "try"], env=env_6t, input="@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = 3\n@@@ end\n", capture_output=True, text=True).stdout
    n[0] += 1
    if not r.startswith("try") or "would be written" not in r or "nothing was written to your project" not in r or (root8 / "src/park/desk.brass").read_text() != before8 or list((root8 / "src/park").glob("try_scratch*")):
        fails.append(f"lean6 try, patch: {r}")
    r5 = subprocess.run([sys.executable, str(BRASS), "try"], env=dict(env_6t, BRASS_LEAN="5"), input=frag_ok, capture_output=True, text=True).stdout
    n[0] += 1
    if "unknown command: try" not in r5:
        fails.append(f"lean5 must not offer try: {r5[:200]}")
    # lean v7: apply checks before it writes; a rejected patch writes nothing and is held; a block with the same file and
    # find text replaces the held one; --drop discards; an unmatched block holds the rest; try is a dry run
    root9 = tmp / "p9"; shutil.copytree(HERE / "fixtures", root9)
    env_7 = dict(os.environ, BRASS_PROJECT=str(root9), BRASS_NO_LOG="1", BRASS_LEAN="7", BRASS_BASELINE=str(HERE / "fixtures"))
    d9 = root9 / "src/park/desk.brass"; orig9 = d9.read_text()
    usage7 = subprocess.run([sys.executable, str(BRASS), "help"], env=env_7, capture_output=True, text=True).stdout
    n[0] += 1
    if "It checks before it writes" not in usage7 or "brass apply --drop" not in usage7 or "brass try" in usage7:
        fails.append(f"lean7 usage: {usage7[:600]}")
    bad7 = ("@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = probe(1, 2)\n@@@ end\n"
            "@@@ edit src/park/desk.brass\n@@@ find\n  fn quiet(n) =\n@@@ replace\n  fn quiet(n) =\n@@@ end\n")
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_7, input=bad7, capture_output=True, text=True).stdout
    n[0] += 1
    if "nothing written: the check rejects" not in r or "probe(…) takes 1 argument" not in r or "line " not in r or "held        2 blocks" not in r or d9.read_text() != orig9 or not (root9 / ".brass-pending").exists():
        fails.append(f"lean7 rejected patch must write nothing and hold: {r}")
    fix7 = "@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = probe(2)\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_7, input=fix7, capture_output=True, text=True).stdout
    n[0] += 1
    if "✓ checked, then written: 2 blocks" not in r or "1 of them held from before" not in r or "fn helper() = probe(2)" not in d9.read_text() or (root9 / ".brass-pending").exists():
        fails.append(f"lean7 amend and commit: {r}")
    d9.write_text(orig9)
    miss7 = ("@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = 5\n@@@ end\n"
             "@@@ edit src/park/desk.brass\n@@@ find\nno such text\n@@@ replace\nx\n@@@ end\n")
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_7, input=miss7, capture_output=True, text=True).stdout
    n[0] += 1
    if "nothing written: 1 block did not match" not in r or "block 2   ✗" not in r or "held        1 block" not in r or d9.read_text() != orig9:
        fails.append(f"lean7 unmatched block holds the rest: {r}")
    r = subprocess.run([sys.executable, str(BRASS), "apply", "--drop"], env=env_7, capture_output=True, text=True).stdout
    n[0] += 1
    if "held patch discarded" not in r or (root9 / ".brass-pending").exists():
        fails.append(f"lean7 --drop: {r}")
    good7 = "@@@ edit src/park/desk.brass\n@@@ find\n  fn helper() = 1\n@@@ replace\n  fn helper() = 6\n@@@ end\n"
    r = subprocess.run([sys.executable, str(BRASS), "apply", "--dry"], env=env_7, input=good7, capture_output=True, text=True).stdout
    n[0] += 1
    if "dry run: every block matches and the check passes; nothing written" not in r or d9.read_text() != orig9 or (root9 / ".brass-pending").exists():
        fails.append(f"lean7 apply --dry writes and holds nothing: {r}")
    r = subprocess.run([sys.executable, str(BRASS), "try"], env=env_7, input=good7, capture_output=True, text=True).stdout
    n[0] += 1
    if "unknown command: try" not in r or d9.read_text() != orig9:
        fails.append(f"lean7 has no try (apply --dry does it): {r}")
    r = subprocess.run([sys.executable, str(BRASS), "apply"], env=env_7, input=good7, capture_output=True, text=True).stdout
    n[0] += 1
    if "✓ checked, then written: 1 block" not in r or "fn helper() = 6" not in d9.read_text() or "changed     " not in r:
        fails.append(f"lean7 clean patch writes at once: {r}")
    # lean v8: a declared type loosened to a builtin is a warning (absent at level 7); `show --for` on an access names its
    # users without bodies
    root10 = tmp / "p10"; shutil.copytree(HERE / "fixtures", root10)
    env_8 = dict(os.environ, BRASS_PROJECT=str(root10), BRASS_NO_LOG="1", BRASS_LEAN="8", BRASS_BASELINE=str(HERE / "fixtures"))
    st10 = root10 / "src/park/staff.brass"
    st10.write_text(st10.read_text().replace("type Staff   = { badge: ids.BadgeId, shift: Shift }", "type Staff   = { badge: Text, shift: Shift }"))
    out8 = subprocess.run([sys.executable, str(BRASS), "check"], env=env_8, capture_output=True, text=True).stdout
    out7 = subprocess.run([sys.executable, str(BRASS), "check"], env=dict(env_8, BRASS_LEAN="7"), capture_output=True, text=True).stdout
    n[0] += 1
    if "field `badge` of staff.Staff was ids.BadgeId at the start and is Text now" not in out8 or "read the ⚠ lines" not in out8 or "loosened" in out7:
        fails.append(f"lean8 loosened type: {out8}\n---\n{out7}")
    st10.write_text((HERE / "fixtures/src/park/staff.brass").read_text())
    out8b = subprocess.run([sys.executable, str(BRASS), "check"], env=env_8, capture_output=True, text=True).stdout
    n[0] += 1
    if "types kept" not in out8b.split("\n")[0]:
        fails.append(f"lean8 types kept: {out8b[:300]}")
    out_fa = subprocess.run([sys.executable, str(BRASS), "show", "--for", "desk.Store"], env=env_8, capture_output=True, text=True).stdout
    n[0] += 1
    if "an access;" not in out_fa or "desk.open" not in out_fa or "user        " in out_fa:
        fails.append(f"lean8 show --for on an access: {out_fa[:400]}")
    # evaluator: an if-chain whose inline branches continue on the next line (`… then "4"` / `else if … else "9"`) is one
    # expression, as on one line (found scoring the Stage 2 trial, 2026-10-17)
    root11 = tmp / "p11"; shutil.copytree(HERE / "fixtures", root11)
    (root11 / "src/park/digits.brass").write_text("""# park/digits.brass
module park.digits

interface
  fn digit(d: Int) -> Text
    example digit(3) == "3"
    example digit(5) == "5"
    example digit(9) == "9"
body
  fn digit(d) =
    if d == 0 then "0" else if d == 1 then "1" else if d == 2 then "2" else if d == 3 then "3" else if d == 4 then "4"
    else if d == 5 then "5" else if d == 6 then "6" else if d == 7 then "7" else if d == 8 then "8" else "9"
""")
    out11 = subprocess.run([sys.executable, str(BRASS), "check"], env=dict(os.environ, BRASS_PROJECT=str(root11), BRASS_NO_LOG="1", BRASS_LEAN="1"), capture_output=True, text=True).stdout
    n[0] += 1
    if "FAILS" in out11 or "fault" in out11 or not re.search(r"examples.*3 hold|\b0 fail", out11):
        fails.append(f"evaluator, if-chain across lines: {out11}")
    # converter coverage, scoped to converters.txt: a passing direct example per state; missing, failing, and
    # non-converter entries each reported; no file, no check
    root5 = tmp / "p5"; shutil.copytree(HERE / "fixtures", root5)
    conv = root5 / "src/park/conv.brass"
    head = ("# park/conv.brass\nmodule park.conv\n\ninterface\n  machine Gate\n    states  Shut, Open, Jammed\n    initial Shut\n"
            "    Shut enters Open\n    Open enters Shut | Jammed\n\n  type Word = Closed | Opened | Stuck\n\n  fn of_gate(g: Gate) -> Word\n")
    body = ("  fn is_open(g: Gate) -> Bool\nbody\n  fn of_gate(g) = if g in {Gate.Shut} then Word.Closed else if g in {Gate.Open} "
            "then Word.Opened else Word.Stuck\n  fn is_open(g) = g in {Gate.Open}\n")
    full = ("    example of_gate(Gate.Shut) == Word.Closed\n    example of_gate(Gate.Open) == Word.Opened\n"
            "    example of_gate(Gate.Jammed) == Word.Stuck\n")
    env_5 = dict(os.environ, BRASS_PROJECT=str(root5), BRASS_NO_LOG="1", BRASS_LEAN="2")
    def ccheck(examples, listed):
        conv.write_text(head + examples + body)
        (root5 / "converters.txt").write_text(listed)
        return subprocess.run([sys.executable, str(BRASS), "check"], env=env_5, capture_output=True, text=True).stdout
    r = ccheck(full, "conv.of_gate\n")
    if "✓ conv.of_gate: a passing direct example for every state of Gate (3)" not in r: fails.append(f"converter, covered: {r}")
    r = ccheck(full.replace("Gate.Jammed", "Gate.Open").replace("Word.Stuck", "Word.Opened"), "conv.of_gate\n")
    if "no direct example for Jammed" not in r or " fail" in r.split("converters")[1].split("\n")[1]: fails.append(f"converter, missing state: {r}")
    r = ccheck(full.replace("Gate.Open) == Word.Opened", "Gate.Open) == Word.Stuck"), "conv.of_gate\n")
    if "1 example fail (line 15)" not in r or "no direct example" in r or "done        nothing else" in r: fails.append(f"converter, failing example: {r}")
    r = ccheck(full, "conv.of_gate\nconv.is_open\n")
    if "✗ conv.is_open (Gate): no direct example for Shut, Open, Jammed" not in r: fails.append(f"converter, undesignated shape: {r}")
    r = ccheck(full, "conv.nothing\n")
    if "conv.nothing: not a total fn in the tree" not in r: fails.append(f"converter, unknown name: {r}")
    (root5 / "converters.txt").unlink()
    r = subprocess.run([sys.executable, str(BRASS), "check"], env=env_5, capture_output=True, text=True).stdout
    if "converters" in r: fails.append(f"converter, no file: {r}")
    # the stand-in evaluator: every example in the fixture tree holds (park/evalcheck.brass carries the regression cases)
    env = dict(os.environ, BRASS_PROJECT=str(root), BRASS_NO_LOG="1")
    out = subprocess.run([sys.executable, str(BRASS), "check", "--examples"], env=env, capture_output=True, text=True).stdout
    if out.count("holds    evalcheck.") != 9 or "FAILS    evalcheck." in out: fails.append(f"evaluator regression examples: {out}")
    shutil.rmtree(tmp)
    if fails:
        print("FAIL"); print("\n---\n".join(fails)); sys.exit(1)
    print(f"ok: {n[0]} cases, plus the inline checks")

if __name__ == "__main__":
    main()
