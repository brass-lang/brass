import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk import payment, queries, review
from desk.advances import AdvanceStatus
from desk.audit import Entry
from desk.errors import Failure, FailureCode
from desk.ids import Category, Role
from desk.lines import Line
from desk.reports import ReportStatus
from desk.staff import Department, Staff


class MemStore:
    def __init__(self, staff, depts):
        self._staff = {s.badge: s for s in staff}
        self._depts = {d.id: d for d in depts}
        self.reports, self.advances, self.audit, self.closed, self.n = {}, {}, [], set(), 0

    def staff(self, b):
        if b not in self._staff: raise Failure(FailureCode.NOT_FOUND, b)
        return self._staff[b]
    def report(self, id):
        if id not in self.reports: raise Failure(FailureCode.NOT_FOUND, id)
        return self.reports[id]
    def department(self, id): return self._depts[id]
    def reports_for(self, d, p): return [r for r in self.reports.values() if r.department == d and r.period == p]
    def submitted_reports(self): return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED]
    def period_closed(self, p): return p in self.closed
    def next_id(self): self.n += 1; return f"X{self.n}"
    def save_report(self, r): self.reports[r.id] = r
    def append_audit(self, e): self.audit.append(e)
    def close_period(self, p): self.closed.add(p)
    def advance(self, id):
        if id not in self.advances: raise Failure(FailureCode.NOT_FOUND, id)
        return self.advances[id]
    def advances_for(self, d, p): return [a for a in self.advances.values() if a.department == d and a.period == p]
    def paid_advances(self): return [a for a in self.advances.values() if a.status is AdvanceStatus.PAID]
    def save_advance(self, a): self.advances[a.id] = a


class MemLedger:
    def __init__(self): self.calls = []
    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key)); return f"L{len(self.calls)}"


def world(budget=1_000_000):
    staff = [
        Staff("fin", "Fin", "D", None, Role.FINANCE, True),
        Staff("dir", "Dir", "D", None, Role.DIRECTOR, True),
        Staff("sup", "Sup", "D", "dir", Role.SUPERVISOR, True),
        Staff("s1", "S1", "D", "sup", Role.STAFF, True),
        Staff("s2", "S2", "D", "sup", Role.STAFF, True),
        Staff("gone", "Gone", "D", "sup", Role.STAFF, False),
    ]
    return MemStore(staff, [Department("D", "dir", budget)]), MemLedger()


def report(store, badge, period, amount):
    id = review.open_draft(store, badge, period, Line(Category.TRAVEL, amount, "trip", True))
    review.submit(store, id, badge)
    while review.approve(store, id, _next(store, id)) is not ReportStatus.APPROVED:
        pass
    return id


def _next(store, id):
    for b in ("sup", "dir", "fin"):
        if review.may_act(store, store.report(id), store.staff(b)):
            return b


