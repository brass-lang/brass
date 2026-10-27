import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fake_host import FakeStore, FakeRegistry, FakeLedger

from desk.staff import Staff, Department
from desk.ids import Role, Category
from desk.records import Region, Vehicle, Delegation, CardTxn, CardStatus
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


def new_store(budget=1_000_000):
    s = FakeStore()
    s.add_department(Department("D1", "DIR1", budget))
    s.add_staff(Staff("STAFF1", "A", "D1", "SUP1", Role.STAFF, True))
    s.add_staff(Staff("SUP1", "B", "D1", "DIR1", Role.SUPERVISOR, True))
    s.add_staff(Staff("DIR1", "C", "D1", None, Role.DIRECTOR, True))
    s.add_staff(Staff("FIN1", "D", "D1", None, Role.FINANCE, True))
    return s


# --- budget at final approval (1-step case: supervisor is the only, and final, approver) ---
s = new_store(budget=10_000)
tid = file_trip(s, "STAFF1", 1, Region.ISLAND, 2, Vehicle.CAR, 0)  # 18000 > 10000 budget, 1 step (supervisor)
reg = FakeRegistry(s)
expect_failure("approve: over budget rejected for non-finance", FailureCode.CONFLICT,
               lambda: approve_trip(s, reg, tid, "SUP1", 1))
check("approve: rejected attempt did not save partial state", s.trip(tid).status is TripStatus.REQUESTED)

# 3-step case so Finance is the required (and final) approver, and can override
s9 = new_store(budget=10_000)
tid3 = file_trip(s9, "STAFF1", 1, Region.OFFSITE, 30, Vehicle.BOAT, 2000)  # 360000+500000=860000, 3 steps
reg9 = FakeRegistry(s9)
approve_trip(s9, reg9, tid3, "SUP1", 1)
approve_trip(s9, reg9, tid3, "DIR1", 1)
status = approve_trip(s9, reg9, tid3, "FIN1", 1)
check("approve: finance can override budget at final step", status is TripStatus.APPROVED)
check("approve: override noted in audit", "override" in s9.audit[-1].reason)

# --- budget check counts trip minus approved/paid reports ---
s2 = new_store(budget=20_000)
tid = file_trip(s2, "STAFF1", 1, Region.ISLAND, 2, Vehicle.CAR, 0)  # committed 18000
reg2 = FakeRegistry(s2)
status = approve_trip(s2, reg2, tid, "SUP1", 1)
check("trip within fresh budget approved", status is TripStatus.APPROVED)
check("spend counts trip remaining", queries.spend(s2, "D1", 1) == 18000)

# approve a report for the same staff/period that reduces the trip's remaining commitment
rid = s2.next_id()
s2.save_report(Report(rid, "STAFF1", "D1", 1, (Line(Category.TRAVEL, 18000, "per diem", True),), ReportStatus.SUBMITTED))
status = review.approve(s2, rid, "SUP1")
check("report approved despite trip's full committed amount", status is ReportStatus.APPROVED)
r = s2.report(rid)
check("report saved approved", r.status is ReportStatus.APPROVED)
check("spend now counts report + trip remaining(0)", queries.spend(s2, "D1", 1) == 18000)
stmt = queries.statement(s2, "D1", 1)
trip_rows = [row for row in stmt.rows if row.id == tid]
check("trip with zero remaining has no statement row", len(trip_rows) == 0)

# --- reconciling ---
s3 = new_store()
tid = file_trip(s3, "STAFF1", 1, Region.ISLAND, 2, Vehicle.CAR, 10)  # committed 18000+600=18600
reg3 = FakeRegistry(s3)
approve_trip(s3, reg3, tid, "SUP1", 1)
rid = s3.next_id()
s3.save_report(Report(rid, "STAFF1", "D1", 1, (Line(Category.TRAVEL, 5000, "hotel", True),), ReportStatus.APPROVED))
reg3.save_txn(CardTxn("TX1", "STAFF1", 1, 2500, Category.OTHER, "shop", CardStatus.OPEN, None))
reg3.save_txn(CardTxn("TX2", "STAFF1", 1, 1000, Category.OTHER, "shop2", CardStatus.DISPUTED, None))
reg3.save_txn(CardTxn("TX3", "STAFF1", 1, 999, Category.OTHER, "shop3", CardStatus.MATCHED, rid))
reg3.save_txn(CardTxn("TX4", "STAFF1", 2, 777, Category.OTHER, "othermonth", CardStatus.OPEN, None))
actual = reconcile_trip(s3, reg3, tid, rid, "FIN1")
check("reconcile: actual = report total + unmatched same-period txns", actual == 5000 + 2500 + 1000)
t = s3.trip(tid)
check("reconcile: status Reconciled", t.status is TripStatus.RECONCILED)
check("reconcile: committed recorded", t.reconciliation.committed == 18600)
check("reconcile: report id recorded", t.reconciliation.report == rid)
check("reconcile: txn ids recorded (order-independent)", set(t.reconciliation.transactions) == {"TX1", "TX2"})
check("reconcile: audit written", s3.audit[-1].subject.value == "Trip")
check("reconcile: exceeds-committed note absent (actual < committed)", "exceeds" not in s3.audit[-1].reason)

