import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk import advances, payment, queries, review
from desk.errors import Failure, FailureCode
from desk.ids import Category, Role
from desk.lines import Line
from desk.records import AdvanceStatus
from desk.reports import ReportStatus
from desk.staff import Department, Staff


class MemStore:
    def __init__(self, staff, departments):
        self._staff = {s.badge: s for s in staff}
        self._depts = {d.id: d for d in departments}
        self.reports, self.advs, self.audit, self.closed, self._n = {}, {}, [], set(), 0

    def staff(self, b):
        if b not in self._staff:
            raise Failure(FailureCode.NOT_FOUND, b)
        return self._staff[b]

    def report(self, id):
        if id not in self.reports:
            raise Failure(FailureCode.NOT_FOUND, id)
        return self.reports[id]

    def department(self, id): return self._depts[id]
    def reports_for(self, d, p): return [r for r in self.reports.values() if r.department == d and r.period == p]
    def submitted_reports(self): return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED]
    def period_closed(self, p): return p in self.closed
    def next_id(self):
        self._n += 1
        return f"id{self._n}"
    def save_report(self, r): self.reports[r.id] = r
    def append_audit(self, e): self.audit.append(e)
    def close_period(self, p): self.closed.add(p)

    def advance(self, id):
        if id not in self.advs:
            raise Failure(FailureCode.NOT_FOUND, id)
        return self.advs[id]
    def advances_for(self, d, p): return [a for a in self.advs.values() if a.department == d and a.period == p]
    def paid_advances(self): return [a for a in self.advs.values() if a.status is AdvanceStatus.PAID]
    def save_advance(self, a): self.advs[a.id] = a


class MemLedger:
    def __init__(self): self.calls = []
    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key))
        return f"L{len(self.calls)}"


def world(budget=1_000_000):
    staff = [
        Staff("alan", "Alan", "D", "sup", Role.STAFF, True),
        Staff("sup", "Sup", "D", "dir", Role.SUPERVISOR, True),
        Staff("dir", "Dir", "D", None, Role.DIRECTOR, True),
        Staff("fin", "Fin", "F", None, Role.FINANCE, True),
        Staff("gone", "Gone", "D", "sup", Role.STAFF, False),
    ]
    return MemStore(staff, [Department("D", "dir", budget), Department("F", "fin", 10**9)]), MemLedger()


def approved_report(s, amount, period=5):
    rid = review.open_draft(s, "alan", period, Line(Category.TRAVEL, amount, "trip", True))
    review.submit(s, rid, "alan")
    for who in ("sup", "dir", "fin")[:3]:
        if review.approve(s, rid, who) is ReportStatus.APPROVED:
            break
    return rid


