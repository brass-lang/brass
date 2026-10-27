import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fakes import FakeStore, FakeRegistry, FakeLedger

from desk.staff import Staff, Department
from desk.ids import Role
from desk.records import Region, Vehicle, Delegation, CardTxn, CardStatus
from desk.lines import Line
from desk.errors import Failure, FailureCode
from desk import review, payment, queries, allowances
from desk.reports import Report, ReportStatus
import desk.trip_desk as td
from desk.trips import TripStatus

PASS = 0
FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")

def expect_failure(name, code, fn):
    try:
        fn()
        check(name, False)
    except Failure as f:
        check(name, f.code is code)


def base_store():
    store = FakeStore()
    store.add_department(Department("dep1", "D1", 1_000_000_00))  # big budget, cents
    store.add_staff(Staff("STAFF1", "Staff One", "dep1", "S1", Role.STAFF, True))
    store.add_staff(Staff("S1", "Supervisor", "dep1", "D1", Role.SUPERVISOR, True))
    store.add_staff(Staff("D1", "Director", "dep1", "F1", Role.DIRECTOR, True))
    store.add_staff(Staff("F1", "Finance", "dep1", None, Role.FINANCE, True))
    store.add_staff(Staff("STAFF2", "Staff Two", "dep1", "S1", Role.STAFF, True))
    return store


# 1. basic file + single-step approve
store = base_store()
tid = td.file_trip(store, "STAFF1", 1, Region.ISLAND, 5, Vehicle.CAR, 0)
t = store.trip(tid)
check("priced", t.committed == 9_000 * 5)
check("status requested", t.status is TripStatus.REQUESTED)

status = td.approve_trip(store, FakeRegistry(), tid, "S1", today=1)
check("single-step approved", status is TripStatus.APPROVED)
t = store.trip(tid)
check("trip saved approved", t.status is TripStatus.APPROVED)
check("audit entry written", store.audit[-1].to_status is TripStatus.APPROVED)

# 2. duplicate open trip -> Conflict
expect_failure("dup trip conflict", FailureCode.CONFLICT, lambda: td.file_trip(store, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0))

# 3. both zero -> InvalidInput
expect_failure("zero plan invalid", FailureCode.INVALID_INPUT, lambda: td.file_trip(store, "STAFF2", 1, Region.ISLAND, 0, Vehicle.CAR, 0))

# 4. self approval unauthorized
store2 = base_store()
tid2 = td.file_trip(store2, "STAFF1", 2, Region.MAINLAND, 2, Vehicle.CAR, 0)
expect_failure("self approve unauthorized", FailureCode.UNAUTHORIZED, lambda: td.approve_trip(store2, FakeRegistry(), tid2, "STAFF1", today=2))

# 5. amend an approved trip returns to requested, clears approvals, audits
store3 = base_store()
tid3 = td.file_trip(store3, "STAFF1", 3, Region.ISLAND, 5, Vehicle.CAR, 0)
td.approve_trip(store3, FakeRegistry(), tid3, "S1", today=3)
t3 = store3.trip(tid3)
check("approved before amend", t3.status is TripStatus.APPROVED)
after = td.amend_trip(store3, tid3, "STAFF1", Region.MAINLAND, 10, Vehicle.CAR, 0)
check("amend returns to requested", after is TripStatus.REQUESTED)
t3 = store3.trip(tid3)
check("amend repriced", t3.committed == 6_000 * 10)
check("amend cleared approvals", t3.approvals == ())
check("amend audited", store3.audit[-1].from_status is TripStatus.APPROVED and store3.audit[-1].to_status is TripStatus.REQUESTED)

# amend by someone else -> Unauthorized
expect_failure("amend by other unauthorized", FailureCode.UNAUTHORIZED,
              lambda: td.amend_trip(store3, tid3, "STAFF2", Region.MAINLAND, 10, Vehicle.CAR, 0))

