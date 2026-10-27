import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk.errors import Failure, FailureCode
from desk.ids import Role
from desk.staff import Staff, Department
from desk.reports import Report, ReportStatus
from desk.advances import Advance, AdvanceStatus
from desk import review, payment, queries


class FakeStore:
    def __init__(self):
        self.staff_by_badge = {}
        self.departments = {}
        self.reports = {}
        self.advs = {}
        self.closed_periods = set()
        self.audit = []
        self._next = 1

    def staff(self, badge):
        if badge not in self.staff_by_badge:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self.staff_by_badge[badge]

    def report(self, id):
        if id not in self.reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self.reports[id]

    def department(self, id):
        if id not in self.departments:
            raise Failure(FailureCode.NOT_FOUND, "no such department")
        return self.departments[id]

    def reports_for(self, department, period):
        return [r for r in self.reports.values() if r.department == department and r.period == period][:1000]

    def submitted_reports(self):
        return [r for r in self.reports.values() if r.status is ReportStatus.SUBMITTED][:1000]

    def period_closed(self, period):
        return period in self.closed_periods

    def next_id(self):
        id = str(self._next)
        self._next += 1
        return id

    def save_report(self, report):
        self.reports[report.id] = report

    def append_audit(self, entry):
        self.audit.append(entry)

    def close_period(self, period):
        self.closed_periods.add(period)

    def advance(self, id):
        if id not in self.advs:
            raise Failure(FailureCode.NOT_FOUND, "no such advance")
        return self.advs[id]

    def advances_for(self, department, period):
        return [a for a in self.advs.values() if a.department == department and a.period == period][:1000]

    def paid_advances(self):
        return [a for a in self.advs.values() if a.status is AdvanceStatus.PAID][:1000]

    def save_advance(self, advance):
        self.advs[advance.id] = advance


class FakeLedger:
    def __init__(self):
        self.calls = []

    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key))
        return f"REF-{key}"


def setup():
    store = FakeStore()
    store.departments["DEPT"] = Department("DEPT", "director1", 1_000_000)
    store.staff_by_badge["staffer"] = Staff("staffer", "Alice", "DEPT", "sup1", Role.STAFF, True)
    store.staff_by_badge["sup1"] = Staff("sup1", "Sup", "DEPT", "director1", Role.SUPERVISOR, True)
    store.staff_by_badge["director1"] = Staff("director1", "Dir", "DEPT", None, Role.DIRECTOR, True)
    store.staff_by_badge["finance1"] = Staff("finance1", "Fin", "DEPT", None, Role.FINANCE, True)
    return store


def expect_failure(fn, code):
    try:
        fn()
        assert False, "expected Failure"
    except Failure as f:
        assert f.code is code, f"expected {code}, got {f.code}"


def test_request_and_approve_small():
    store = setup()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    a = store.advance(aid)
    assert a.status is AdvanceStatus.REQUESTED
    assert a.department == "DEPT"
    assert store.audit == []            # requesting is not audited

    status = review.approve_advance(store, aid, "sup1")
    assert status is AdvanceStatus.APPROVED    # <=50_000 => 1 step (supervisor only)
    a = store.advance(aid)
    assert a.status is AdvanceStatus.APPROVED
    assert len(store.audit) == 1
    e = store.audit[0]
    assert e.who == "sup1" and e.report == aid
    assert e.from_status is AdvanceStatus.REQUESTED and e.to_status is AdvanceStatus.APPROVED

    # budget now reflects the advance
    assert queries.spend(store, "DEPT", 1) == 10_000
    stmt = queries.statement(store, "DEPT", 1)
    assert stmt.spend == 10_000
    assert len(stmt.rows) == 1
    assert stmt.rows[0].id == aid and stmt.rows[0].total == 10_000 and stmt.rows[0].budgeted == 10_000


def test_requester_cannot_approve_own_advance():
    store = setup()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    expect_failure(lambda: review.approve_advance(store, aid, "staffer"), FailureCode.UNAUTHORIZED)


def test_wrong_approver_rejected():
    store = setup()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    expect_failure(lambda: review.approve_advance(store, aid, "director1"), FailureCode.UNAUTHORIZED)


def test_closed_period_blocks_request_and_approval():
    store = setup()
    store.close_period(1)
    expect_failure(lambda: review.request_advance(store, "staffer", 1, 10_000), FailureCode.CONFLICT)

    store2 = setup()
    aid = review.request_advance(store2, "staffer", 1, 10_000)
    store2.close_period(1)
    expect_failure(lambda: review.approve_advance(store2, aid, "sup1"), FailureCode.CONFLICT)


