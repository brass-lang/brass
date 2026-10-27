import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fake_host import FakeStore, FakeRegistry, FakeLedger

from desk.staff import Staff, Department
from desk.ids import Role
from desk.records import Region, Vehicle, Delegation, CardTxn, CardStatus, Category
from desk.errors import Failure, FailureCode
from desk.trips import TripStatus
from desk.trip_desk import file_trip, amend_trip, approve_trip, reconcile_trip, close_trip
from desk.reports import Report, ReportStatus
from desk.lines import Line
from desk import review, payment, queries

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


def new_store():
    s = FakeStore()
    s.add_department(Department("D1", "DIR1", 1_000_000))
    s.add_staff(Staff("STAFF1", "A", "D1", "SUP1", Role.STAFF, True))
    s.add_staff(Staff("SUP1", "B", "D1", "DIR1", Role.SUPERVISOR, True))
    s.add_staff(Staff("DIR1", "C", "D1", None, Role.DIRECTOR, True))
    s.add_staff(Staff("FIN1", "D", "D1", None, Role.FINANCE, True))
    return s


# --- filing ---
s = new_store()
tid = file_trip(s, "STAFF1", 1, Region.ISLAND, 3, Vehicle.CAR, 10)
t = s.trip(tid)
check("file: committed priced", t.committed == 9000 * 3 + 60 * 10)
check("file: status requested", t.status is TripStatus.REQUESTED)
check("file: region/vehicle recorded even if zero-day", t.plan.region is Region.ISLAND and t.plan.vehicle is Vehicle.CAR)

expect_failure("file: both zero is InvalidInput", FailureCode.INVALID_INPUT,
               lambda: file_trip(s, "STAFF1", 2, Region.ISLAND, 0, Vehicle.CAR, 0))
expect_failure("file: days out of range", FailureCode.INVALID_INPUT,
               lambda: file_trip(s, "STAFF1", 2, Region.ISLAND, 31, Vehicle.CAR, 0))
expect_failure("file: one open trip per period", FailureCode.CONFLICT,
               lambda: file_trip(s, "STAFF1", 1, Region.MAINLAND, 1, Vehicle.TRUCK, 0))

# zero-day/zero-km component contributes zero, with region/vehicle still recorded
tid2 = file_trip(s, "STAFF1", 2, Region.MAINLAND, 0, Vehicle.TRUCK, 100)
t2 = s.trip(tid2)
check("file: zero days contributes zero", t2.committed == 90 * 100)

# closed period
s.close_period(5)
expect_failure("file: closed period", FailureCode.CONFLICT,
               lambda: file_trip(s, "STAFF1", 5, Region.ISLAND, 1, Vehicle.CAR, 0))

# --- amending ---
s2 = new_store()
tid = file_trip(s2, "STAFF1", 1, Region.ISLAND, 3, Vehicle.CAR, 10)
status = amend_trip(s2, tid, "STAFF1", Region.OFFSITE, 5, Vehicle.BOAT, 0)
t = s2.trip(tid)
check("amend: repriced", t.committed == 12000 * 5)
check("amend: status requested", status is TripStatus.REQUESTED)

expect_failure("amend: not owner", FailureCode.UNAUTHORIZED, lambda: amend_trip(s2, tid, "SUP1", Region.ISLAND, 1, Vehicle.CAR, 0))