# 6. multi-step approval requiring director + finance, with budget override by finance
store4 = base_store()
store4.departments["dep1"] = Department("dep1", "D1", 100_00)  # tiny budget forces override
tid4 = td.file_trip(store4, "STAFF1", 4, Region.OFFSITE, 30, Vehicle.TRUCK, 2000)  # big amount -> 3 steps
t4 = store4.trip(tid4)
check("3-step committed amount", t4.committed > 500_000)
st = td.approve_trip(store4, FakeRegistry(), tid4, "S1", today=4)
check("step1 still requested", st is TripStatus.REQUESTED)
st = td.approve_trip(store4, FakeRegistry(), tid4, "D1", today=4)
check("step2 still requested", st is TripStatus.REQUESTED)
expect_failure("director is not the finance step's approver", FailureCode.UNAUTHORIZED,
              lambda: td.approve_trip(store4, FakeRegistry(), tid4, "D1", today=4))
st = td.approve_trip(store4, FakeRegistry(), tid4, "F1", today=4)
check("finance override approves", st is TripStatus.APPROVED)
check("override audit reason", "override" in store4.audit[-1].reason)

# a non-finance approver at the final (and only) step is blocked by an exceeded budget
store4b = base_store()
store4b.departments["dep1"] = Department("dep1", "D1", 100)  # tiny budget
tid4b = td.file_trip(store4b, "STAFF1", 4, Region.ISLAND, 1, Vehicle.CAR, 0)  # single supervisor step
expect_failure("supervisor cannot override budget", FailureCode.CONFLICT,
              lambda: td.approve_trip(store4b, FakeRegistry(), tid4b, "S1", today=4))
check("budget-blocked trip stays requested", store4b.trip(tid4b).status is TripStatus.REQUESTED)

# 7. delegation
store5 = base_store()
reg5 = FakeRegistry()
tid5 = td.file_trip(store5, "STAFF1", 5, Region.ISLAND, 5, Vehicle.CAR, 0)  # supervisor-only step
delegate_badge = "DELEG1"
store5.add_staff(Staff(delegate_badge, "Delegate", "dep1", None, Role.STAFF, True))
reg5.save_delegation(Delegation("dg1", "S1", delegate_badge, 1, 10, False))
st = td.approve_trip(store5, reg5, tid5, delegate_badge, today=5)
check("delegate approves", st is TripStatus.APPROVED)
reason = store5.audit[-1].reason
check("delegation reason mentions delegator", "S1" in reason)
check("delegation reason mentions period", "5" in reason)

# delegation expired -> unauthorized
store5b = base_store()
reg5b = FakeRegistry()
tid5b = td.file_trip(store5b, "STAFF1", 20, Region.ISLAND, 5, Vehicle.CAR, 0)
reg5b.save_delegation(Delegation("dg2", "S1", delegate_badge, 1, 10, False))
store5b.add_staff(Staff(delegate_badge, "Delegate", "dep1", None, Role.STAFF, True))
expect_failure("expired delegation unauthorized", FailureCode.UNAUTHORIZED,
              lambda: td.approve_trip(store5b, reg5b, tid5b, delegate_badge, today=20))

# 8. budget: report beside a trip does not double-count
from desk.ids import Category

store6 = base_store()
store6.departments["dep1"] = Department("dep1", "D1", 6_000)  # budget exactly equal to trip committed
tid6 = td.file_trip(store6, "STAFF1", 6, Region.MAINLAND, 1, Vehicle.CAR, 0)  # committed = 6000
t6 = store6.trip(tid6)
check("trip6 committed is 6000", t6.committed == 6_000)
td.approve_trip(store6, FakeRegistry(), tid6, "S1", today=6)

r_id = store6.next_id()
store6.save_report(Report(r_id, "STAFF1", "dep1", 6, (Line(Category.TRAVEL, 6_000, "mileage", True),), ReportStatus.SUBMITTED))
status6 = review.approve(store6, r_id, "S1")
check("report approves without double-charging the trip", status6 is ReportStatus.APPROVED)
check("dept spend after is just 6000", queries.spend(store6, "dep1", 6) == 6_000)
t6 = store6.trip(tid6)
check("trip now fully covered", t6.status is TripStatus.APPROVED)

# statement no longer lists the trip once it is fully covered by the report
st6 = queries.statement(store6, "dep1", 6)
check("trip row dropped once fully covered", not any(r.id == tid6 for r in st6.rows))

