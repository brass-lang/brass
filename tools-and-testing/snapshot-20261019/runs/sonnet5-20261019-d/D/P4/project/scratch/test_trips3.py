import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fake_host import FakeStore, FakeRegistry

from desk.staff import Staff, Department
from desk.ids import Role
from desk.records import Region, Vehicle, Delegation
from desk.errors import Failure, FailureCode
from desk.trips import TripStatus
from desk.trip_desk import file_trip, approve_trip

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


def new_store(sup_active=True):
    s = FakeStore()
    s.add_department(Department("D1", "DIR1", 1_000_000))
    s.add_staff(Staff("STAFF1", "A", "D1", "SUP1", Role.STAFF, True))
    s.add_staff(Staff("SUP1", "B", "D1", "DIR1", Role.SUPERVISOR, sup_active))
    s.add_staff(Staff("DIR1", "C", "D1", None, Role.DIRECTOR, True))
    s.add_staff(Staff("FIN1", "D", "D1", None, Role.FINANCE, True))
    s.add_staff(Staff("DEL1", "E", "D1", None, Role.STAFF, True))
    return s


# Nominal supervisor is inactive, no delegation: falls back to stand-in (director).
s = new_store(sup_active=False)
tid = file_trip(s, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg = FakeRegistry(s)
status = approve_trip(s, reg, tid, "DIR1", 1)
check("inactive nominal: stand-in (director) approves", status is TripStatus.APPROVED)

# Nominal supervisor is inactive, but a delegate from the supervisor exists: delegate can approve
# even though stand_in() alone (director's supervisor chain) would also work -- delegate should
# take precedence/also be accepted without requiring the stand-in path.
s2 = new_store(sup_active=False)
tid = file_trip(s2, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg2 = FakeRegistry(s2)
reg2.save_delegation(Delegation("DG1", "SUP1", "DEL1", 1, 3, False))
status = approve_trip(s2, reg2, tid, "DEL1", 1)
check("inactive nominal + delegate: delegate approves", status is TripStatus.APPROVED)

# Nominal supervisor active, but delegated to DEL1 anyway (vacation-style delegation): delegate can approve
s3 = new_store(sup_active=True)
tid = file_trip(s3, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg3 = FakeRegistry(s3)
reg3.save_delegation(Delegation("DG1", "SUP1", "DEL1", 1, 3, False))
status = approve_trip(s3, reg3, tid, "DEL1", 1)
check("active nominal + delegate: delegate approves too", status is TripStatus.APPROVED)

# Active nominal, unrelated staff member (not supervisor, not delegate): rejected
s4 = new_store(sup_active=True)
tid = file_trip(s4, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg4 = FakeRegistry(s4)
expect_failure("active nominal: unrelated staff rejected", FailureCode.UNAUTHORIZED,
               lambda: approve_trip(s4, reg4, tid, "DEL1", 1))

print(f"\n{PASS} passed, {FAIL} failed")
