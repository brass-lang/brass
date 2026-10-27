import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fakes import FakeStore, FakeRegistry, FakeLedger
from desk.ids import Role, Category
from desk.staff import Staff, Department
from desk.records import Region, Vehicle
from desk.trips import TripStatus
from desk import trip_desk, review, payment, queries, advance_desk
from desk.lines import Line
from desk.reports import Report, ReportStatus
from desk.errors import Failure, FailureCode

def mk():
    store = FakeStore()
    reg = FakeRegistry()
    store.add_department(Department("D1", "dir1", budget=10_000_00))
    store.add_staff(Staff("staff1", "Staff One", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("staff2", "Staff Two", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("sup1", "Sup One", "D1", "dir1", Role.SUPERVISOR, True))
    store.add_staff(Staff("dir1", "Dir One", "D1", None, Role.DIRECTOR, True))
    store.add_staff(Staff("fin1", "Fin One", "D1", None, Role.FINANCE, True))
    return store, reg

def expect_failure(fn, code):
    try:
        fn()
        raise AssertionError("expected failure")
    except Failure as f:
        assert f.code is code, f"expected {code} got {f.code}: {f.message}"

# --- close_period closes open trips, in store order, then closes period ---
store, reg = mk()
tid1 = trip_desk.file_trip(store, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
tid2 = trip_desk.file_trip(store, "staff2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
trip_desk.approve_trip(store, reg, tid1, "sup1", today=1)  # tid1 -> Approved
# tid2 stays Requested
payment.close_period(store, 1, "fin1")
assert store.period_closed(1)
assert store.trip(tid1).status is TripStatus.CLOSED
assert store.trip(tid2).status is TripStatus.CLOSED
audited_trip_ids = [e.subject_id for e in store._audit if e.to_status is TripStatus.CLOSED]
assert set(audited_trip_ids) == {tid1, tid2}
print("close_period closes open trips + audits OK")

# re-closing an already closed period -> Conflict
expect_failure(lambda: payment.close_period(store, 1, "fin1"), FailureCode.CONFLICT)
print("re-close closed period -> Conflict OK")

# --- retry semantics: simulate failure mid-way through closing ---
store, reg = mk()
tid1 = trip_desk.file_trip(store, "staff1", 2, Region.ISLAND, 1, Vehicle.CAR, 0)
tid2 = trip_desk.file_trip(store, "staff2", 2, Region.ISLAND, 1, Vehicle.CAR, 0)

orig_append_audit = store.append_audit
calls = {"n": 0}
def flaky_append_audit(entry):
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("audit sink down")
    return orig_append_audit(entry)
store.append_audit = flaky_append_audit

try:
    payment.close_period(store, 2, "fin1")
    raise AssertionError("expected failure")
except RuntimeError:
    pass

# first trip in store order got Closed (saved) but its audit failed; period stays open
assert not store.period_closed(2)
order = list(store._trips.keys())
first_trip_id = [t.id for t in store.trips_in(2)][0]
assert store.trip(first_trip_id).status is TripStatus.CLOSED
print("partial failure: trip saved Closed, period stays open OK")

# retry: should skip the already-closed trip (no new audit attempt for it), close the rest, then close period
store.append_audit = orig_append_audit
audit_len_before = len(store._audit)
payment.close_period(store, 2, "fin1")
assert store.period_closed(2)
assert store.trip(tid1).status is TripStatus.CLOSED
assert store.trip(tid2).status is TripStatus.CLOSED
new_entries = store._audit[audit_len_before:]
audited_ids = {e.subject_id for e in new_entries}
assert first_trip_id not in audited_ids, "already-closed trip must not be re-audited by retry"
print("retry skips already-closed trip, closes rest, closes period OK")

# --- report beside a trip: budget double counting ---
store, reg = mk()
store2budget = store.department("D1")
# small department budget to make the interaction visible
store._departments["D1"] = Department("D1", "dir1", budget=20_000)
tid = trip_desk.file_trip(store, "staff1", 3, Region.ISLAND, 2, Vehicle.CAR, 0)  # committed = 18000
trip_desk.approve_trip(store, reg, tid, "sup1", today=3)  # trip Approved, remaining=18000 (no covered reports yet)

# file + submit + approve a report of 18000 by staff1 for same period; this report, once approved,
# should itself count toward budget, and the trip's remaining should drop to 0 - no double charge.
rid = store.next_id()
r = Report(rid, "staff1", "D1", 3, (Line(Category.TRAVEL, 18000, "travel", True),), ReportStatus.SUBMITTED)
store.save_report(r)
# approver: sup1 (single step, since 18000 <= SUPERVISOR_ONLY_UP_TO)
status = review.approve(store, rid, "sup1")
assert status is ReportStatus.APPROVED, status
print("report beside trip approved without budget conflict (no double charge) OK")

stmt = queries.statement(store, "D1", 3)
print("spend after both:", stmt.spend, "budget:", stmt.budget)
assert stmt.spend == 18000, stmt.spend  # report counts 18000; trip's remaining commitment now 0, not double counted
trip_rows = [row for row in stmt.rows if row.id == tid]
assert trip_rows == [], "trip with 0 remaining should not appear as a row"
print("statement shows no double count, trip row omitted when remaining is 0 OK")

print("ALL CLOSE-PERIOD / BUDGET-INTERACTION CHECKS PASSED")
