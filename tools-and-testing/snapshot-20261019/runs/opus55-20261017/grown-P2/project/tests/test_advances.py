import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk import advances, payment, queries, review
from desk.errors import Failure, FailureCode
from desk.ids import Category, Role
from desk.lines import Line
from desk.records import AdvanceStatus
from desk.reports import ReportStatus
from desk.staff import Department, Staff


class FakeStore:
    def __init__(self):
        self.staffs, self.depts, self.reports, self.advs, self.closed, self.audit, self.n = {}, {}, {}, {}, set(), [], 0

    def staff(self, b):
        if b not in self.staffs:
            raise Failure(FailureCode.NOT_FOUND, b)
        return self.staffs[b]
    def report(self, i): return self.reports[i]
    def department(self, i): return self.depts[i]
    def reports_for(self, d, p): return [r for r in self.reports.values() if r.department == d and r.period == p]
    def submitted_reports(self): return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED]
    def period_closed(self, p): return p in self.closed
    def next_id(self):
        self.n += 1
        return f"id{self.n}"
    def save_report(self, r): self.reports[r.id] = r
    def append_audit(self, e): self.audit.append(e)
    def close_period(self, p): self.closed.add(p)
    def advance(self, i):
        if i not in self.advs:
            raise Failure(FailureCode.NOT_FOUND, i)
        return self.advs[i]
    def advances_for(self, d, p): return [a for a in self.advs.values() if a.department == d and a.period == p]
    def paid_advances(self): return [a for a in self.advs.values() if a.status is AdvanceStatus.PAID]
    def save_advance(self, a): self.advs[a.id] = a


class FakeLedger:
    def __init__(self): self.calls = []
    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key))
        return f"ref-{key}"


def world(budget=1_000_000):
    s = FakeStore()
    for st in [Staff("w", "Worker", "D", "sup", Role.STAFF, True), Staff("sup", "Sup", "D", "dir", Role.SUPERVISOR, True),
               Staff("dir", "Dir", "D", None, Role.DIRECTOR, True), Staff("fin", "Fin", "F", None, Role.FINANCE, True)]:
        s.staffs[st.badge] = st
    s.depts["D"] = Department("D", "dir", budget)
    return s, FakeLedger()


def approved_report(s, amount, period=5, category=Category.TRAVEL):
    rid = review.open_draft(s, "w", period, Line(category, amount, "trip", True))
    review.submit(s, rid, "w")
    for b in ("sup", "dir", "fin"):
        if review.approve(s, rid, b) is ReportStatus.APPROVED:
            break
    return rid


