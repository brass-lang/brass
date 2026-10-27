import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from desk import advances, review, payment, queries
from desk.errors import Failure, FailureCode
from desk.ids import Role, Category
from desk.lines import Line
from desk.records import AdvanceStatus
from desk.reports import ReportStatus
from desk.staff import Staff, Department


class FakeStore:
    def __init__(self):
        self.staffs, self.depts, self.reports, self.advs, self.audit, self.closed, self.n = {}, {}, {}, {}, [], set(), 0
    def staff(self, b):
        if b not in self.staffs: raise Failure(FailureCode.NOT_FOUND, b)
        return self.staffs[b]
    def report(self, i):
        if i not in self.reports: raise Failure(FailureCode.NOT_FOUND, i)
        return self.reports[i]
    def department(self, i): return self.depts[i]
    def reports_for(self, d, p): return [r for r in self.reports.values() if r.department == d and r.period == p]
    def submitted_reports(self): return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED]
    def period_closed(self, p): return p in self.closed
    def next_id(self): self.n += 1; return f"id{self.n}"
    def save_report(self, r): self.reports[r.id] = r
    def append_audit(self, e): self.audit.append(e)
    def close_period(self, p): self.closed.add(p)
    def advance(self, i):
        if i not in self.advs: raise Failure(FailureCode.NOT_FOUND, i)
        return self.advs[i]
    def advances_for(self, d, p): return [a for a in self.advs.values() if a.department == d and a.period == p]
    def paid_advances(self): return [a for a in self.advs.values() if a.status is AdvanceStatus.PAID]
    def save_advance(self, a): self.advs[a.id] = a


class FakeLedger:
    def __init__(self): self.calls = []
    def pay(self, badge, amount, key): self.calls.append((badge, amount, key)); return f"ref{len(self.calls)}"


def setup(budget=10_000_000):
    s = FakeStore()
    for st in [Staff("dir", "D", "ops", None, Role.DIRECTOR, True), Staff("sup", "S", "ops", "dir", Role.SUPERVISOR, True),
               Staff("bob", "B", "ops", "sup", Role.STAFF, True), Staff("fin", "F", "fin", None, Role.FINANCE, True)]:
        s.staffs[st.badge] = st
    s.depts["ops"] = Department("ops", "dir", budget)
    return s, FakeLedger()


def report(s, amount, period=5):
    rid = review.open_draft(s, "bob", period, Line(Category.TRAVEL, amount, "trip", True))
    review.submit(s, rid, "bob")
    return rid


class T(unittest.TestCase):
    def test_flow_partial(self):
        s, l = setup()
        a = advances.request_advance(s, "bob", 5, 100_000)
        self.assertEqual(s.audit, [])
        with self.assertRaises(Failure) as c: advances.approve_advance(s, a, "dir")
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        self.assertIs(advances.approve_advance(s, a, "sup"), AdvanceStatus.REQUESTED)
        self.assertIs(advances.approve_advance(s, a, "dir"), AdvanceStatus.APPROVED)
        self.assertEqual(queries.spend(s, "ops", 5), 100_000)
        self.assertEqual(advances.pay_advance(s, l, a, "fin"), "ref1")
        self.assertEqual(l.calls, [("bob", 100_000, a)])
        st = queries.statement(s, "ops", 5)
        self.assertEqual(st.rows[0].id, a)
        rid = report(s, 140_000)
        review.approve(s, rid, "sup"); review.approve(s, rid, "dir")
        self.assertEqual(queries.spend(s, "ops", 5), 240_000)
        self.assertEqual(advances.outstanding_advances(s, 8), [a])
        self.assertEqual(advances.outstanding_advances(s, 7), [])
        self.assertEqual(advances.pay_against(s, l, rid, a, "fin"), "ref2")
        self.assertEqual(l.calls[-1], ("bob", 40_000, rid))
        self.assertEqual(s.advs[a].status, AdvanceStatus.SETTLED); self.assertEqual(s.advs[a].owed, 0)
        self.assertEqual(s.reports[rid].reference, "ref2")
        self.assertEqual(queries.spend(s, "ops", 5), 140_000)
        self.assertEqual([(e.report, e.from_status, e.to_status) for e in s.audit][-2:],
                         [(rid, ReportStatus.APPROVED, ReportStatus.PAID), (a, AdvanceStatus.PAID, AdvanceStatus.SETTLED)])
        with self.assertRaises(Failure) as c: advances.pay_against(s, l, rid, a, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)

    def test_covered(self):
        s, l = setup()
        a = advances.request_advance(s, "bob", 5, 30_000)
        advances.approve_advance(s, a, "sup"); advances.pay_advance(s, l, a, "fin")
        rid = report(s, 20_000); review.approve(s, rid, "sup")
        self.assertEqual(advances.pay_against(s, l, rid, a, "fin"), "settled")
        self.assertEqual(len(l.calls), 1)
        self.assertEqual(s.reports[rid].reference, "ref1"); self.assertEqual(s.advs[a].owed, 10_000)

    def test_budget(self):
        s, l = setup(budget=40_000)
        a = advances.request_advance(s, "bob", 5, 30_000)
        advances.approve_advance(s, a, "sup")
        rid = report(s, 20_000)
        with self.assertRaises(Failure) as c: review.approve(s, rid, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        b = advances.request_advance(s, "bob", 5, 600_000)
        advances.approve_advance(s, b, "sup"); advances.approve_advance(s, b, "dir")
        self.assertIs(advances.approve_advance(s, b, "fin"), AdvanceStatus.APPROVED)
        self.assertEqual(s.audit[-1].reason, "approved; budget override")

    def test_refusals(self):
        s, l = setup()
        with self.assertRaises(Failure) as c: advances.request_advance(s, "bob", 5, 0)
        self.assertIs(c.exception.code, FailureCode.INVALID_INPUT)
        s.closed.add(6)
        with self.assertRaises(Failure) as c: advances.request_advance(s, "bob", 6, 5)
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        a = advances.request_advance(s, "bob", 5, 5)
        with self.assertRaises(Failure) as c: advances.approve_advance(s, a, "bob")
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        with self.assertRaises(Failure) as c: advances.pay_advance(s, l, a, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        advances.approve_advance(s, a, "sup")
        s.closed.add(5)
        advances.pay_advance(s, l, a, "fin")   # closed period does not block payment


unittest.main()
