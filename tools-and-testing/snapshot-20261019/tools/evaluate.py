#!/usr/bin/env python3
"""Run a case table against an expense-desk tree, in either language.

usage: evaluate.py <project-dir> brass|python <cases.json> [--json out.json] [--only B01,B02]

Python: the tree is imported; each operation is called with a fake Store and Ledger built from the case's fixture.
Brass: the tree is loaded by the brass stand-in; each granted entry point runs in the stand-in evaluator against a
host whose replies come from the same fixture, keyed by argument, so reads may happen in any order. A refined
parameter type, refinements inside its records and arrays included, and every `before` line of the entry point are
checked before the body runs, as the runtime's boundary would (InvalidInput, no host call).

Values are built from the tree's own declarations: records by field name, enumerations by member name, so a session's
added fields and renamed modules do not matter. A field the fixture does not give gets its type's zero value; a value
that cannot be built is reported as "could not run", never scored as a defect of the program.

Comparison (SPEC.md §5): the result, on the fields the case names; per record (a report or advance id), saves and
ledger calls in order and audit entries as a set; any order across records; a saved record on the fields the case names; an audit entry on who,
record, from, to, and its reason only where the case says what it must contain. Reads are not compared. Names of
states and enumeration members compare case-blind and without underscores (APPROVED, Approved).

A test, not a proof. The Brass side runs the stand-in; contracts and refinements beyond the boundary are not checked.
"""
import dataclasses
import enum
import importlib
import importlib.machinery
import importlib.util
import inspect
import json
import os
import pkgutil
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROXY = HERE.parents[2] / "validation" / "proxy" / "bin"   # the current brass stand-in (the rerun); stage 1 ran pre-c25

ENUM_MARKERS = {"Category": "Feed", "Role": "Supervisor", "ReportStatus": "ChangesRequested", "Currency": "CRC",
                "AdvanceStatus": "Settled", "PoStatus": "Received", "CardStatus": "Disputed", "ExceptionStatus": "Granted",
                "Region": "Offsite", "Vehicle": "Boat"}

# The grown baseline's Registry (SPEC-GROWN.md §2): read operations answered from the case's "registry" fixture.
REG_ONE = {"vendor": ("vendors", "Vendor", None), "po": ("pos", "PurchaseOrder", "PoStatus"),
           "txn": ("txns", "CardTxn", "CardStatus"), "delegation": ("delegations", "Delegation", None),
           "cost_center": ("cost_centers", "CostCenter", None), "entity": ("entities", "Entity", None),
           "exception": ("exceptions", "PolicyException", "ExceptionStatus")}
REG_SAVES = {"save_po": ("id", "status", "approvals", "received"), "save_txn": ("id", "status", "matched"),
             "save_delegation": ("id", "revoked", "delegator", "delegate", "first", "last"), "save_vendor": ("id", "active"),
             "save_card_limit": ("badge", "limit"), "save_exception": ("id", "status", "decided_by", "position")}
ARG_ENUMS = {"region": "Region", "vehicle": "Vehicle", "category": "Category"}


class NotFoundInFixture(Exception):
    pass