# 9. a trip that still has remaining commitment shows up in the statement, after advance rows
store7 = base_store()
store7.departments["dep1"] = Department("dep1", "D1", 1_000_000)
tid7 = td.file_trip(store7, "STAFF1", 7, Region.OFFSITE, 10, Vehicle.CAR, 0)  # committed = 120000, 2 steps
td.approve_trip(store7, FakeRegistry(), tid7, "S1", today=7)
td.approve_trip(store7, FakeRegistry(), tid7, "D1", today=7)
st7 = queries.statement(store7, "dep1", 7)
check("trip row present", any(r.id == tid7 for r in st7.rows))
trip_row = [r for r in st7.rows if r.id == tid7][0]
check("trip row total == budgeted == remaining", trip_row.total == trip_row.budgeted == 120_000)
check("spend includes the trip", st7.spend == 120_000)
check("remaining excludes the trip's commitment", st7.remaining == 1_000_000 - 120_000)

# 10. reconciling against a report and card transactions
reg10 = FakeRegistry()
report10 = store7.next_id()
store7.save_report(Report(report10, "STAFF1", "dep1", 7, (Line(Category.TRAVEL, 50_000, "trip expenses", True),), ReportStatus.APPROVED))
txn_id = reg10.next_delegation_id()
reg10.save_txn(CardTxn(txn_id, "STAFF1", 7, 2_500, Category.OTHER, "shop", CardStatus.OPEN, None))
other_txn_id = reg10.next_delegation_id()  # belongs to a different period: must not be counted
reg10.save_txn(CardTxn(other_txn_id, "STAFF1", 8, 999, Category.OTHER, "shop2", CardStatus.OPEN, None))
actual = td.reconcile_trip(store7, reg10, tid7, report10, "F1")
check("actual = report total + unmatched txn", actual == 50_000 + 2_500)
t7 = store7.trip(tid7)
check("trip reconciled", t7.status is TripStatus.RECONCILED)
check("reconciliation fields", t7.reconciliation.committed == 120_000 and t7.reconciliation.actual == 52_500
     and t7.reconciliation.report == report10 and t7.reconciliation.transactions == (txn_id,))
# a Reconciled trip counts nothing: only the report's own budgeted total remains charged
check("reconciled trip stops counting its leftover commitment",
     queries.spend(store7, "dep1", 7) == 50_000 and queries.statement(store7, "dep1", 7).remaining == 950_000)
audit_len_before = len(store7.audit)
actual2 = td.reconcile_trip(store7, reg10, tid7, report10, "F1")
check("repeat reconcile same result", actual2 == actual)
check("repeat with unchanged inputs does not re-audit", len(store7.audit) == audit_len_before)

# 11. closing a period closes open trips in order, then marks the period closed; a failed audit write does not roll back
store8 = base_store()
tidA = td.file_trip(store8, "STAFF1", 9, Region.ISLAND, 1, Vehicle.CAR, 0)
tidB = td.file_trip(store8, "STAFF2", 9, Region.ISLAND, 1, Vehicle.CAR, 0)

class FlakyStore(FakeStore):
    def __init__(self, base):
        self.__dict__.update(base.__dict__)
        self.fail_once_for = None

    def append_audit(self, entry):
        if self.fail_once_for is not None and entry.subject_id == self.fail_once_for:
            self.fail_once_for = None
            raise Failure(FailureCode.UNAVAILABLE, "audit sink is down")
        super().append_audit(entry)

flaky = FlakyStore(store8)
flaky.fail_once_for = tidB
try:
    payment.close_period(flaky, 9, "F1")
    check("expected failure on second trip's audit", False)
except Failure as f:
    check("propagated failure code", f.code is FailureCode.UNAVAILABLE)

check("period still open after failure", not flaky.period_closed(9))
check("first trip closed despite later failure", flaky.trip(tidA).status is TripStatus.CLOSED)
check("second trip closed even though its audit failed", flaky.trip(tidB).status is TripStatus.CLOSED)
audit_count_after_failure = len([e for e in flaky.audit if e.subject_id == tidB])
check("second trip has no audit entry yet", audit_count_after_failure == 0)

payment.close_period(flaky, 9, "F1")
check("retry closes the period", flaky.period_closed(9))
audit_count_final = len([e for e in flaky.audit if e.subject_id == tidB])
check("retry does not backfill the missing audit entry", audit_count_final == 0)
audit_count_A = len([e for e in flaky.audit if e.subject_id == tidA])
check("retry does not re-audit the already-closed trip", audit_count_A == 1)

print(f"PASS={PASS} FAIL={FAIL}")