# reconcile again with unchanged inputs: saves same, no new audit entry
audit_len = len(s3.audit)
actual2 = reconcile_trip(s3, reg3, tid, rid, "FIN1")
check("reconcile again: same result", actual2 == actual)
check("reconcile again: no new audit entry when unchanged", len(s3.audit) == audit_len)

# reconcile again with a change (new txn) -> new audit entry, replaces not adds
reg3.save_txn(CardTxn("TX5", "STAFF1", 1, 300, Category.OTHER, "shop5", CardStatus.OPEN, None))
actual3 = reconcile_trip(s3, reg3, tid, rid, "FIN1")
check("reconcile again changed: new total", actual3 == actual + 300)
check("reconcile again changed: new audit entry written", len(s3.audit) == audit_len + 1)
t = s3.trip(tid)
check("reconcile again changed: replaces, doesn't add", t.reconciliation.actual == actual3)

# reconciling with report exceeding committed -> audit notes it
s4 = new_store()
tid = file_trip(s4, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # committed 9000
reg4 = FakeRegistry(s4)
approve_trip(s4, reg4, tid, "SUP1", 1)
rid = s4.next_id()
s4.save_report(Report(rid, "STAFF1", "D1", 1, (Line(Category.TRAVEL, 50000, "big", True),), ReportStatus.APPROVED))
actual = reconcile_trip(s4, reg4, tid, rid, "FIN1")
check("reconcile: exceeding committed not refused", actual == 50000)
check("reconcile: audit notes actual exceeds committed", "exceeds" in s4.audit[-1].reason)

# reconcile refusals
s5 = new_store()
tid = file_trip(s5, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg5 = FakeRegistry(s5)
rid = s5.next_id()
s5.save_report(Report(rid, "STAFF1", "D1", 1, (Line(Category.TRAVEL, 100, "x", True),), ReportStatus.SUBMITTED))
expect_failure("reconcile: trip not approved yet -> conflict", FailureCode.CONFLICT,
               lambda: reconcile_trip(s5, reg5, tid, rid, "FIN1"))
approve_trip(s5, reg5, tid, "SUP1", 1)
expect_failure("reconcile: report not approved/paid -> conflict", FailureCode.CONFLICT,
               lambda: reconcile_trip(s5, reg5, tid, rid, "FIN1"))
expect_failure("reconcile: not finance -> unauthorized", FailureCode.UNAUTHORIZED,
               lambda: reconcile_trip(s5, reg5, tid, rid, "STAFF1"))

# --- closing ---
s6 = new_store()
tid = file_trip(s6, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
close_trip(s6, tid, "FIN1", "trip cancelled")
t = s6.trip(tid)
check("close_trip: status closed", t.status is TripStatus.CLOSED)
check("close_trip: audited", s6.audit[-1].reason == "trip cancelled")
# a closed trip does not block a new filing for the same period
tid2 = file_trip(s6, "STAFF1", 1, Region.MAINLAND, 1, Vehicle.TRUCK, 0)
check("closed trip doesn't block new filing", tid2 != tid)

expect_failure("close_trip: reconciled trip cannot be closed", FailureCode.CONFLICT, lambda: close_trip(s6, tid, "FIN1", "x"))

# --- close_period closes open trips ---
s7 = new_store()
tid_req = file_trip(s7, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
s7.add_staff(Staff("STAFF2", "F", "D1", "SUP1", Role.STAFF, True))
tid_app = file_trip(s7, "STAFF2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg7 = FakeRegistry(s7)
approve_trip(s7, reg7, tid_app, "SUP1", 1)
payment.close_period(s7, 1, "FIN1")
check("close_period: requested trip closed", s7.trip(tid_req).status is TripStatus.CLOSED)
check("close_period: approved trip closed", s7.trip(tid_app).status is TripStatus.CLOSED)
check("close_period: period closed", s7.period_closed(1))
check("close_period: trips audited", any(e.subject_id == tid_req for e in s7.audit) and any(e.subject_id == tid_app for e in s7.audit))

# reconciled trip is never closed by close_period
s8 = new_store()
tid = file_trip(s8, "STAFF1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg8 = FakeRegistry(s8)
approve_trip(s8, reg8, tid, "SUP1", 1)
rid = s8.next_id()
s8.save_report(Report(rid, "STAFF1", "D1", 1, (Line(Category.TRAVEL, 100, "x", True),), ReportStatus.APPROVED))
reconcile_trip(s8, reg8, tid, rid, "FIN1")
payment.close_period(s8, 1, "FIN1")
check("close_period: reconciled trip untouched", s8.trip(tid).status is TripStatus.RECONCILED)

print(f"\n{PASS} passed, {FAIL} failed")