def registry_read(name, a, fx, build):
    """(handled, value) for a Registry read; raises NotFoundInFixture for a missing record."""
    rg = fx.get("registry", {})
    if name in REG_ONE:
        key, rec, st = REG_ONE[name]
        hit = [x for x in rg.get(key, []) if x["id"] == a[0]]
        if not hit:
            raise NotFoundInFixture(name)
        return True, build(rec, hit[0], st)
    rows = lambda key, rec, st, pred: [build(rec, x, st) for x in rg.get(key, []) if pred(x)]
    if name == "pos_for": return True, rows("pos", "PurchaseOrder", "PoStatus", lambda x: x["department"] == a[0] and x["period"] == a[1])
    if name == "pos_of_vendor": return True, rows("pos", "PurchaseOrder", "PoStatus", lambda x: x["vendor"] == a[0])
    if name == "txns_for": return True, rows("txns", "CardTxn", "CardStatus", lambda x: x["period"] == a[0])
    if name == "delegations_from": return True, rows("delegations", "Delegation", None, lambda x: x["delegator"] == a[0])
    if name == "exceptions_for": return True, rows("exceptions", "PolicyException", "ExceptionStatus", lambda x: x["report"] == a[0])
    if name == "departments_of":
        if a[0] not in rg.get("departments_of", {}):
            raise NotFoundInFixture(name)
        return True, list(rg["departments_of"][a[0]])
    if name == "departments": return True, [d["id"] for d in fx["departments"]]
    if name == "allowance":
        hit = [x["amount"] for x in rg.get("allowances", []) if x["department"] == a[0] and x["period"] == a[1]]
        if not hit:
            raise NotFoundInFixture(name)
        return True, hit[0]
    if name == "card_limit":
        hit = [x for x in rg.get("card_limits", []) if x["badge"] == a[0]]
        if not hit:
            raise NotFoundInFixture(name)
        return True, build("CardLimit", hit[0], None)
    return False, None


class Failed(Exception):
    pass