class T(unittest.TestCase):
    def code(self, code, f, *a):
        with self.assertRaises(Failure) as c: f(*a)
        self.assertIs(c.exception.code, code)

    def test_request(self):
        s, _ = world()
        self.code(FailureCode.INVALID_INPUT, review.request_advance, s, "s1", 5, 0)
        self.code(FailureCode.UNAUTHORIZED, review.request_advance, s, "gone", 5, 10)
        s.closed.add(4)
        self.code(FailureCode.CONFLICT, review.request_advance, s, "s1", 4, 10)
        id = review.request_advance(s, "s1", 5, 10)
        a = s.advance(id)
        self.assertEqual((a.department, a.status, a.approvals, a.reference, a.owed), ("D", AdvanceStatus.REQUESTED, (), None, None))
        self.assertEqual(s.audit, [])

    def test_approve_chain_and_budget(self):
        s, l = world(budget=120_000)
        id = review.request_advance(s, "s1", 5, 100_000)
        self.code(FailureCode.UNAUTHORIZED, review.approve_advance, s, id, "dir")
        self.code(FailureCode.UNAUTHORIZED, review.approve_advance, s, id, "s1")
        self.assertIs(review.approve_advance(s, id, "sup"), AdvanceStatus.REQUESTED)
        self.assertIs(review.approve_advance(s, id, "dir"), AdvanceStatus.APPROVED)
        self.code(FailureCode.CONFLICT, review.approve_advance, s, id, "dir")
        self.assertEqual(s.advance(id).approvals, ("sup",))
        self.assertEqual(queries.spend(s, "D", 5), 100_000)
        # a report now exceeding the budget is refused at the last step for non-finance
        rid = review.open_draft(s, "s2", 5, Line(Category.TRAVEL, 120_000, "x", True))
        review.submit(s, rid, "s2")
        review.approve(s, rid, "sup")
        self.code(FailureCode.CONFLICT, review.approve, s, rid, "dir")
        # advance over budget: refused for director
        id2 = review.request_advance(s, "s2", 5, 40_000)
        self.code(FailureCode.CONFLICT, review.approve_advance, s, id2, "sup")  # one step only; sup is last
        # closed period
        id3 = review.request_advance(s, "s2", 5, 10)
        s.closed.add(5)
        self.code(FailureCode.CONFLICT, review.approve_advance, s, id3, "sup")
        # paying is not blocked by closed period
        self.assertEqual(payment.pay_advance(s, l, id, "fin"), "L1")
        self.assertEqual(l.calls, [("s1", 100_000, id)])
        self.assertEqual(s.audit[-1], Entry("fin", id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
        st = queries.statement(s, "D", 5)
        self.assertEqual((st.spend, st.remaining, st.rows[-1].id, st.rows[-1].total), (100_000, 20_000, id, 100_000))

    def test_finance_override_at_third_step(self):
        s, _ = world(budget=100)
        id = review.request_advance(s, "s1", 5, 600_000)
        review.approve_advance(s, id, "sup"); review.approve_advance(s, id, "dir")
        self.assertIs(review.approve_advance(s, id, "fin"), AdvanceStatus.APPROVED)
        self.assertEqual(s.audit[-1].reason, "approved; budget override")
        self.assertEqual(queries.statement(s, "D", 5).remaining, 100 - 600_000)

    def _paid_advance(self, s, l, badge, period, amount):
        id = review.request_advance(s, badge, period, amount)
        review.approve_advance(s, id, "sup")
        payment.pay_advance(s, l, id, "fin")
        return id

    def test_settle_partial(self):
        s, l = world()
        aid = self._paid_advance(s, l, "s1", 5, 10_000)
        rid = report(s, "s1", 5, 15_000)
        self.assertEqual(queries.spend(s, "D", 5), 25_000)
        self.assertEqual(payment.pay_against(s, l, rid, aid, "fin"), "L2")
        self.assertEqual(l.calls[-1], ("s1", 5_000, rid))
        self.assertEqual((s.report(rid).status, s.report(rid).reference), (ReportStatus.PAID, "L2"))
        self.assertEqual((s.advance(aid).status, s.advance(aid).owed, s.advance(aid).reference), (AdvanceStatus.SETTLED, 0, "L1"))
        self.assertEqual(s.audit[-2:], [Entry("fin", rid, ReportStatus.APPROVED, ReportStatus.PAID, "paid"),
                                        Entry("fin", aid, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled")])
        self.assertEqual(queries.spend(s, "D", 5), 15_000)
        self.assertEqual(len(queries.statement(s, "D", 5).rows), 1)
        self.code(FailureCode.CONFLICT, payment.pay_against, s, l, report(s, "s1", 5, 10), aid, "fin")

    def test_settle_covered(self):
        s, l = world()
        aid = self._paid_advance(s, l, "s1", 5, 10_000)
        rid = report(s, "s1", 5, 4_000)
        self.assertEqual(payment.pay_against(s, l, rid, aid, "fin"), "settled")
        self.assertEqual(len(l.calls), 1)
        self.assertEqual(s.report(rid).reference, "L1")
        self.assertEqual(s.advance(aid).owed, 6_000)

    def test_settle_conflicts(self):
        s, l = world()
        aid = self._paid_advance(s, l, "s1", 5, 10_000)
        self.code(FailureCode.CONFLICT, payment.pay_against, s, l, report(s, "s2", 5, 10), aid, "fin")
        self.code(FailureCode.CONFLICT, payment.pay_against, s, l, report(s, "s1", 6, 10), aid, "fin")
        unpaid = review.request_advance(s, "s1", 5, 10)
        self.code(FailureCode.CONFLICT, payment.pay_against, s, l, report(s, "s1", 5, 10), unpaid, "fin")
        self.code(FailureCode.UNAUTHORIZED, payment.pay_against, s, l, report(s, "s1", 5, 10), aid, "dir")

    def test_outstanding(self):
        s, l = world()
        a5 = self._paid_advance(s, l, "s1", 5, 10)
        a6 = self._paid_advance(s, l, "s1", 6, 10)
        self.assertEqual(queries.outstanding_advances(s, 7), [])
        self.assertEqual(queries.outstanding_advances(s, 8), [a5])
        self.assertEqual(queries.outstanding_advances(s, 9), [a5, a6])


if __name__ == "__main__":
    unittest.main()
