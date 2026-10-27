import sys
sys.path.insert(0, "src")

from desk.ids import Role
from desk.staff import Staff, Department
from desk.reports import Report, ReportStatus
from desk.advances import Advance, AdvanceStatus
from desk.trips import Trip, TripStatus
from desk.records import CardTxn, CardStatus, Delegation, Region, Vehicle
from desk.errors import Failure, FailureCode

from desk import trip_desk, payment, queries, review, advance_desk


class FakeStore:
    def __init__(self):
        self.staff_ = {}
        self.departments = {}
        self.reports = {}
        self.advances = {}
        self.trips = {}
        self.closed_periods = set()
        self.audit = []
        self.counter = 0

    # Store protocol
    def staff(self, badge):
        if badge not in self.staff_:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self.staff_[badge]

    def report(self, id):
        if id not in self.reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self.reports[id]

    def department(self, id):
        return self.departments[id]

    def reports_for(self, department, period):
        return [r for r in self.reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        return list(self.reports.values())

    def period_closed(self, period):
        return period in self.closed_periods

    def next_id(self):
        self.counter += 1
        return str(self.counter)

    def save_report(self, report):
        self.reports[report.id] = report

    def append_audit(self, entry):
        self.audit.append(entry)

    def close_period(self, period):
        self.closed_periods.add(period)

    def advance(self, id):
        return self.advances[id]

    def advances_for(self, department, period):
        return [a for a in self.advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        return [a for a in self.advances.values() if a.status == AdvanceStatus.PAID]

    def save_advance(self, advance):
        self.advances[advance.id] = advance

    def trip(self, id):
        if id not in self.trips:
            raise Failure(FailureCode.NOT_FOUND, "no such trip")
        return self.trips[id]

    def trips_for(self, department, period):
        return [t for t in self.trips.values() if t.department == department and t.period == period]

    def trips_in(self, period):
        return [t for t in self.trips.values() if t.period == period]

    def save_trip(self, trip):
        self.trips[trip.id] = trip


class FakeRegistry:
    def __init__(self):
        self.txns = {}
        self.delegations = {}
        self.counter = 0

    def txns_for(self, period):
        return [t for t in self.txns.values() if t.period == period]

    def txn(self, id):
        return self.txns[id]

    def save_txn(self, t):
        self.txns[t.id] = t

    def delegations_from(self, badge):
        return [d for d in self.delegations.values() if d.delegator == badge]

    def delegation(self, id):
        return self.delegations[id]

    def save_delegation(self, d):
        self.delegations[d.id] = d

    def next_id(self):
        self.counter += 1
        return "d" + str(self.counter)


def mkstore():
    s = FakeStore()
    s.departments["D1"] = Department("D1", "director1", 1_000_000)
    s.staff_["staffer"] = Staff("staffer", "Staffer", "D1", "super1", Role.STAFF, True)
    s.staff_["super1"] = Staff("super1", "Super", "D1", "director1", Role.SUPERVISOR, True)
    s.staff_["director1"] = Staff("director1", "Director", "D1", None, Role.DIRECTOR, True)
    s.staff_["finance1"] = Staff("finance1", "Finance", "D1", None, Role.FINANCE, True)
    return s


def expect_failure(code, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except Failure as f:
        assert f.code == code, f"expected {code} got {f.code}: {f.message}"
        return f
    raise AssertionError("expected a Failure, none raised")


def test_filing_pricing_and_conflict():
    s = mkstore()
    tid = trip_desk.file_trip(s, "staffer", 1, Region.ISLAND, 2, Vehicle.CAR, 100)
    t = s.trip(tid)
    assert t.committed == 9_000 * 2 + 60 * 100, t.committed
    assert t.status == TripStatus.REQUESTED
    # second open trip same period: Conflict
    expect_failure(FailureCode.CONFLICT, trip_desk.file_trip, s, "staffer", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
    # both zero: InvalidInput
    expect_failure(FailureCode.INVALID_INPUT, trip_desk.file_trip, s, "staffer", 2, Region.ISLAND, 0, Vehicle.CAR, 0)
    print("test_filing_pricing_and_conflict OK")


def test_approve_small_single_step_and_budget():
    s = mkstore()
    tid = trip_desk.file_trip(s, "staffer", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # 9000 cents, 1 step
    reg = FakeRegistry()
    # not by filer
    expect_failure(FailureCode.UNAUTHORIZED, trip_desk.approve_trip, s, reg, tid, "staffer", 1)
    status = trip_desk.approve_trip(s, reg, tid, "super1", 1)
    assert status == TripStatus.APPROVED
    t = s.trip(tid)
    assert t.status == TripStatus.APPROVED
    assert len(s.audit) == 1
    e = s.audit[0]
    assert e.reason == "approved"
    print("test_approve_small_single_step_and_budget OK")


def test_multi_step_approval_amounts():
    s = mkstore()
    # 60000 cents per diem * x ... use mileage to cross DIRECTOR_UP_TO (500000)
    tid = trip_desk.file_trip(s, "staffer", 1, Region.OFFSITE, 30, Vehicle.BOAT, 2000)  # big amount, 3 steps
    reg = FakeRegistry()
    t = s.trip(tid)
    assert t.committed > 500_000
    st = trip_desk.approve_trip(s, reg, tid, "super1", 1)
    assert st == TripStatus.REQUESTED
    assert len(s.trip(tid).approvals) == 1
    st = trip_desk.approve_trip(s, reg, tid, "director1", 1)
    assert st == TripStatus.REQUESTED
    assert len(s.trip(tid).approvals) == 2
    st = trip_desk.approve_trip(s, reg, tid, "finance1", 1)
    assert st == TripStatus.APPROVED
    assert s.trip(tid).committed <= s.department("D1").budget
    assert s.audit[-1].reason == "approved"
    print("test_multi_step_approval_amounts OK")


def test_trip_approval_budget_override():
    s = mkstore()
    s.departments["D1"] = Department("D1", "director1", 1_000)  # tiny budget
    tid = trip_desk.file_trip(s, "staffer", 1, Region.OFFSITE, 30, Vehicle.BOAT, 2000)  # 860000, 3 steps
    reg = FakeRegistry()
    assert trip_desk.approve_trip(s, reg, tid, "super1", 1) == TripStatus.REQUESTED
    # director's step is not the final one: no budget check yet
    assert trip_desk.approve_trip(s, reg, tid, "director1", 1) == TripStatus.REQUESTED
    # only finance may reach the final (3rd) step
    expect_failure(FailureCode.UNAUTHORIZED, trip_desk.approve_trip, s, reg, tid, "director1", 1)
    st = trip_desk.approve_trip(s, reg, tid, "finance1", 1)
    assert st == TripStatus.APPROVED
    assert "override" in s.audit[-1].reason
    print("test_trip_approval_budget_override OK")


def test_delegation():
    s = mkstore()
    s.staff_["super1"] = Staff("super1", "Super", "D1", "director1", Role.SUPERVISOR, True)
    tid = trip_desk.file_trip(s, "staffer", 5, Region.ISLAND, 1, Vehicle.CAR, 0)
    reg = FakeRegistry()
    reg.delegations["d1"] = Delegation("d1", "super1", "delegate1", 5, 5, False)
    s.staff_["delegate1"] = Staff("delegate1", "Delegate", "D1", None, Role.STAFF, True)
    # not yet in force for today=4
    expect_failure(FailureCode.UNAUTHORIZED, trip_desk.approve_trip, s, reg, tid, "delegate1", 4)
    status = trip_desk.approve_trip(s, reg, tid, "delegate1", 5)
    assert status == TripStatus.APPROVED
    assert "delegat" in s.audit[-1].reason.lower() and "super1" in s.audit[-1].reason and "5" in s.audit[-1].reason
    # revoked delegation stops counting for new approvals, but this trip is already approved; test on a fresh trip
    tid2 = trip_desk.file_trip(s, "staffer", 6, Region.ISLAND, 1, Vehicle.CAR, 0)
    reg.delegations["d2"] = Delegation("d2", "super1", "delegate1", 6, 6, True)  # revoked
    expect_failure(FailureCode.UNAUTHORIZED, trip_desk.approve_trip, s, reg, tid2, "delegate1", 6)
    print("test_delegation OK")


def test_amend_clears_approvals_and_reverts():
    s = mkstore()
    tid = trip_desk.file_trip(s, "staffer", 1, Region.OFFSITE, 30, Vehicle.BOAT, 2000)
    reg = FakeRegistry()
    trip_desk.approve_trip(s, reg, tid, "super1", 1)
    trip_desk.approve_trip(s, reg, tid, "director1", 1)
    trip_desk.approve_trip(s, reg, tid, "finance1", 1)
    assert s.trip(tid).status == TripStatus.APPROVED
    audit_count = len(s.audit)
    status = trip_desk.amend_trip(s, tid, "staffer", Region.ISLAND, 1, Vehicle.CAR, 0)
    assert status == TripStatus.REQUESTED
    t = s.trip(tid)
    assert t.status == TripStatus.REQUESTED
    assert t.approvals == ()
    assert t.committed == 9_000
    assert len(s.audit) == audit_count + 1
    # not the filer
    expect_failure(FailureCode.UNAUTHORIZED, trip_desk.amend_trip, s, tid, "super1", Region.ISLAND, 1, Vehicle.CAR, 0)
    # amend while Requested: no extra audit entry
    audit_count = len(s.audit)
    trip_desk.amend_trip(s, tid, "staffer", Region.MAINLAND, 2, Vehicle.TRUCK, 0)
    assert len(s.audit) == audit_count
    print("test_amend_clears_approvals_and_reverts OK")


def test_report_and_trip_budget_interplay():
    s = mkstore()
    s.departments["D1"] = Department("D1", "director1", 100_000)  # small budget
    tid = trip_desk.file_trip(s, "staffer", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # committed 9000
    reg = FakeRegistry()
    trip_desk.approve_trip(s, reg, tid, "super1", 1)
    assert s.trip(tid).status == TripStatus.APPROVED
    # statement / spend should show 9000 from the trip
    spend = queries.spend(s, "D1", 1)
    assert spend == 9_000, spend
    stmt = queries.statement(s, "D1", 1)
    assert any(r.id == tid and r.total == 9_000 for r in stmt.rows), stmt.rows

    # now file a report of the staffer for same period with a travel line of 9000 (per diem-like, using OTHER category to avoid lines module coupling)
    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(s, "staffer", 1, Line(Category.OTHER, 5_000, "x", True))
    review.submit(s, rid, "staffer")
    # approve report (1-step, amount 5000): with trip present, must not double count
    st = review.approve(s, rid, "super1")
    assert st == ReportStatus.APPROVED
    r = s.report(rid)
    assert r.status == ReportStatus.APPROVED

    spend2 = queries.spend(s, "D1", 1)
    # trip now counts only 9000 - 5000 = 4000, plus report 5000 = 9000 total still
    assert spend2 == 9_000, spend2
    print("test_report_and_trip_budget_interplay OK")


def test_reconcile_and_repeat():
    s = mkstore()
    reg = FakeRegistry()
    tid = trip_desk.file_trip(s, "staffer", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # 9000
    trip_desk.approve_trip(s, reg, tid, "super1", 1)

    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(s, "staffer", 1, Line(Category.OTHER, 4_000, "x", True))
    review.submit(s, rid, "staffer")
    review.approve(s, rid, "super1")

    reg.txns["tx1"] = CardTxn("tx1", "staffer", 1, 1_000, Category.OTHER, "m", CardStatus.OPEN)
    reg.txns["tx2"] = CardTxn("tx2", "staffer", 1, 2_000, Category.OTHER, "m", CardStatus.DISPUTED)
    reg.txns["tx3"] = CardTxn("tx3", "staffer", 1, 500, Category.OTHER, "m", CardStatus.MATCHED, matched=rid)

    actual = trip_desk.reconcile_trip(s, reg, tid, rid, "finance1")
    assert actual == 4_000 + 1_000 + 2_000, actual
    t = s.trip(tid)
    assert t.status == TripStatus.RECONCILED
    assert t.reconciliation.actual == actual
    assert set(t.reconciliation.transactions) == {"tx1", "tx2"}
    audit_count = len(s.audit)

    # repeat unchanged: saves again, same result, no new audit entry
    actual2 = trip_desk.reconcile_trip(s, reg, tid, rid, "finance1")
    assert actual2 == actual
    assert len(s.audit) == audit_count, "repeat with unchanged inputs must not add an audit entry"

    # change: add another unmatched txn -> differs -> new audit entry
    reg.txns["tx4"] = CardTxn("tx4", "staffer", 1, 500, Category.OTHER, "m", CardStatus.OPEN)
    actual3 = trip_desk.reconcile_trip(s, reg, tid, rid, "finance1")
    assert actual3 == actual + 500
    assert len(s.audit) == audit_count + 1
    print("test_reconcile_and_repeat OK")


def test_close_trip_and_close_period():
    s = mkstore()
    reg = FakeRegistry()
    tid1 = trip_desk.file_trip(s, "staffer", 2, Region.ISLAND, 1, Vehicle.CAR, 0)
    s.staff_["staffer2"] = Staff("staffer2", "Staffer2", "D1", "super1", Role.STAFF, True)
    tid2 = trip_desk.file_trip(s, "staffer2", 2, Region.ISLAND, 1, Vehicle.CAR, 0)
    trip_desk.approve_trip(s, reg, tid2, "super1", 2)
    # close a single requested trip early
    trip_desk.close_trip(s, tid1, "finance1", "trip cancelled")
    assert s.trip(tid1).status == TripStatus.CLOSED
    # closed trip doesn't block re-filing
    tid1b = trip_desk.file_trip(s, "staffer", 2, Region.ISLAND, 1, Vehicle.CAR, 0)
    assert s.trip(tid1b).status == TripStatus.REQUESTED

    payment.close_period(s, 2, "finance1")
    assert s.period_closed(2)
    assert s.trip(tid2).status == TripStatus.CLOSED
    assert s.trip(tid1b).status == TripStatus.CLOSED
    expect_failure(FailureCode.CONFLICT, payment.close_period, s, 2, "finance1")
    print("test_close_trip_and_close_period OK")


def test_close_period_retry_is_idempotent():
    s = mkstore()
    reg = FakeRegistry()
    tid = trip_desk.file_trip(s, "staffer", 3, Region.ISLAND, 1, Vehicle.CAR, 0)

    orig_save_trip = s.save_trip
    calls = {"n": 0}

    def flaky_append_audit(entry):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated audit failure")
        s.audit.append(entry)

    s.append_audit = flaky_append_audit
    try:
        payment.close_period(s, 3, "finance1")
        raise AssertionError("expected the simulated failure to propagate")
    except RuntimeError:
        pass
    assert s.trip(tid).status == TripStatus.CLOSED, "the trip's save must have gone through before the audit failure"
    assert not s.period_closed(3), "period must stay open when closing fails"
    assert len(s.audit) == 0

    s.append_audit = orig_save_trip and s.audit.append  # restore normal behavior
    payment.close_period(s, 3, "finance1")
    assert s.period_closed(3)
    assert len(s.audit) == 0, "the audit entry for the already-closed trip must not be retried"
    print("test_close_period_retry_is_idempotent OK")


def test_reconciled_trip_never_closed():
    s = mkstore()
    reg = FakeRegistry()
    tid = trip_desk.file_trip(s, "staffer", 4, Region.ISLAND, 1, Vehicle.CAR, 0)
    trip_desk.approve_trip(s, reg, tid, "super1", 4)
    from desk.lines import Line
    from desk.ids import Category
    rid = review.open_draft(s, "staffer", 4, Line(Category.OTHER, 1, "x", False))
    review.submit(s, rid, "staffer")
    review.approve(s, rid, "super1")
    trip_desk.reconcile_trip(s, reg, tid, rid, "finance1")
    assert s.trip(tid).status == TripStatus.RECONCILED
    payment.close_period(s, 4, "finance1")
    assert s.trip(tid).status == TripStatus.RECONCILED, "a reconciled trip must never be closed"
    print("test_reconciled_trip_never_closed OK")


if __name__ == "__main__":
    test_filing_pricing_and_conflict()
    test_approve_small_single_step_and_budget()
    test_multi_step_approval_amounts()
    test_trip_approval_budget_override()
    test_delegation()
    test_amend_clears_approvals_and_reverts()
    test_report_and_trip_budget_interplay()
    test_reconcile_and_repeat()
    test_close_trip_and_close_period()
    test_close_period_retry_is_idempotent()
    test_reconciled_trip_never_closed()
    print("ALL OK")