def canon(v):
    if isinstance(v, str):
        return v.lower().replace("_", "")
    if isinstance(v, dict):
        return {k: canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [canon(x) for x in v]
    return v


def matches(want, got):
    """Does got carry what want names? Dicts compare on want's keys only; lists element by element."""
    if isinstance(want, dict):
        return isinstance(got, dict) and all(matches(v, got.get(k)) for k, v in want.items())
    if isinstance(want, list):
        return isinstance(got, list) and len(got) == len(want) and all(matches(a, b) for a, b in zip(want, got))
    return canon(want) == canon(got)


def record_key(w):
    if w["op"] in ("save_report", "save_advance") or w["op"] in REG_SAVES:
        return w.get("id") or w.get("badge")
    if w["op"] == "append_audit":
        return w.get("report")
    if w["op"] == "pay":
        return w.get("key")
    return w["op"]


def write_problems(key, want, got):
    """Saves and ledger calls in order; audit entries as a set, each expected entry matched by a distinct one."""
    problems = []
    w_main = [w for w in want if w["op"] != "append_audit"]; g_main = [g for g in got if g["op"] != "append_audit"]
    for i, w in enumerate(w_main):
        if i >= len(g_main):
            problems.append(f"{key}: {w['op']} {i + 1} expected, got nothing"); break
        g = g_main[i]
        if g["op"] != w["op"]:
            problems.append(f"{key}: write {i + 1} expected {w['op']}, got {g['op']}"); break
        for k, v in w.items():
            if k != "op" and not matches(v, g.get(k)):
                problems.append(f"{key}: {w['op']} {i + 1}: {k} expected {v!r}, got {g.get(k)!r}")
    if len(g_main) > len(w_main):
        problems.append(f"{key}: unexpected {g_main[len(w_main)]['op']}")
    w_aud = [w for w in want if w["op"] == "append_audit"]; g_aud = [g for g in got if g["op"] == "append_audit"]
    free = list(g_aud)
    for w in w_aud:
        hit = next((g for g in free if all(canon(v) in canon(g.get("reason") or "") if k == "reason_contains"
                                           else matches(v, g.get(k)) for k, v in w.items() if k != "op")), None)
        if hit is None:
            problems.append(f"{key}: no audit entry matching {({k: v for k, v in w.items() if k != 'op'})}; got {[(g['who'], g['from'], g['to']) for g in g_aud]}")
        else:
            free.remove(hit)
    if free and len(g_aud) > len(w_aud):
        problems.append(f"{key}: {len(g_aud) - len(w_aud)} unexpected audit entries")
    return problems


def compare(case, result, writes):
    problems = []
    if not matches(case["expect"], result):
        problems.append(f"result: expected {case['expect']}, got {result}")
    want_g, got_g = {}, {}
    for w in case["writes"]:
        want_g.setdefault(record_key(w), []).append(w)
    for w in writes:
        got_g.setdefault(record_key(w), []).append(w)
    for key in list(want_g) + [k for k in got_g if k not in want_g]:
        problems.extend(write_problems(key, want_g.get(key, []), got_g.get(key, [])))
    return problems


def audit_fields(get):
    frm = next((get(n) for n in ("was", "from_status", "from_", "before", "old") if get(n) is not None), None)
    to = next((get(n) for n in ("now", "to_status", "to", "after", "new") if get(n) is not None), None)
    rec = next((get(n) for n in ("report", "record", "report_id", "advance", "id") if get(n) is not None), None)
    return rec, frm, to


# --- Python ------------------------------------------------------------------------------------------------------

class PyRunner:
    def __init__(self, project):
        sys.path.insert(0, str(Path(project) / "src"))
        for k in [k for k in sys.modules if k == "desk" or k.startswith("desk.")]:
            del sys.modules[k]
        pkg = importlib.import_module("desk")
        self.mods = {n: importlib.import_module(f"desk.{n}") for _, n, _ in pkgutil.iter_modules(pkg.__path__)}
        self.errors = self.mods["errors"]
        self.classes = {}
        for m in self.mods.values():
            for name, c in vars(m).items():
                if inspect.isclass(c) and c.__module__.startswith("desk"):
                    self.classes.setdefault(name, c)
        self.enums = {}
        for role, member in ENUM_MARKERS.items():
            hit = [c for c in self.classes.values() if issubclass(c, enum.Enum) and any(self.same(e, member) for e in c)]
            if hit:                                   # the exact name, else the smallest enumeration holding the marker
                self.enums[role] = min(hit, key=lambda c: (c.__name__ != role, len(c)))

    @staticmethod
    def same(e, name):
        return canon(e.name) == canon(name) or canon(str(e.value)) == canon(name)

    def enum(self, role, name):
        if role not in self.enums:
            raise Failed(f"no enumeration with a member {ENUM_MARKERS[role]}")
        for e in self.enums[role]:
            if self.same(e, name):
                return e
        raise Failed(f"{self.enums[role].__name__} has no member {name}")

    def cls(self, name):
        c = self.classes.get(name)
        if c is None or not dataclasses.is_dataclass(c):
            raise Failed(f"no dataclass {name}")
        return c

    def build(self, name, data, status_role="ReportStatus"):
        c = self.cls(name)
        kw = {}
        for f in dataclasses.fields(c):
            if f.name not in data or data[f.name] is None and f.name not in ("supervisor",):
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                    if f.name in data:
                        kw[f.name] = None; continue
                    raise Failed(f"{name}.{f.name} has no default and the fixture does not give it")
                continue
            kw[f.name] = self.convert(f.name, data[f.name], status_role)
        return c(**kw)

    def convert(self, field, v, status_role):
        if field == "category": return self.enum("Category", v)
        if field == "role": return self.enum("Role", v)
        if field == "currency": return self.enum("Currency", v)
        if field == "status": return self.enum(status_role or "ReportStatus", v)
        if field == "lines": return tuple(self.build("Line", l) for l in v)
        if field in ("approvals", "departments"): return tuple(v)
        return v

    def arg(self, v, name=""):
        if name in ARG_ENUMS and isinstance(v, str):
            return self.enum(ARG_ENUMS[name], v)
        if isinstance(v, dict) and "category" in v:
            return self.build("Line", v)
        if isinstance(v, list) and v and isinstance(v[0], dict) and "position" in v[0]:
            rc = next((c for c in self.classes.values() if dataclasses.is_dataclass(c)
                       and {"position", "reason"} <= {f.name for f in dataclasses.fields(c)}), None)
            return [rc(**x) if rc else dict(x) for x in v]
        return v

    def plain(self, v, top=True):
        if v is None and top: return "Done"
        if isinstance(v, enum.Enum): return v.name
        if dataclasses.is_dataclass(v): return {f.name: self.plain(getattr(v, f.name), False) for f in dataclasses.fields(v)}
        if isinstance(v, (list, tuple)): return [self.plain(x, False) for x in v]
        if isinstance(v, dict): return {k: self.plain(x, False) for k, x in v.items()}
        return v

    def find(self, op):
        for n in ("review", "payment", "queries") + tuple(sorted(self.mods)):
            f = getattr(self.mods.get(n), op, None)
            if inspect.isfunction(f):
                return f
        raise Failed(f"operation {op} not found")

    def run(self, case):
        rn, F, FC = self, self.errors.Failure, self.errors.FailureCode
        fx = case["store"]
        writes, ids, replies = [], list(fx.get("next_ids", ["n1", "n2"])), list(case["ledger"])

        def nf(what):
            raise F(FC.NOT_FOUND, f"no such {what}")

        def name(v):
            return v.name if isinstance(v, enum.Enum) else v

        class Store:
            def staff(self, badge):
                hit = [s for s in fx["staff"] if s["badge"] == badge]
                return rn.build("Staff", hit[0]) if hit else nf("staff member")
            def report(self, id):
                hit = [r for r in fx["reports"] if r["id"] == id]
                return rn.build("Report", hit[0]) if hit else nf("report")
            def department(self, id):
                hit = [d for d in fx["departments"] if d["id"] == id]
                return rn.build("Department", hit[0]) if hit else nf("department")
            def reports_for(self, department, period):
                return [rn.build("Report", r) for r in fx["reports"] if r["department"] == department and r["period"] == period]
            def submitted_reports(self):
                return [rn.build("Report", r) for r in fx["reports"] if r["status"] == "Submitted"]
            def period_closed(self, period):
                return period in fx["closed"]
            def next_id(self):
                return ids.pop(0)
            def rate(self, currency, period):
                hit = [x["rate"] for x in fx.get("rates", []) if canon(x["currency"]) == canon(name(currency)) and x["period"] == period]
                return hit[0] if hit else nf("rate")
            def advance(self, id):
                hit = [a for a in fx.get("advances", []) if a["id"] == id]
                return rn.build("Advance", hit[0], "AdvanceStatus") if hit else nf("advance")
            def advances_for(self, department, period):
                return [rn.build("Advance", a, "AdvanceStatus") for a in fx.get("advances", []) if a["department"] == department and a["period"] == period]
            def paid_advances(self):
                return [rn.build("Advance", a, "AdvanceStatus") for a in fx.get("advances", []) if a["status"] == "Paid"]
            def save_report(self, r):
                g = lambda n: getattr(r, n, None)
                writes.append({"op": "save_report", "id": r.id, "status": name(r.status), "approvals": list(r.approvals),
                               "reference": g("reference"), "badge": g("badge"), "department": g("department"),
                               "period": g("period"), "line_count": len(r.lines), "line_amounts": [l.amount for l in r.lines]})
            def save_advance(self, a):
                g = lambda n: getattr(a, n, None)
                writes.append({"op": "save_advance", "id": a.id, "status": name(a.status), "approvals": list(g("approvals") or []),
                               "reference": g("reference"), "owed": g("owed"), "amount": g("amount"), "badge": g("badge"),
                               "department": g("department"), "period": g("period")})
            def append_audit(self, e):
                rec, frm, to = audit_fields(lambda n: getattr(e, n, None))
                writes.append({"op": "append_audit", "who": e.who, "report": rec, "from": name(frm), "to": name(to),
                               "reason": getattr(e, "reason", None)})
            def close_period(self, period):
                writes.append({"op": "close_period", "period": period})

        class Ledger:
            def pay(self, badge, amount, key):
                writes.append({"op": "pay", "badge": badge, "amount": amount, "key": key})
                rep = replies.pop(0) if replies else "Unavailable"
                if rep == "Unavailable":
                    raise F(FC.UNAVAILABLE, "ledger down")
                return rep

        def pybuild(rec, data, st):
            return rn.build(rec, data, st)

        class Registry:
            def __getattr__(self, name):
                if name in REG_SAVES:
                    def save(x, _n=name):
                        writes.append({"op": _n, **{k: rn.plain(getattr(x, k, None), False) for k in REG_SAVES[_n]}})
                    return save
                def read(*a, _n=name):
                    try:
                        ok, v = registry_read(_n, [name_of(x) for x in a], fx, pybuild)
                    except NotFoundInFixture:
                        raise F(FC.NOT_FOUND, f"no such {_n}")
                    if not ok:
                        raise AttributeError(_n)
                    return v
                return read

        def name_of(x):
            return x.name if isinstance(x, enum.Enum) else x

        fn = self.find(case["op"])
        kwargs = {}
        for pn, p in inspect.signature(fn).parameters.items():
            if "store" in pn: kwargs[pn] = Store()
            elif "ledger" in pn: kwargs[pn] = Ledger()
            elif pn in ("reg", "registry"): kwargs[pn] = Registry()     # by name exactly: `region` is not the registry
            elif pn in case["args"]: kwargs[pn] = self.arg(case["args"][pn], pn)
            elif p.default is inspect.Parameter.empty:
                raise Failed(f"{case['op']} takes {pn}, which the case does not give")
        try:
            result = {"ok": self.plain(fn(**kwargs))}
        except F as f:
            result = {"err": f.code.value}
        return result, writes


# --- Brass --------------------------------------------------------------------------------------------------------

class FakeDecl:
    def __init__(self, text, key):
        self.lines, self.key = [(0, f"type X = {text}")], key


class BrassRunner:
    def __init__(self, project):
        os.environ.update(BRASS_PROJECT=str(project), BRASS_NO_LOG="1", BRASS_SRC="desk")
        loader = importlib.machinery.SourceFileLoader("brass_mod", str(PROXY / "brass"))
        spec = importlib.util.spec_from_loader("brass_mod", loader)
        self.kc = importlib.util.module_from_spec(spec); loader.exec_module(self.kc)
        sys.path.insert(0, str(PROXY))
        import brasseval as ke
        self.ke = ke
        self.w = self.kc.World()
        if self.w.parse_errors:
            raise Failed(f"parse errors: {self.w.parse_errors}")
        self.ev0 = ke.Evaluator(self.w, self.kc.strip_comment)
        self.entries = {d.name: (m, d) for _, _, m, d in self.kc.grant_entries(self.w)}
        self.enums = {}
        for role, member in ENUM_MARKERS.items():
            hit = [(d, st) for d in self.w.decls.values() for st in [self.states(d)] if st and any(canon(s) == canon(member) for s in st)]
            if hit:                                   # the exact name, else a machine, else the smallest enumeration holding the marker
                d, st = min(hit, key=lambda h: (h[0].name != role, h[0].kind != "machine", len(h[1])))
                self.enums[role] = (d.key, st)

    def states(self, d):
        if d.kind == "machine":
            text = " ".join(self.kc.strip_comment(l) for _, l in d.lines)
            m = re.search(r"\bstates\s+(.+?)(?:\s+initial\b|$)", text)
            return [s.strip() for s in m.group(1).split(",")] if m else None
        return self.ev0.enum_states(d) if d.kind == "type" else None

    def decl(self, name):
        hit = [d for d in self.w.decls.values() if d.name == name and d.kind == "type"]
        if not hit:
            raise Failed(f"no type {name}")
        return hit[0]

    def enum(self, role, name):
        if role not in self.enums:
            raise Failed(f"no enumeration with a member {ENUM_MARKERS[role]}")
        key, st = self.enums[role]
        hit = [s for s in st if canon(s) == canon(name)]
        if not hit:
            raise Failed(f"{key[1]} has no member {name}")
        return self.ke.State(key, hit[0])

    def zero(self, mod_name, t):
        t = t.strip()
        if t.startswith("Maybe"): return None
        if t.startswith("Array") or t.startswith("Set"): return []
        if t.startswith("Int"): return 0
        if t == "Text": return ""
        if t == "Bool": return False
        base = t.split(" where ")[0].strip()
        m = self.w.mods[mod_name]
        k = self.kc.type_key(m, self.w.decls, base)
        if k is None:
            raise Failed(f"cannot give a zero value of {t}")
        d = self.w.decls[k]
        st = self.states(d)
        if st:
            return self.ke.State(k, st[0])
        rhs = " ".join(self.kc.strip_comment(l) for _, l in d.lines).split("=", 1)[1].strip()
        if rhs.startswith("{"):
            raise Failed(f"cannot give a zero value of record {t}")
        return self.zero(k[0], rhs)

    def build(self, name, data, status_role="ReportStatus"):
        d = self.decl(name)
        v = {}
        for f, t in d.fields.items():
            v[f] = self.convert(f, data[f], status_role) if f in data and data[f] is not None or f == "supervisor" and f in data \
                else self.zero(d.module, t)
        for f in ("reference", "owed"):                    # state-dependent fields, present only in their states
            if f not in d.fields and data.get(f) is not None:
                v[f] = data[f]
        return v

    def convert(self, field, v, status_role):
        if field == "category": return self.enum("Category", v)
        if field == "role": return self.enum("Role", v)
        if field == "currency": return self.enum("Currency", v)
        if field == "status": return self.enum(status_role, v)
        if field == "lines": return [self.build("Line", l) for l in v]
        if field == "approvals": return list(v)
        return v

    def arg(self, v, name=""):
        if name in ARG_ENUMS and isinstance(v, str):
            return self.enum(ARG_ENUMS[name], v)
        if isinstance(v, dict) and "category" in v:
            return self.build("Line", v)
        return v

    def plain(self, v):
        ke = self.ke
        if isinstance(v, ke.State): return v.name
        if isinstance(v, dict): return {k: self.plain(x) for k, x in v.items()}
        if isinstance(v, list): return [self.plain(x) for x in v]
        return v

    @staticmethod
    def full_fields(rhs):
        """Field name -> type text, refinement included (`position: Int where it in 1 to 50`), from a record's braces.
        brass's field table keeps only the type name, which would drop a field's own refinement."""
        depth, start, end = 0, rhs.index("{") + 1, None
        for i, ch in enumerate(rhs):
            depth += ch in "{(<["; depth -= ch in "})>]"
            if depth == 0 and i > 0:
                end = i; break
        body, parts, cur, depth = rhs[start:end], [], "", 0
        for ch in body:
            depth += ch in "{(<["; depth -= ch in "})>]"
            if ch == "," and depth == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        parts.append(cur)
        out = {}
        for part in parts:
            if ":" in part:
                name, t = part.split(":", 1)
                out[name.strip()] = t.strip()
        return out

    def boundary_ok(self, m, d, pn, pt, a):
        full = re.search(rf"\b{pn}\s*:\s*(.+?)(?=,\s*[a-z_]\w*\s*:|\)\s*->|\)\s*$)", self.kc.signature(d))
        return self.conforms(m, full.group(1).strip() if full else pt, a)

    def conforms(self, m, t, v, depth=0):
        """Does v meet type t as written in module m, refinements inside records and arrays included? The runtime's
        boundary checks the whole argument (spec: an entry point's arguments against its parameter types)."""
        t = t.strip()
        if depth > 12 or v is None and t.startswith("Maybe"):
            return True
        if t.startswith("Maybe<"):
            return self.conforms(m, t[6:-1], v, depth + 1)
        ev = self.ke.Evaluator(self.w, self.kc.strip_comment)
        if " where " in t and not t.startswith("{"):
            base = t.split(" where ", 1)[0].strip()
            return ev.satisfies(v, m, FakeDecl(t, ("", ""))) and self.conforms(m, base, v, depth + 1)
        if t.startswith("Array<") and isinstance(v, list):
            inner = t[6:t.rindex(">")]
            return all(self.conforms(m, inner, x, depth + 1) for x in v)
        k = self.kc.type_key(m, self.w.decls, t)
        if k is None:
            return True
        decl, dm = self.w.decls[k], self.w.mods[k[0]]
        if decl.kind != "type" or self.states(decl):
            return True
        rhs = " ".join(self.kc.strip_comment(l) for _, l in decl.lines).split("=", 1)[1].strip()
        if " where " in rhs and not ev.satisfies(v, dm, decl):
            return False
        if rhs.startswith("{") and isinstance(v, dict):
            return all(self.conforms(dm, ft, v[f], depth + 1) for f, ft in self.full_fields(rhs).items() if f in v)
        base = rhs.split(" where ", 1)[0].strip()
        return base == t or self.conforms(dm, base, v, depth + 1)

    def befores_hold(self, m, d, env):
        """An entry point's `before` lines, checked at the boundary before the body runs (spec 6: a failure is InvalidInput)."""
        ev = self.ke.Evaluator(self.w, self.kc.strip_comment)
        for _, l in d.lines:
            t = self.kc.strip_comment(l).strip()
            if t.startswith("before "):
                try:
                    if not ev.truth(ev.eval(self.ke.parse_expr(t[len("before "):]), m, dict(env))):
                        return False
                except self.ke.BrassError as e:
                    raise Failed(f"could not evaluate `{t}` at the boundary: {e}")
        return True

    def run(self, case):
        ke, rn = self.ke, self
        fx = case["store"]
        writes, ids, replies = [], list(fx.get("next_ids", ["n1", "n2"])), list(case["ledger"])
        Ok = lambda v: ke.Outcome(True, v)
        Err = lambda c: ke.Outcome(False, ke.Code(c))
        name = lambda v: v.name if isinstance(v, ke.State) else v

        def one(rows, build):
            return Ok(build(rows[0])) if rows else Err("NotFound")

        class FixtureHost(ke.Host):
            def __init__(self):
                super().__init__({})

            def answer(self, op, args, ev, m):
                self.trace.append((op, args))
                n, a = op.split(".", 1)[1], list(args)
                rep = lambda r: rn.build("Report", r)
                adv = lambda x: rn.build("Advance", x, "AdvanceStatus")
                if n == "staff": return one([s for s in fx["staff"] if s["badge"] == a[0]], lambda s: rn.build("Staff", s))
                if n == "report": return one([r for r in fx["reports"] if r["id"] == a[0]], rep)
                if n == "department": return one([d for d in fx["departments"] if d["id"] == a[0]], lambda d: rn.build("Department", d))
                if n == "reports_for": return Ok([rep(r) for r in fx["reports"] if r["department"] == a[0] and r["period"] == a[1]])
                if n == "submitted_reports": return Ok([rep(r) for r in fx["reports"] if r["status"] == "Submitted"])
                if n == "period_closed": return Ok(a[0] in fx["closed"])
                if n == "next_id": return Ok(ids.pop(0))
                if n == "rate":
                    return one([x for x in fx.get("rates", []) if canon(x["currency"]) == canon(name(a[0])) and x["period"] == a[1]], lambda x: x["rate"])
                if n == "advance": return one([x for x in fx.get("advances", []) if x["id"] == a[0]], adv)
                if n == "advances_for": return Ok([adv(x) for x in fx.get("advances", []) if x["department"] == a[0] and x["period"] == a[1]])
                if n == "paid_advances": return Ok([adv(x) for x in fx.get("advances", []) if x["status"] == "Paid"])
                if n == "save_report":
                    r = a[0]
                    writes.append({"op": "save_report", "id": r.get("id"), "status": name(r.get("status")), "approvals": list(r.get("approvals", [])),
                                   "reference": r.get("reference"), "badge": r.get("badge"), "department": r.get("department"),
                                   "period": r.get("period"), "line_count": len(r.get("lines", [])), "line_amounts": [l.get("amount") for l in r.get("lines", [])]})
                    return Ok("Done")
                if n == "save_advance":
                    x = a[0]
                    writes.append({"op": "save_advance", **{k: x.get(k) for k in ("id", "reference", "owed", "amount", "badge", "department", "period")},
                                   "status": name(x.get("status")), "approvals": list(x.get("approvals", []))})
                    return Ok("Done")
                if n == "append_audit":
                    e = a[0]
                    rec, frm, to = audit_fields(e.get)
                    writes.append({"op": "append_audit", "who": e.get("who"), "report": rec, "from": name(frm), "to": name(to), "reason": e.get("reason")})
                    return Ok("Done")
                if n == "close_period":
                    writes.append({"op": "close_period", "period": a[0]}); return Ok("Done")
                if n == "pay":
                    writes.append({"op": "pay", "badge": a[0], "amount": a[1], "key": a[2]})
                    r = replies.pop(0) if replies else "Unavailable"
                    return Err("Unavailable") if r == "Unavailable" else Ok(r)
                if n in REG_SAVES:
                    x = a[0]
                    writes.append({"op": n, **{k: rn.plain(x.get(k)) for k in REG_SAVES[n]}})
                    return Ok("Done")
                try:
                    ok, v = registry_read(n, [name(x) for x in a], fx, rn.build)
                except NotFoundInFixture:
                    return Err("NotFound")
                if ok:
                    return Ok(v)
                return Err("Unavailable")

        if case["op"] not in self.entries:
            raise Failed(f"entry point {case['op']} not in grants")
        m, d = self.entries[case["op"]]
        ev = ke.Evaluator(self.w, self.kc.strip_comment); ev.host_module = m
        host = FixtureHost()
        acc = {h.split(":")[0] for h in self.kc.holds_of(self.w, m, d)}
        args = []
        for pn, pt in d.params.items():
            if pn in acc:
                args.append(host); continue
            if pn not in case["args"]:
                raise Failed(f"{case['op']} takes {pn}, which the case does not give")
            a = self.arg(case["args"][pn], pn)
            try:
                ok = self.boundary_ok(m, d, pn, pt, a)
            except ke.BrassError as e:
                raise Failed(f"boundary check on {pn}: {e}")
            if not ok:
                return {"err": "InvalidInput"}, []
            args.append(a)
        pre = self.befores_hold(m, d, {pn: a for pn, a in zip([p for p in d.params if p not in acc], [a for a in args if a is not host])})
        if not pre:
            return {"err": "InvalidInput"}, []
        try:
            got = ev.call(m, d, args)
        except ke.BrassError as e:
            raise Failed(str(e))
        if not isinstance(got, ke.Outcome):
            raise Failed(f"entry point returned a plain value: {got!r}")
        if got.ok:
            return {"ok": self.plain(got.value)}, writes
        return {"err": got.value.name if isinstance(got.value, ke.Code) else str(got.value)}, writes


def main(argv):
    project, lang, cases_path = argv[0], argv[1], argv[2]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    cases = json.loads(Path(cases_path).read_text())
    try:
        runner = BrassRunner(project) if lang == "brass" else PyRunner(project)
    except Exception as e:                            # a tree that does not load is a finding, reported as such
        print(f"{lang}: tree did not load: {type(e).__name__}: {e}")
        return 2
    rows = []
    for c in cases:
        if only and c["id"] not in only:
            continue
        kind = "ran"
        try:
            result, writes = runner.run(c)
            problems = compare(c, result, writes)
        except Failed as e:
            problems, kind = [f"could not run: {e}"], "could not run"
        except Exception as e:                        # a tree that crashes on a case is a finding, reported as such
            problems, kind = [f"crashed: {type(e).__name__}: {e}"], "crashed"
        rows.append({"id": c["id"], "op": c["op"], "rule": c["rule"], "kind": c.get("kind", ""), "holds": not problems,
                     "run": kind, "problems": problems})
    held = sum(r["holds"] for r in rows)
    mode = "stand-in execution" if lang == "brass" else "executed"
    print(f"{lang}: {held} of {len(rows)} cases hold ({mode})")
    for r in rows:
        if not r["holds"]:
            print(f"  FAILS {r['id']} {r['op']} [{r['rule']}]")
            for p in r["problems"]:
                print(f"        {p}")
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps({"language": lang, "mode": mode, "held": held, "total": len(rows), "cases": rows}, indent=1))
    return 0 if held == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
