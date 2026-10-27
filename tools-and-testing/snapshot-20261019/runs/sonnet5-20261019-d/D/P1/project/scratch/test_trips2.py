import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fakes import FakeStore, FakeRegistry, FakeLedger
from desk.ids import Role, Category
from desk.staff import Staff, Department
from desk.records import Region, Vehicle, Delegation, CardTxn, CardStatus
from desk.trips import TripStatus
from desk import trip_desk, review, payment, queries, reports as reports_mod
from desk.lines import Line
from desk.errors import Failure, FailureCode

def mk():
    store = FakeStore()
    reg = FakeRegistry()
    store.add_department(Department("D1", "dir1", budget=10_000_00))
    store.add_staff(Staff("staff1", "Staff One", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("sup1", "Sup One", "D1", "dir1", Role.SUPERVISOR, True))
    store.add_staff(Staff("dir1", "Dir One", "D1", None, Role.DIRECTOR, True))
    store.add_staff(Staff("fin1", "Fin One", "D1", None, Role.FINANCE, True))
    store.add_staff(Staff("delegate1", "Del One", "D1", "dir1", Role.SUPERVISOR, True))
    return store, reg

def expect_failure(fn, code):
    try:
        fn()
        raise AssertionError("expected failure")
    except Failure as f:
        assert f.code is code, f"expected {code} got {f.code}: {f.message}"

# --- Delegation test ---
store, reg = mk()
tid = trip_desk.file_trip(store, "staff1", 5, Region.ISLAND, 2, Vehicle.CAR, 0)  # committed 18000, single step (supervisor)
# sup1 delegates to delegate1 for period 5 only
reg.save_delegation(Delegation("deleg1", "sup1", "delegate1", 5, 5, False))
# delegate1 should be accepted as approver (not sup1)
status = trip_desk.approve_trip(store, reg, tid, "delegate1", today=5)
assert status is TripStatus.APPROVED
entry = store._audit[-1]
assert "sup1" in entry.reason and "5" in entry.reason, entry.reason
print("delegation approval OK, reason:", entry.reason)

# revoked delegation should not count
store, reg = mk()
tid = trip_desk.file_trip(store, "staff1", 6, Region.ISLAND, 2, Vehicle.CAR, 0)
reg.save_delegation(Delegation("deleg2", "sup1", "delegate1", 6, 6, True))  # revoked
expect_failure(lambda: trip_desk.approve_trip(store, reg, tid, "delegate1", today=6), FailureCode.UNAUTHORIZED)
print("revoked delegation rejected OK")

# delegation checked against `today`, not trip.period
store, reg = mk()
tid = trip_desk.file_trip(store, "staff1", 7, Region.ISLAND, 2, Vehicle.CAR, 0)
reg.save_delegation(Delegation("deleg3", "sup1", "delegate1", 9, 9, False))  # in force only for period 9
expect_failure(lambda: trip_desk.approve_trip(store, reg, tid, "delegate1", today=7), FailureCode.UNAUTHORIZED)
status = trip_desk.approve_trip(store, reg, tid, "delegate1", today=9)
assert status is TripStatus.APPROVED
print("delegation checked against today, not trip.period OK")

# --- Reconciliation ---
store, reg = mk()
tid = trip_desk.file_trip(store, "staff1", 1, Region.ISLAND, 2, Vehicle.CAR, 0)  # committed 18000
trip_desk.approve_trip(store, reg, tid, "sup1", today=1)

# build a report for staff1/period1, Approved
rid = store.next_id()
from desk.reports import Report, ReportStatus
r = Report(rid, "staff1", "D1", 1, (Line(Category.TRAVEL, 15000, "hotel", True),), ReportStatus.APPROVED)
store.save_report(r)

# card txns: matched one (already counted) + unmatched open one
t_matched = CardTxn("txn1", "staff1", 1, 15000, Category.TRAVEL, "Hotel Co", CardStatus.MATCHED, matched=rid)
t_open = CardTxn("txn2", "staff1", 1, 500, Category.OTHER, "Snack", CardStatus.OPEN)
t_disputed = CardTxn("txn3", "staff1", 1, 200, Category.OTHER, "Taxi", CardStatus.DISPUTED)
reg.save_txn(t_matched)
reg.save_txn(t_open)
reg.save_txn(t_disputed)

actual = trip_desk.reconcile_trip(store, reg, tid, rid, "fin1")
assert actual == 15000 + 500 + 200, actual
t = store.trip(tid)
assert t.status is TripStatus.RECONCILED
assert set(t.reconciliation.transactions) == {"txn2", "txn3"}
assert t.reconciliation.committed == 18000
assert t.reconciliation.actual == 15700
print("reconcile OK, actual=", actual)

entry = store._audit[-1]
assert entry.from_status is TripStatus.APPROVED and entry.to_status is TripStatus.RECONCILED
assert "exceeds" not in entry.reason  # actual < committed here
print("reconcile audit OK:", entry.reason)

# reconcile again with unchanged inputs: succeeds, no new audit entry
before_audit_len = len(store._audit)
actual2 = trip_desk.reconcile_trip(store, reg, tid, rid, "fin1")
assert actual2 == actual
assert len(store._audit) == before_audit_len, "no new audit entry expected for unchanged reconciliation"
print("repeat reconcile unchanged -> no new audit OK")

# reconcile again with changed inputs (new open txn) -> new audit entry, replaces not adds
t_open2 = CardTxn("txn4", "staff1", 1, 100, Category.OTHER, "Coffee", CardStatus.OPEN)
reg.save_txn(t_open2)
actual3 = trip_desk.reconcile_trip(store, reg, tid, rid, "fin1")
assert actual3 == 15000 + 500 + 200 + 100
t = store.trip(tid)
assert set(t.reconciliation.transactions) == {"txn2", "txn3", "txn4"}
assert len(store._audit) == before_audit_len + 1
print("repeat reconcile changed -> new audit, replaces OK")

# reconcile with report not approved/paid -> conflict
store2, reg2 = mk()
tid2 = trip_desk.file_trip(store2, "staff1", 1, Region.ISLAND, 2, Vehicle.CAR, 0)
trip_desk.approve_trip(store2, reg2, tid2, "sup1", today=1)
rid2 = store2.next_id()
r2 = Report(rid2, "staff1", "D1", 1, (Line(Category.TRAVEL, 1000, "x", True),), ReportStatus.SUBMITTED)
store2.save_report(r2)
expect_failure(lambda: trip_desk.reconcile_trip(store2, reg2, tid2, rid2, "fin1"), FailureCode.CONFLICT)
print("reconcile against non-approved report -> Conflict OK")

print("ALL RECONCILE/DELEGATION CHECKS PASSED")
