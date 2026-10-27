import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fakes import FakeStore, FakeRegistry, FakeLedger
from desk.ids import Role
from desk.staff import Staff, Department
from desk.records import Region, Vehicle, Delegation, CardTxn, CardStatus
from desk.trips import TripStatus
from desk import trip_desk, review, payment, queries, reports as reports_mod, lines
from desk.lines import Line
from desk.ids import Category
from desk.errors import Failure, FailureCode

def mk():
    store = FakeStore()
    reg = FakeRegistry()
    store.add_department(Department("D1", "dir1", budget=10_000_00))
    store.add_staff(Staff("staff1", "Staff One", "D1", "sup1", Role.STAFF, True))
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

# 1. Filing basics
store, reg = mk()
tid = trip_desk.file_trip(store, "staff1", 1, Region.ISLAND, 2, Vehicle.CAR, 0)
t = store.trip(tid)
assert t.committed == 9_000*2, t.committed
assert t.status is TripStatus.REQUESTED
print("filing basic OK")

# both zero -> InvalidInput
expect_failure(lambda: trip_desk.file_trip(store, "staff1", 2, Region.ISLAND, 0, Vehicle.CAR, 0), FailureCode.INVALID_INPUT)
print("both-zero InvalidInput OK")

# duplicate open trip -> Conflict
expect_failure(lambda: trip_desk.file_trip(store, "staff1", 1, Region.MAINLAND, 1, Vehicle.CAR, 0), FailureCode.CONFLICT)
print("duplicate open trip Conflict OK")

# 2. Approve small trip (within SUPERVISOR_ONLY_UP_TO) - single step by supervisor
status = trip_desk.approve_trip(store, reg, tid, "sup1", today=1)
assert status is TripStatus.APPROVED, status
t = store.trip(tid)
assert t.status is TripStatus.APPROVED
assert len(store._audit) == 1
entry = store._audit[0]
assert entry.to_status is TripStatus.APPROVED
assert entry.reason == "approved", entry.reason
print("single-step approval OK")

# 3. Budget counts via statement
stmt = queries.statement(store, "D1", 1)
assert stmt.spend == 18_000, stmt.spend
trip_rows = [r for r in stmt.rows if r.id == tid]
assert len(trip_rows) == 1 and trip_rows[0].total == 18_000
print("statement trip row OK")

# 4. Amend trip: Approved -> Requested, clears approvals, reprices
status = trip_desk.amend_trip(store, tid, "staff1", Region.OFFSITE, 1, Vehicle.CAR, 0)
assert status is TripStatus.REQUESTED, status
t = store.trip(tid)
assert t.committed == 12_000, t.committed
assert t.approvals == ()
assert len(store._audit) == 2
entry = store._audit[1]
assert entry.from_status is TripStatus.APPROVED and entry.to_status is TripStatus.REQUESTED
print("amend OK, audited")

# amend by someone else -> Unauthorized
expect_failure(lambda: trip_desk.amend_trip(store, tid, "sup1", Region.OFFSITE, 1, Vehicle.CAR, 0), FailureCode.UNAUTHORIZED)
print("amend unauthorized OK")

# re-approve
status = trip_desk.approve_trip(store, reg, tid, "sup1", today=1)
assert status is TripStatus.APPROVED
print("re-approve OK")

# 5. amend on reconciled/closed -> conflict; test via closing
store2, reg2 = mk()
tid2 = trip_desk.file_trip(store2, "staff1", 2, Region.MAINLAND, 1, Vehicle.CAR, 0)
trip_desk.close_trip(store2, tid2, "fin1", "trip cancelled")
t2 = store2.trip(tid2)
assert t2.status is TripStatus.CLOSED
expect_failure(lambda: trip_desk.amend_trip(store2, tid2, "staff1", Region.MAINLAND, 1, Vehicle.CAR, 0), FailureCode.CONFLICT)
print("amend on closed -> conflict OK")

# filing again in same period after Closed is OK (closed doesn't block)
tid3 = trip_desk.file_trip(store2, "staff1", 2, Region.MAINLAND, 2, Vehicle.CAR, 0)
print("file after closed OK")

# 6. Multi-step approval requiring director then finance, with budget check
store3, reg3 = mk()
# large trip to force 3 steps (DIRECTOR_UP_TO=500_000) - need committed > 500_000
# max per-plan amount is 360000(per diem)+500000(boat mileage)=860000, use boat
tid4 = trip_desk.file_trip(store3, "staff1", 3, Region.OFFSITE, 30, Vehicle.BOAT, 2000)
t4 = store3.trip(tid4)
print("big trip committed:", t4.committed)
assert t4.committed > 500_000

# step 1: supervisor
s = trip_desk.approve_trip(store3, reg3, tid4, "sup1", today=3)
assert s is TripStatus.REQUESTED
# step1 by staff1 self -> unauthorized
expect_failure(lambda: trip_desk.approve_trip(store3, reg3, tid4, "staff1", today=3), FailureCode.UNAUTHORIZED)
# step 2: director
s = trip_desk.approve_trip(store3, reg3, tid4, "dir1", today=3)
assert s is TripStatus.REQUESTED
# step 3: needs finance, department budget 1,000,000 < committed 860000+? let's check department budget sufficient
dept = store3.department("D1")
print("budget", dept.budget, "committed", t4.committed)
# finance step
s = trip_desk.approve_trip(store3, reg3, tid4, "fin1", today=3)
assert s is TripStatus.APPROVED
print("multi-step approval with finance OK")

print("ALL BASIC CHECKS PASSED")