class Tests(unittest.TestCase):
    def test_request_refusals(self):
        s, _ = world()
        with self.assertRaises(Failure) as c: advances.request_advance(s, "w", 5, 0)
        self.assertIs(c.exception.code, FailureCode.INVALID_INPUT)
        s.closed.add(5)
        with self.assertRaises(Failure) as c: advances.request_advance(s, "w", 5, 10)
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        s.staffs["w"] = Staff("w", "Worker", "D", "sup", Role.STAFF, False)
        with self.assertRaises(Failure) as c: advances.request_advance(s, "w", 6, 10)
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        self.assertEqual(s.audit, [])

    def test_two_step_chain_and_budget(self):
        s, _ = world(budget=100_000)
        aid = advances.request_advance(s, "w", 5, 60_000)
        self.assertEqual(s.audit, [])
        for bad in ("w", "dir", "fin"):
            with self.assertRaises(Failure) as c: advances.approve_advance(s, aid, bad)
            self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)
        self.assertIs(advances.approve_advance(s, aid, "sup"), AdvanceStatus.REQUESTED)
        self.assertEqual(s.advs[aid].approvals, ("sup",))
        self.assertIs(advances.approve_advance(s, aid, "dir"), AdvanceStatus.APPROVED)
        self.assertEqual(queries.spend(s, "D", 5), 60_000)
        st = queries.statement(s, "D", 5)
        self.assertEqual((st.spend, st.remaining, st.rows[-1].id, st.rows[-1].total, st.rows[-1].budgeted), (60_000, 40_000, aid, 60_000, 60_000))
        # a report that would now exceed the budget is refused at the last step by a non-finance approver
        rid = review.open_draft(s, "w", 5, Line(Category.TRAVEL, 45_000, "x", True))
        review.submit(s, rid, "w")
        with self.assertRaises(Failure) as c: review.approve(s, rid, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        # and so is a second advance
        aid2 = advances.request_advance(s, "w", 5, 45_000)
        with self.assertRaises(Failure) as c: advances.approve_advance(s, aid2, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)

    def test_closed_period_blocks_approval_not_payment(self):
        s, l = world()
        aid = advances.request_advance(s, "w", 5, 100)
        s.closed.add(5)
        with self.assertRaises(Failure) as c: advances.approve_advance(s, aid, "sup")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        s.closed.clear()
        advances.approve_advance(s, aid, "sup")
        s.closed.add(5)
        self.assertEqual(advances.pay_advance(s, l, aid, "fin"), f"ref-{aid}")
        self.assertEqual(l.calls, [("w", 100, aid)])
        self.assertEqual(s.advs[aid].status, AdvanceStatus.PAID)
        with self.assertRaises(Failure) as c: advances.pay_advance(s, l, aid, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        with self.assertRaises(Failure) as c: advances.pay_advance(s, l, aid, "sup")
        self.assertIs(c.exception.code, FailureCode.UNAUTHORIZED)

    def paid_advance(self, s, l, amount, period=5):
        aid = advances.request_advance(s, "w", period, amount)
        for b in ("sup", "dir", "fin"):
            if advances.approve_advance(s, aid, b) is AdvanceStatus.APPROVED:
                break
        advances.pay_advance(s, l, aid, "fin")
        return aid

    def test_settle_partial(self):
        s, l = world()
        aid = self.paid_advance(s, l, 10_000)
        rid = approved_report(s, 30_000)
        self.assertEqual(queries.spend(s, "D", 5), 40_000)
        ref = advances.pay_against(s, l, rid, aid, "fin")
        self.assertEqual(ref, f"ref-{rid}")
        self.assertEqual(l.calls[-1], ("w", 20_000, rid))
        self.assertEqual((s.advs[aid].status, s.advs[aid].owed), (AdvanceStatus.SETTLED, 0))
        self.assertEqual((s.reports[rid].status, s.reports[rid].reference), (ReportStatus.PAID, ref))
        self.assertEqual(queries.spend(s, "D", 5), 30_000)
        self.assertEqual([r.id for r in queries.statement(s, "D", 5).rows], [rid])
        self.assertEqual([(e.report, e.to_status, e.reason) for e in s.audit[-2:]],
                         [(rid, ReportStatus.PAID, "paid"), (aid, AdvanceStatus.SETTLED, "settled")])

    def test_settle_covers(self):
        s, l = world()
        aid = self.paid_advance(s, l, 30_000)
        rid = approved_report(s, 20_000)
        n = len(l.calls)
        self.assertEqual(advances.pay_against(s, l, rid, aid, "fin"), "settled")
        self.assertEqual(len(l.calls), n)
        self.assertEqual(s.reports[rid].reference, f"ref-{aid}")
        self.assertEqual(s.advs[aid].owed, 10_000)

    def test_settle_conflicts(self):
        s, l = world()
        s.staffs["v"] = Staff("v", "Other", "D", "sup", Role.STAFF, True)
        aid = self.paid_advance(s, l, 1_000)
        other_period = approved_report(s, 500, period=6)
        with self.assertRaises(Failure) as c: advances.pay_against(s, l, other_period, aid, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        rid = approved_report(s, 500)
        advances.pay_against(s, l, rid, aid, "fin")
        rid2 = approved_report(s, 500)
        with self.assertRaises(Failure) as c: advances.pay_against(s, l, rid2, aid, "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)
        with self.assertRaises(Failure) as c: advances.pay_against(s, l, rid, self.paid_advance(s, l, 5), "fin")
        self.assertIs(c.exception.code, FailureCode.CONFLICT)          # report already paid

    def test_outstanding(self):
        s, l = world()
        a5 = self.paid_advance(s, l, 100, period=5)
        a6 = self.paid_advance(s, l, 100, period=6)
        self.assertEqual(advances.outstanding_advances(s, 7), [])
        self.assertEqual(advances.outstanding_advances(s, 8), [a5])
        self.assertEqual(advances.outstanding_advances(s, 9), [a5, a6])

    def test_baseline_report_flow_unchanged(self):
        s, l = world()
        rid = approved_report(s, 600_000, category=Category.CONTAINMENT)
        self.assertEqual(payment.pay(s, l, rid, "fin"), f"ref-{rid}")
        self.assertEqual(queries.spend(s, "D", 5), 600_000)


if __name__ == "__main__":
    unittest.main()