def test_budget_override_only_finance():
    store = setup()
    store.departments["DEPT"] = Department("DEPT", "director1", 5_000)   # tiny budget
    aid = review.request_advance(store, "staffer", 1, 10_000)
    expect_failure(lambda: review.approve_advance(store, aid, "sup1"), FailureCode.CONFLICT)
    # finance can override, but amount <=50000 routes to supervisor only, never reaches finance step
    # bump amount so it routes to finance as final step
    store2 = setup()
    store2.departments["DEPT"] = Department("DEPT", "director1", 5_000)
    aid2 = review.request_advance(store2, "staffer", 1, 600_000)  # >500_000 => 3 steps: sup, dir, finance
    review.approve_advance(store2, aid2, "sup1")
    review.approve_advance(store2, aid2, "director1")
    status = review.approve_advance(store2, aid2, "finance1")   # finance can override budget
    assert status is AdvanceStatus.APPROVED


def test_pay_advance_and_statement():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    review.approve_advance(store, aid, "sup1")
    ref = payment.pay_advance(store, ledger, aid, "finance1")
    assert ref == f"REF-{aid}"
    a = store.advance(aid)
    assert a.status is AdvanceStatus.PAID and a.reference == ref
    assert ledger.calls == [("staffer", 10_000, aid)]
    # still counts against budget while Paid
    assert queries.spend(store, "DEPT", 1) == 10_000


def test_pay_advance_closed_period_allowed():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    review.approve_advance(store, aid, "sup1")
    store.close_period(1)
    ref = payment.pay_advance(store, ledger, aid, "finance1")
    assert ref == f"REF-{aid}"


def test_settle_full_cover():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 10_000)
    review.approve_advance(store, aid, "sup1")
    payment.pay_advance(store, ledger, aid, "finance1")

    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 4_000, "taxi", True))
    review.submit(store, rid, "staffer")
    review.approve(store, rid, "sup1")

    # advance no longer counts once settled, report counts instead -- check before settle
    assert queries.spend(store, "DEPT", 1) == 10_000 + 4_000

    result = payment.pay_against(store, ledger, rid, aid, "finance1")
    assert result == "settled"
    r = store.report(rid)
    assert r.status is ReportStatus.PAID
    assert r.reference == f"REF-{aid}"     # took the advance's reference
    a = store.advance(aid)
    assert a.status is AdvanceStatus.SETTLED
    assert a.owed == 6_000                 # 10000 - 4000
    assert len(ledger.calls) == 1          # no new ledger call for the report

    # after settling, advance no longer counts; only report (now Paid) counts
    assert queries.spend(store, "DEPT", 1) == 4_000
    stmt = queries.statement(store, "DEPT", 1)
    assert len(stmt.rows) == 1 and stmt.rows[0].id == rid


def test_settle_partial_cover():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 4_000)
    review.approve_advance(store, aid, "sup1")
    payment.pay_advance(store, ledger, aid, "finance1")

    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 10_000, "taxi", True))
    review.submit(store, rid, "staffer")
    review.approve(store, rid, "sup1")

    result = payment.pay_against(store, ledger, rid, aid, "finance1")
    assert result == f"REF-{rid}"
    r = store.report(rid)
    assert r.status is ReportStatus.PAID and r.reference == result
    a = store.advance(aid)
    assert a.status is AdvanceStatus.SETTLED and a.owed == 0
    assert ledger.calls[-1] == ("staffer", 10_000 - 4_000, rid)


def test_settle_rejects_mismatched_badge_or_period():
    store = setup()
    ledger = FakeLedger()
    store.staff_by_badge["other"] = Staff("other", "Bob", "DEPT", "sup1", Role.STAFF, True)
    aid = review.request_advance(store, "staffer", 1, 4_000)
    review.approve_advance(store, aid, "sup1")
    payment.pay_advance(store, ledger, aid, "finance1")

    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(store, "other", 1, Line(Category.OTHER, 10_000, "taxi", True))
    review.submit(store, rid, "other")
    review.approve(store, rid, "sup1")

    expect_failure(lambda: payment.pay_against(store, ledger, rid, aid, "finance1"), FailureCode.CONFLICT)


def test_settle_once_only():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 4_000)
    review.approve_advance(store, aid, "sup1")
    payment.pay_advance(store, ledger, aid, "finance1")

    from desk.lines import Line
    from desk.ids import Category
    rid1 = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 10_000, "taxi", True))
    review.submit(store, rid1, "staffer")
    review.approve(store, rid1, "sup1")
    payment.pay_against(store, ledger, rid1, aid, "finance1")

    rid2 = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 1_000, "taxi2", False))
    review.submit(store, rid2, "staffer")
    review.approve(store, rid2, "sup1")
    expect_failure(lambda: payment.pay_against(store, ledger, rid2, aid, "finance1"), FailureCode.CONFLICT)


def test_outstanding_advances():
    store = setup()
    ledger = FakeLedger()
    aid = review.request_advance(store, "staffer", 1, 4_000)
    review.approve_advance(store, aid, "sup1")
    payment.pay_advance(store, ledger, aid, "finance1")

    assert queries.outstanding_advances(store, 1) == []
    assert queries.outstanding_advances(store, 3) == []    # period + 2 < today => 1+2 < 3 is False
    assert queries.outstanding_advances(store, 4) == [aid]  # 1+2 < 4 True


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK {t.__name__}")


if __name__ == "__main__":
    run_all()
    print("ALL PASS")