# approve fully then amend returns to requested + audited
s3 = new_store()
tid = file_trip(s3, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # 9000, 1 step (supervisor only)
approve_trip(s3, FakeRegistry(s3), tid, "SUP1", 1)
t = s3.trip(tid)
check("approve: single-step to approved", t.status is TripStatus.APPROVED)
before_audit_len = len(s3.audit)
amend_trip(s3, tid, "STAFF1", Region.ISLAND, 2, Vehicle.CAR, 0)
t = s3.trip(tid)
check("amend after approved: back to requested", t.status is TripStatus.REQUESTED)
check("amend after approved: approvals cleared", t.approvals == ())
check("amend after approved: audited", len(s3.audit) == before_audit_len + 1)
last = s3.audit[-1]
check("amend audit: from Approved to Requested", last.from_status is TripStatus.APPROVED and last.to_status is TripStatus.REQUESTED)

expect_failure("amend: reconciled trip is conflict", FailureCode.CONFLICT, lambda: (
    s3.save_trip(__import__('dataclasses').replace(s3.trip(tid), status=TripStatus.RECONCILED)),
    amend_trip(s3, tid, "STAFF1", Region.ISLAND, 1, Vehicle.CAR, 0))[1])

# --- approving: multi-step with budget ---
s4 = new_store()
# big committed amount to force 3 steps (DIRECTOR_UP_TO=500_000)
tid = file_trip(s4, "STAFF1", 1, Region.OFFSITE, 30, Vehicle.CAR, 2000)  # 360000 + 120000=480000 -> <=500000 -> 2 steps actually
t = s4.trip(tid)
print("committed", t.committed)

# force 3-step: need > 500_000
tid3 = file_trip(s4, "STAFF1", 2, Region.OFFSITE, 30, Vehicle.BOAT, 2000)  # 360000 + 500000=860000 -> 3 steps
t3 = s4.trip(tid3)
check("3-step committed over DIRECTOR_UP_TO", t3.committed > 500_000)

reg4 = FakeRegistry(s4)
status = approve_trip(s4, reg4, tid3, "SUP1", 2)
check("3-step: step1 stays requested", status is TripStatus.REQUESTED)
status = approve_trip(s4, reg4, tid3, "DIR1", 2)
check("3-step: step2 stays requested", status is TripStatus.REQUESTED)
expect_failure("3-step: non-finance cannot finalize", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s4, reg4, tid3, "SUP1", 2))
status = approve_trip(s4, reg4, tid3, "FIN1", 2)
check("3-step: finance finalizes", status is TripStatus.APPROVED)

# requester cannot approve own trip
expect_failure("approve: requester cannot approve own trip", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s4, reg4, tid, "STAFF1", 1))

# not next approver
expect_failure("approve: wrong approver", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s4, reg4, tid, "FIN1", 1))

# --- delegation ---
s5 = new_store()
s5.add_staff(Staff("DEL1", "E", "D1", None, Role.STAFF, True))
tid = file_trip(s5, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # 1 step, supervisor
reg5 = FakeRegistry(s5)
reg5.save_delegation(Delegation("DG1", "SUP1", "DEL1", 1, 3, False))
status = approve_trip(s5, reg5, tid, "DEL1", 2)  # today=2, in force [1,3]
check("delegate: approves on behalf", status is TripStatus.APPROVED)
last = s5.audit[-1]
check("delegate: audit mentions delegator badge", "SUP1" in last.reason)
check("delegate: audit mentions today's period", "2" in last.reason)

# delegation outside force range (today) does not count
s5b = new_store()
s5b.add_staff(Staff("DEL1", "E", "D1", None, Role.STAFF, True))
tid = file_trip(s5b, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg5b = FakeRegistry(s5b)
reg5b.save_delegation(Delegation("DG1", "SUP1", "DEL1", 5, 6, False))
expect_failure("delegate: out of force range rejected", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s5b, reg5b, tid, "DEL1", 2))

# revoked delegation doesn't count even if approvals already given stay valid is N/A single-step here
s5c = new_store()
s5c.add_staff(Staff("DEL1", "E", "D1", None, Role.STAFF, True))
tid = file_trip(s5c, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg5c = FakeRegistry(s5c)
reg5c.save_delegation(Delegation("DG1", "SUP1", "DEL1", 1, 3, True))  # revoked
expect_failure("delegate: revoked rejected", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s5c, reg5c, tid, "DEL1", 2))

print(f"\n{PASS} passed, {FAIL} failed")