class Advances(unittest.TestCase):
    def code(self, fn, *args):
        with self.assertRaises(Failure) as c:
            fn(*args)
        return c.exception.code

    def test_request_refusals(self):
        s, _ = world()
        self.assertIs(self.code(advances.request_advance, s, "gone", 5, 100), FailureCode.UNAUTHORIZED)
        self.assertIs(self.code(advances.request_advance, s, "alan", 5, 0), FailureCode.INVALID_INPUT)
        s.closed.add(5)
        self.assertIs(self.code(advances.request_advance, s, "alan", 5, 100), FailureCode.CONFLICT)
        self.assertEqual(s.advs, {})
        self.assertEqual(s.audit, [])

    def test_chain_pay_and_settle_partial(self):
        s, l = world()
        aid = advances.request_advance(s, "alan", 5, 60_000)
        self.assertEqual(s.audit, [])
        self.assertIs(self.code(advances.approve_advance, s, aid, "alan"), FailureCode.UNAUTHORIZED)
        self.assertIs(self.code(advances.approve_advance, s, aid, "dir"), FailureCode.UNAUTHORIZED)
        self.assertIs(advances.approve_advance(s, aid, "sup"), AdvanceStatus.REQUESTED)
        self.assertEqual(queries.spend(s, "D", 5), 0)
        self.assertIs(advances.approve_advance(s, aid, "dir"), AdvanceStatus.APPROVED)
        self.assertEqual(s.advs[aid].approvals, ("sup",))
        self.assertEqual(queries.spend(s, "D", 5), 60_000)
        self.assertIs(self.code(advances.pay_advance, s, l, aid, "dir"), FailureCode.UNAUTHORIZED)
        s.closed.add(5)                                 # closing does not block paying
        self.assertEqual(advances.pay_advance(s, l, aid, "fin"), "L1")
        s.closed.discard(5)
        self.assertEqual(l.calls, [("alan", 60_000, aid)])
        self.assertEqual(s.advs[aid].reference, "L1")
        st = queries.statement(s, "D", 5)
        self.assertEqual((st.spend, st.remaining, len(st.rows)), (60_000, 940_000, 1))
        self.assertEqual(st.rows[0].total, 60_000)

        rid = approved_report(s, 80_000)
        self.assertEqual(queries.spend(s, "D", 5), 140_000)
        self.assertEqual(advances.pay_against(s, l, rid, aid, "fin"), "L2")
        self.assertEqual(l.calls[-1], ("alan", 20_000, rid))
        self.assertEqual((s.reports[rid].status, s.reports[rid].reference), (ReportStatus.PAID, "L2"))
        self.assertEqual((s.advs[aid].status, s.advs[aid].owed), (AdvanceStatus.SETTLED, 0))
        self.assertEqual(queries.spend(s, "D", 5), 80_000)
        self.assertEqual(len(queries.statement(s, "D", 5).rows), 1)
        self.assertEqual([(e.report, e.from_status, e.to_status, e.reason) for e in s.audit if e.report == aid], [
            (aid, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED, "approved; awaiting the next approver"),
            (aid, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED, "approved"),
            (aid, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"),
            (aid, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"),
        ])
        # settled once only
        rid2 = approved_report(s, 1_000)
        self.assertIs(self.code(advances.pay_against, s, l, rid2, aid, "fin"), FailureCode.CONFLICT)

    def test_settle_covering(self):
        s, l = world()
        aid = advances.request_advance(s, "alan", 5, 30_000)
        advances.approve_advance(s, aid, "sup")
        advances.pay_advance(s, l, aid, "fin")
        rid = approved_report(s, 25_000)
        self.assertEqual(advances.pay_against(s, l, rid, aid, "fin"), "settled")
        self.assertEqual(len(l.calls), 1)
        self.assertEqual(s.reports[rid].reference, "L1")
        self.assertEqual(s.advs[aid].owed, 5_000)

    def test_settle_conflicts(self):
        s, l = world()
        aid = advances.request_advance(s, "alan", 5, 30_000)
        rid_other_period = approved_report(s, 1_000, period=6)
        advances.approve_advance(s, aid, "sup")
        self.assertIs(self.code(advances.pay_against, s, l, rid_other_period, aid, "fin"), FailureCode.CONFLICT)  # not paid
        advances.pay_advance(s, l, aid, "fin")
        self.assertIs(self.code(advances.pay_against, s, l, rid_other_period, aid, "fin"), FailureCode.CONFLICT)
        self.assertEqual(len(l.calls), 1)

    def test_budget(self):
        s, l = world(budget=40_000)
        aid = advances.request_advance(s, "alan", 5, 30_000)
        advances.approve_advance(s, aid, "sup")
        rid = review.open_draft(s, "alan", 5, Line(Category.TRAVEL, 20_000, "trip", True))
        review.submit(s, rid, "alan")
        self.assertIs(self.code(review.approve, s, rid, "sup"), FailureCode.CONFLICT)
        a2 = advances.request_advance(s, "alan", 5, 20_000)
        self.assertIs(self.code(advances.approve_advance, s, a2, "sup"), FailureCode.CONFLICT)

    def test_outstanding(self):
        s, l = world()
        ids = []
        for p in (1, 2, 3):
            a = advances.request_advance(s, "alan", p, 100)
            advances.approve_advance(s, a, "sup")
            advances.pay_advance(s, l, a, "fin")
            ids.append(a)
        self.assertEqual(advances.outstanding_advances(s, 4), [ids[0]])
        self.assertEqual(advances.outstanding_advances(s, 6), ids)

    def test_baseline_report_pay(self):
        s, l = world()
        rid = approved_report(s, 1_000)
        self.assertEqual(payment.pay(s, l, rid, "fin"), "L1")
        self.assertEqual(queries.spend(s, "D", 5), 1_000)


if __name__ == "__main__":
    unittest.main()
