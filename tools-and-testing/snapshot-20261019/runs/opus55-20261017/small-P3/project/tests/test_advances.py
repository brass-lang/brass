import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk import review, payment, queries
from desk.advances import AdvanceStatus
from desk.errors import Failure, FailureCode
from desk.ids import Role, Category
from desk.lines import Line
from desk.reports import ReportStatus
from desk.staff import Staff, Department


class FakeStore:
    def __init__(self):
        self.staffs, self.depts, self.reports, self.advs = {}, {}, {}, {}
        self.audit, self.closed, self.n = [], set(), 0
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
    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key)); return f"L{len(self.calls)}"


def setup(budget=1_000_000):
    s = FakeStore()
    for b, sup, role in [("dir", None, Role.DIRECTOR), ("sup", "dir", Role.SUPERVISOR), ("st", "sup", Role.STAFF),
                         ("fin", None, Role.FINANCE)]:
        s.staffs[b] = Staff(b, b, "D", sup, role, True)
    s.depts["D"] = Department("D", "dir", budget)
    return s, FakeLedger()


def code(fn):
    try: fn()
    except Failure as f: return f.code
    return None


def approved_report(s, amount, period=5):
    rid = review.open_draft(s, "st", period, Line(Category.TRAVEL, amount, "x", True))
    review.submit(s, rid, "st")
    for who in ("sup", "dir", "fin"):
        if review.approve(s, rid, who) is ReportStatus.APPROVED: break
    return rid


class T(unittest.TestCase):
    def test_flow_partial(self):
        s, L = setup()
        aid = review.request_advance(s, "st", 5, 60_000)
        self.assertEqual(s.audit, [])
        self.assertEqual(code(lambda: review.approve_advance(s, aid, "st")), FailureCode.UNAUTHORIZED)
        self.assertEqual(code(lambda: review.approve_advance(s, aid, "dir")), FailureCode.UNAUTHORIZED)
        self.assertEqual(review.approve_advance(s, aid, "sup"), AdvanceStatus.REQUESTED)
        self.assertEqual(review.approve_advance(s, aid, "dir"), AdvanceStatus.APPROVED)
        self.assertEqual(queries.spend(s, "D", 5), 60_000)
        self.assertEqual(code(lambda: payment.pay_advance(s, L, aid, "sup")), FailureCode.UNAUTHORIZED)
        self.assertEqual(payment.pay_advance(s, L, aid, "fin"), "L1")
        self.assertEqual(L.calls, [("st", 60_000, aid)])
        self.assertEqual(queries.outstanding_advances(s, 7), [])
        self.assertEqual(queries.outstanding_advances(s, 8), [aid])
        rid = approved_report(s, 100_000)
        st = queries.statement(s, "D", 5)
        self.assertEqual(st.spend, 160_000)
        self.assertEqual([r.id for r in st.rows], [rid, aid])
        self.assertEqual(payment.pay_against(s, L, rid, aid, "fin"), "L2")
        self.assertEqual(L.calls[-1], ("st", 40_000, rid))
        a = s.advs[aid]
        self.assertEqual((a.status, a.owed, a.reference), (AdvanceStatus.SETTLED, 0, "L1"))
        self.assertEqual((s.reports[rid].status, s.reports[rid].reference), (ReportStatus.PAID, "L2"))
        self.assertEqual(queries.spend(s, "D", 5), 100_000)
        self.assertEqual(code(lambda: payment.pay_against(s, L, rid, aid, "fin")), FailureCode.CONFLICT)
        for e in s.audit: print(e)

    def test_covers(self):
        s, L = setup()
        aid = review.request_advance(s, "st", 5, 30_000)
        review.approve_advance(s, aid, "sup")
        payment.pay_advance(s, L, aid, "fin")
        rid = approved_report(s, 20_000)
        self.assertEqual(payment.pay_against(s, L, rid, aid, "fin"), "settled")
        self.assertEqual(len(L.calls), 1)
        self.assertEqual(s.reports[rid].reference, "L1")
        self.assertEqual(s.advs[aid].owed, 10_000)

    def test_refusals(self):
        s, L = setup(budget=50_000)
        self.assertEqual(code(lambda: review.request_advance(s, "st", 5, 0)), FailureCode.INVALID_INPUT)
        s.closed.add(4)
        self.assertEqual(code(lambda: review.request_advance(s, "st", 4, 10)), FailureCode.CONFLICT)
        a1 = review.request_advance(s, "st", 5, 40_000)
        review.approve_advance(s, a1, "sup")
        a2 = review.request_advance(s, "st", 5, 20_000)
        self.assertEqual(code(lambda: review.approve_advance(s, a2, "sup")), FailureCode.CONFLICT)
        # report budget check also sees the advance
        rid = review.open_draft(s, "st", 5, Line(Category.TRAVEL, 20_000, "x", True))
        review.submit(s, rid, "st")
        self.assertEqual(code(lambda: review.approve(s, rid, "sup")), FailureCode.CONFLICT)
        # pay_against with unpaid advance / other period
        self.assertEqual(code(lambda: payment.pay_against(s, L, rid, a1, "fin")), FailureCode.CONFLICT)
        s.closed.add(5)
        self.assertEqual(code(lambda: review.approve_advance(s, a2, "sup")), FailureCode.CONFLICT)
        self.assertEqual(payment.pay_advance(s, L, a1, "fin"), "L1")  # closed period does not block payment


unittest.main()
