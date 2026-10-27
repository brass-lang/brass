import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk import review, payment, queries
from desk.advances import AdvanceStatus
from desk.audit import Entry
from desk.errors import Failure, FailureCode
from desk.ids import Role, Category
from desk.lines import Line
from desk.reports import ReportStatus
from desk.staff import Staff, Department


class FakeStore:
    def __init__(self):
        self.staffs, self.depts, self.reports, self.advs = {}, {}, {}, {}
        self.closed, self.audit, self.n = set(), [], 0
    def staff(self, b):
        if b not in self.staffs: raise Failure(FailureCode.NOT_FOUND, b)
        return self.staffs[b]
    def report(self, id): return self.reports[id]
    def department(self, id): return self.depts[id]
    def reports_for(self, d, p): return [r for r in self.reports.values() if r.department == d and r.period == p]
    def submitted_reports(self): return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED]
    def period_closed(self, p): return p in self.closed
    def next_id(self): self.n += 1; return f"id{self.n}"
    def save_report(self, r): self.reports[r.id] = r
    def append_audit(self, e): self.audit.append(e)
    def close_period(self, p): self.closed.add(p)
    def advance(self, id):
        if id not in self.advs: raise Failure(FailureCode.NOT_FOUND, id)
        return self.advs[id]
    def advances_for(self, d, p): return [a for a in self.advs.values() if a.department == d and a.period == p]
    def paid_advances(self): return [a for a in self.advs.values() if a.status is AdvanceStatus.PAID]
    def save_advance(self, a): self.advs[a.id] = a


class FakeLedger:
    def __init__(self): self.calls = []
    def pay(self, badge, amount, key): self.calls.append((badge, amount, key)); return f"L{len(self.calls)}"


def setup(budget=1_000_000):
    s = FakeStore()
    for st in [Staff("dir", "D", "vet", None, Role.DIRECTOR, True), Staff("sup", "S", "vet", "dir", Role.SUPERVISOR, True),
               Staff("joe", "J", "vet", "sup", Role.STAFF, True), Staff("fin", "F", "acct", None, Role.FINANCE, True)]:
        s.staffs[st.badge] = st
    s.depts["vet"] = Department("vet", "dir", budget)
    return s, FakeLedger()


def approved_report(s, amount, period=5):
    rid = review.open_draft(s, "joe", period, Line(Category.TRAVEL, amount, "x", True))
    review.submit(s, rid, "joe")
    review.approve(s, rid, "sup")
    if amount > 50_000: review.approve(s, rid, "dir")
    return rid


class T(unittest.TestCase):
    def test_flow_covered(self):
        s, l = setup()
        a = review.request_advance(s, "joe", 5, 60_000)
        self.assertEqual(s.audit, [])
        self.assertEqual(review.approve_advance(s, a, "sup"), AdvanceStatus.REQUESTED)
        with self.assertRaises(Failure) as c: review.approve_advance(s, a, "sup")
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        self.assertEqual(review.approve_advance(s, a, "dir"), AdvanceStatus.APPROVED)
        self.assertEqual(queries.spend(s, "vet", 5), 60_000)
        self.assertEqual(payment.pay_advance(s, l, a, "fin"), "L1")
        self.assertEqual(l.calls, [("joe", 60_000, a)])
        st = queries.statement(s, "vet", 5)
        self.assertEqual(st.spend, 60_000); self.assertEqual(st.rows[0].total, 60_000)
        rid = approved_report(s, 40_000)
        self.assertEqual(queries.spend(s, "vet", 5), 100_000)
        self.assertEqual(queries.outstanding_advances(s, 8), [a])
        self.assertEqual(queries.outstanding_advances(s, 7), [])
        self.assertEqual(payment.pay_against(s, l, rid, a, "fin"), "settled")
        self.assertEqual(len(l.calls), 1)
        self.assertEqual(s.reports[rid].reference, "L1"); self.assertIs(s.reports[rid].status, ReportStatus.PAID)
        self.assertEqual(s.advs[a].owed, 20_000); self.assertIs(s.advs[a].status, AdvanceStatus.SETTLED)
        self.assertEqual(queries.spend(s, "vet", 5), 40_000)
        self.assertEqual(queries.outstanding_advances(s, 8), [])
        with self.assertRaises(Failure) as c: payment.pay_against(s, l, rid, a, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        print(*s.audit, sep="\n")

    def test_partial_and_budget(self):
        s, l = setup(budget=50_000)
        a = review.request_advance(s, "joe", 5, 30_000)
        review.approve_advance(s, a, "sup")
        b = review.request_advance(s, "joe", 5, 30_000)
        with self.assertRaises(Failure) as c: review.approve_advance(s, b, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        payment.pay_advance(s, l, a, "fin")
        over = review.open_draft(s, "joe", 5, Line(Category.TRAVEL, 20_001, "x", True))
        review.submit(s, over, "joe")
        with self.assertRaises(Failure) as c: review.approve(s, over, "sup")   # paid advance counts against reports
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        rid = review.open_draft(s, "joe", 5, Line(Category.TRAVEL, 20_000, "x", True))
        review.submit(s, rid, "joe")
        self.assertIs(review.approve(s, rid, "sup"), ReportStatus.APPROVED)

    def test_finance_override(self):
        s, l = setup(budget=100)
        a = review.request_advance(s, "joe", 5, 600_000)
        review.approve_advance(s, a, "sup"); review.approve_advance(s, a, "dir")
        self.assertIs(review.approve_advance(s, a, "fin"), AdvanceStatus.APPROVED)
        self.assertEqual(s.audit[-1].reason, "approved; budget override")
        self.assertEqual(queries.statement(s, "vet", 5).remaining, -599_900)
    def test_partial(self):
        s, l = setup()
        a = review.request_advance(s, "joe", 5, 10_000)
        review.approve_advance(s, a, "sup"); payment.pay_advance(s, l, a, "fin")
        rid = approved_report(s, 25_000)
        self.assertEqual(payment.pay_against(s, l, rid, a, "fin"), "L2")
        self.assertEqual(l.calls[1], ("joe", 15_000, rid))
        self.assertEqual(s.advs[a].owed, 0)
        self.assertEqual(s.reports[rid].reference, "L2")

    def test_refusals(self):
        s, l = setup()
        for amt in (0, -1):
            with self.assertRaises(Failure) as c: review.request_advance(s, "joe", 5, amt)
            self.assertIs(c.exception.code, FailureCode.INVALID_INPUT)
        a = review.request_advance(s, "joe", 5, 100)
        with self.assertRaises(Failure) as c: review.approve_advance(s, a, "joe")
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        with self.assertRaises(Failure) as c: payment.pay_advance(s, l, a, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        s.closed.add(5)
        with self.assertRaises(Failure) as c: review.approve_advance(s, a, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        with self.assertRaises(Failure) as c: review.request_advance(s, "joe", 5, 100)
        self.assertIs(c.exception.code, FailureCode.CONFLICT)


if __name__ == "__main__":
    unittest.main()
