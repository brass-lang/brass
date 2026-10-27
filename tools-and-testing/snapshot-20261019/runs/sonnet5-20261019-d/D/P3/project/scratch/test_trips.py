import sys
sys.path.insert(0, "/private/tmp/rerun-sonnet5-20261019-d/D/P3/project/src")
sys.path.insert(0, "/private/tmp/rerun-sonnet5-20261019-d/D/P3/project/scratch")

from fake_host import FakeStore, FakeRegistry, FailingAuditStore

from desk.errors import Failure, FailureCode
from desk.ids import Category, Role
from desk.lines import Line
from desk.records import CardStatus, CardTxn, Delegation, Region, Vehicle
from desk.reports import Report, ReportStatus
from desk.staff import Department, Staff
from desk.trips import TripStatus
from desk import trip_desk, review, payment, queries

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


def make_store():
    store = FakeStore()
    store.add_department(Department("D1", "director1", 10_000_000))
    store.add_staff(Staff("staff1", "Staff One", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("staff2", "Staff Two", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("sup1", "Sup One", "D1", "director1", Role.SUPERVISOR, True))
    store.add_staff(Staff("director1", "Director One", "D1", None, Role.DIRECTOR, True))
    store.add_staff(Staff("finance1", "Finance One", "D1", None, Role.FINANCE, True))
    store.add_staff(Staff("inactive1", "Inactive One", "D1", None, Role.STAFF, False))
    return store


# --- filing ---
store = make_store()
tid = trip_desk.file_trip(store, "staff1", 1, Region.ISLAND, 3, Vehicle.CAR, 100)
t = store.trip(tid)
check("file: committed priced correctly", t.committed == 9_000 * 3 + 60 * 100)
check("file: department set", t.department == "D1")
check("file: status Requested", t.status is TripStatus.REQUESTED)
check("file: not audited", len(store._audit) == 0)

expect_failure("file: both zero -> InvalidInput", FailureCode.INVALID_INPUT,
                lambda: trip_desk.file_trip(store, "staff1", 2, Region.ISLAND, 0, Vehicle.CAR, 0))
expect_failure("file: days over max -> InvalidInput", FailureCode.INVALID_INPUT,
                lambda: trip_desk.file_trip(store, "staff1", 2, Region.ISLAND, 31, Vehicle.CAR, 0))
expect_failure("file: km over max -> InvalidInput", FailureCode.INVALID_INPUT,
                lambda: trip_desk.file_trip(store, "staff1", 2, Region.ISLAND, 0, Vehicle.CAR, 2001))
expect_failure("file: duplicate open trip -> Conflict", FailureCode.CONFLICT,
                lambda: trip_desk.file_trip(store, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0))
expect_failure("file: inactive staff -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.file_trip(store, "inactive1", 1, Region.ISLAND, 1, Vehicle.CAR, 0))

store.close_period(99)
expect_failure("file: closed period -> Conflict", FailureCode.CONFLICT,
                lambda: trip_desk.file_trip(store, "staff1", 99, Region.ISLAND, 1, Vehicle.CAR, 0))

# zero-component trip still prices correctly (only days)
tid0 = trip_desk.file_trip(store, "staff2", 5, Region.MAINLAND, 10, Vehicle.TRUCK, 0)
t0 = store.trip(tid0)
check("file: km-zero component contributes zero", t0.committed == 6_000 * 10)

# a closed trip does not block a new one
tid_block = trip_desk.file_trip(store, "staff1", 7, Region.ISLAND, 1, Vehicle.CAR, 0)
trip_desk.close_trip(store, tid_block, "finance1", "no longer needed")
tid_again = trip_desk.file_trip(store, "staff1", 7, Region.ISLAND, 2, Vehicle.CAR, 0)
check("file: closed trip doesn't block refiling", tid_again != tid_block)

# --- amending ---
store2 = make_store()
tid = trip_desk.file_trip(store2, "staff1", 1, Region.ISLAND, 3, Vehicle.CAR, 0)
status = trip_desk.amend_trip(store2, tid, "staff1", Region.MAINLAND, 5, Vehicle.CAR, 0)
check("amend: reprices", store2.trip(tid).committed == 6_000 * 5)
check("amend: stays Requested if was Requested", status is TripStatus.REQUESTED)
check("amend: no audit if Requested->Requested", len(store2._audit) == 0)

expect_failure("amend: not the filer -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.amend_trip(store2, tid, "staff2", Region.ISLAND, 1, Vehicle.CAR, 0))
expect_failure("amend: both zero -> InvalidInput", FailureCode.INVALID_INPUT,
                lambda: trip_desk.amend_trip(store2, tid, "staff1", Region.ISLAND, 0, Vehicle.CAR, 0))

# --- approval: single step, no delegation ---
store3 = make_store()
tid = trip_desk.file_trip(store3, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # committed 9000, small => 1 step
expect_failure("approve: requester cannot approve own trip", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.approve_trip(store3, FakeRegistry(), tid, "staff1", 1))
expect_failure("approve: wrong approver -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.approve_trip(store3, FakeRegistry(), tid, "staff2", 1))
reg3 = FakeRegistry()
status = trip_desk.approve_trip(store3, reg3, tid, "sup1", 1)
check("approve: single step reaches Approved", status is TripStatus.APPROVED)
check("approve: audited", any(e.subject_id == tid and e.to_status is TripStatus.APPROVED for e in store3._audit))

# amend clears approvals and returns Approved -> Requested, audited
status2 = trip_desk.amend_trip(store3, tid, "staff1", Region.OFFSITE, 2, Vehicle.CAR, 0)
check("amend: Approved -> Requested", status2 is TripStatus.REQUESTED)
check("amend: audited when returning from Approved", any(e.to_status is TripStatus.REQUESTED and e.reason == "amended" for e in store3._audit))
t3 = store3.trip(tid)
check("amend: approvals cleared", t3.approvals == ())

# --- approval: delegation ---
store4 = make_store()
tid = trip_desk.file_trip(store4, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg4 = FakeRegistry()
# sup1 delegates to staff2 for periods 1-3
reg4.save_delegation(Delegation("DEL1", "sup1", "staff2", 1, 3, False))
status = trip_desk.approve_trip(store4, reg4, tid, "staff2", 1)  # today=1, in force
check("approve: delegate may approve", status is TripStatus.APPROVED)
entry = [e for e in store4._audit if e.subject_id == tid][0]
check("approve: delegation audit mentions delegator badge", "sup1" in entry.reason)
check("approve: delegation audit mentions period", "1" in entry.reason)

# revoked / out-of-force delegation does not count
store5 = make_store()
tid = trip_desk.file_trip(store5, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
reg5 = FakeRegistry()
reg5.save_delegation(Delegation("DEL2", "sup1", "staff2", 5, 6, False))  # not in force for today=1
expect_failure("approve: delegation out of force -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.approve_trip(store5, reg5, tid, "staff2", 1))

# --- approval: multi-step with budget check at last step ---
store6 = make_store()
# a large commitment forces supervisor -> director -> finance (3 steps)
tid = trip_desk.file_trip(store6, "staff1", 1, Region.OFFSITE, 30, Vehicle.BOAT, 2000)
t6 = store6.trip(tid)
print("committed for 3-step test:", t6.committed)
reg6 = FakeRegistry()
s1 = trip_desk.approve_trip(store6, reg6, tid, "sup1", 1)
check("approve: step1 stays Requested", s1 is TripStatus.REQUESTED)
s2 = trip_desk.approve_trip(store6, reg6, tid, "director1", 1)
check("approve: step2 stays Requested", s2 is TripStatus.REQUESTED)
s3 = trip_desk.approve_trip(store6, reg6, tid, "finance1", 1)
check("approve: step3 reaches Approved", s3 is TripStatus.APPROVED)

# department budget exceeded -> non-finance refused, finance can override
store7 = make_store()
store7.add_department(Department("D1", "director1", 10_000))  # tiny budget
tid = trip_desk.file_trip(store7, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # committed 9000 <= 10000, 1 step (supervisor)
# first trip fits; approve it to consume budget
trip_desk.approve_trip(store7, FakeRegistry(), tid, "sup1", 1)
tid2 = trip_desk.file_trip(store7, "staff2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)  # another 9000, total would exceed 10000
expect_failure("approve: over budget refused for non-finance", FailureCode.CONFLICT,
                lambda: trip_desk.approve_trip(store7, FakeRegistry(), tid2, "sup1", 1))
# Finance override
# tid2 is single-step (supervisor) by routing, so finance must act as supervisor's stand-in via role check;
# role_for(1) is SUPERVISOR, so required badge is "sup1", finance1 wouldn't be accepted as approver here.
# Let's instead directly test via a report large enough to force a finance step for the override test (see below).

# --- budget: trip counts remaining commitment only while Approved ---
store8 = make_store()
tid = trip_desk.file_trip(store8, "staff1", 1, Region.ISLAND, 10, Vehicle.CAR, 0)  # committed 90,000
trip_desk.approve_trip(store8, FakeRegistry(), tid, "sup1", 1)
trip_desk.approve_trip(store8, FakeRegistry(), tid, "director1", 1)
from desk.budget import department_spend
check("budget: approved trip counts full committed when uncovered", department_spend(store8, "D1", 1) == 90_000)

# a report by the same staff/period, once approved/paid, reduces the trip's remaining count
r = Report("R1", "staff1", "D1", 1, (Line(Category.TRAVEL, 20_000, "taxi", True),), ReportStatus.SUBMITTED)
store8.save_report(r)
# manually approve the report bypassing routing/budget checks (test-only) to inspect budget math
import dataclasses
store8.save_report(dataclasses.replace(r, status=ReportStatus.APPROVED))
check("budget: trip's remaining reduced by approved report", department_spend(store8, "D1", 1) == 90_000 - 20_000 + 20_000)
# note: department_spend ALSO counts the report itself (20,000) plus the trip's reduced remaining (70,000) = 90,000 total,
# i.e. total spend stays at the trip's committed amount once a covering report appears - no double count.

# --- approving a report beside a trip: no double counting at the report's own final approval ---
store9 = make_store()
store9.add_department(Department("D1", "director1", 100_000))
tid = trip_desk.file_trip(store9, "staff1", 1, Region.ISLAND, 10, Vehicle.CAR, 0)  # committed 90,000
trip_desk.approve_trip(store9, FakeRegistry(), tid, "sup1", 1)
trip_desk.approve_trip(store9, FakeRegistry(), tid, "director1", 1)
# department budget is 100,000; trip alone already counts 90,000 (uncovered)
rid = review.open_draft(store9, "staff1", 1, Line(Category.TRAVEL, 5_000, "meal", True))
review.submit(store9, rid, "staff1")
# approving this 5,000 report: if trip were still counted at 90,000 AND +5,000 added, total=95,000 <= 100,000 -> should succeed
status = review.approve(store9, rid, "sup1")
check("report-beside-trip: report approval succeeds without double counting", status is ReportStatus.APPROVED)
check("report-beside-trip: dept spend equals trip committed (90,000), not 95,000", department_spend(store9, "D1", 1) == 90_000)

# --- reconciling ---
storeR = make_store()
tid = trip_desk.file_trip(storeR, "staff1", 1, Region.ISLAND, 5, Vehicle.CAR, 0)  # committed 45,000
trip_desk.approve_trip(storeR, FakeRegistry(), tid, "sup1", 1)
rid = review.open_draft(storeR, "staff1", 1, Line(Category.TRAVEL, 45_000, "per diem", True))
review.submit(storeR, rid, "staff1")
review.approve(storeR, rid, "sup1")  # single step given small amount, but trip already approved reduces budget check amount... just check it completes
r_status = storeR.report(rid).status
check("reconcile setup: report reached Approved", r_status is ReportStatus.APPROVED)

regR = FakeRegistry()
regR.save_txn(CardTxn("TX1", "staff1", 1, 3_000, Category.OTHER, "cab", CardStatus.OPEN))
regR.save_txn(CardTxn("TX2", "staff1", 1, 1_000, Category.OTHER, "snack", CardStatus.DISPUTED))
regR.save_txn(CardTxn("TX3", "staff1", 1, 500, Category.OTHER, "matched-one", CardStatus.MATCHED, matched=rid))
actual = trip_desk.reconcile_trip(storeR, regR, tid, rid, "finance1")
check("reconcile: actual = report total + unmatched txns", actual == 45_000 + 3_000 + 1_000)
tR = storeR.trip(tid)
check("reconcile: status Reconciled", tR.status is TripStatus.RECONCILED)
check("reconcile: recorded committed/actual/report/txns", tR.reconciliation.committed == 45_000 and
      tR.reconciliation.actual == actual and tR.reconciliation.report == rid and
      set(tR.reconciliation.transactions) == {"TX1", "TX2"})
check("reconcile: audited", any(e.subject_id == tid and e.to_status is TripStatus.RECONCILED for e in storeR._audit))
check("reconcile: reconciled trip counts 0 toward budget", department_spend(storeR, "D1", 1) == 45_000)  # just the report now

# re-reconcile with unchanged inputs: saves same, no new audit entry
audit_count = len(storeR._audit)
actual2 = trip_desk.reconcile_trip(storeR, regR, tid, rid, "finance1")
check("reconcile again: same result", actual2 == actual)
check("reconcile again: no new audit entry when unchanged", len(storeR._audit) == audit_count)

# reconcile again with a changed input (new unmatched txn) -> new audit entry, replaces not adds
regR.save_txn(CardTxn("TX4", "staff1", 1, 2_000, Category.OTHER, "extra", CardStatus.OPEN))
actual3 = trip_desk.reconcile_trip(storeR, regR, tid, rid, "finance1")
check("reconcile again: recomputes with new txn", actual3 == actual + 2_000)
check("reconcile again: new audit entry written on change", len(storeR._audit) == audit_count + 1)
check("reconcile again: replaces, not adds", len(storeR.trip(tid).reconciliation.transactions) == 3)

# failure ordering: save succeeds, audit fails -> trip stays saved, retry w/ unchanged inputs succeeds without new audit
storeF = FailingAuditStore()
storeF.add_department(Department("D1", "director1", 10_000_000))
storeF.add_staff(Staff("staff1", "S1", "D1", "sup1", Role.STAFF, True))
storeF.add_staff(Staff("sup1", "Sup1", "D1", "director1", Role.SUPERVISOR, True))
storeF.add_staff(Staff("director1", "Dir1", "D1", None, Role.DIRECTOR, True))
storeF.add_staff(Staff("finance1", "Fin1", "D1", None, Role.FINANCE, True))
tidF = trip_desk.file_trip(storeF, "staff1", 1, Region.ISLAND, 5, Vehicle.CAR, 0)
trip_desk.approve_trip(storeF, FakeRegistry(), tidF, "sup1", 1)
ridF = review.open_draft(storeF, "staff1", 1, Line(Category.TRAVEL, 45_000, "per diem", True))
review.submit(storeF, ridF, "staff1")
review.approve(storeF, ridF, "sup1")
regF = FakeRegistry()
audit_before = len(storeF._audit)
storeF.fail_audit_next = True
expect_failure("reconcile: audit failure propagates", FailureCode.UNAVAILABLE,
                lambda: trip_desk.reconcile_trip(storeF, regF, tidF, ridF, "finance1"))
check("reconcile: trip saved Reconciled despite audit failure", storeF.trip(tidF).status is TripStatus.RECONCILED)
check("reconcile: no audit entry written on failure", len(storeF._audit) == audit_before)
# retry with unchanged inputs succeeds, and does NOT write the missing entry
actualF = trip_desk.reconcile_trip(storeF, regF, tidF, ridF, "finance1")
check("reconcile retry: succeeds", actualF == 45_000)
check("reconcile retry: still does not write the missing audit entry", len(storeF._audit) == audit_before)

# --- closing ---
storeC = make_store()
tid1 = trip_desk.file_trip(storeC, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
tid2 = trip_desk.file_trip(storeC, "staff2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
trip_desk.approve_trip(storeC, FakeRegistry(), tid2, "sup1", 1)
expect_failure("close_period: not finance -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: payment.close_period(storeC, 1, "staff1"))
payment.close_period(storeC, 1, "finance1")
check("close_period: Requested trip closed", storeC.trip(tid1).status is TripStatus.CLOSED)
check("close_period: Approved trip closed", storeC.trip(tid2).status is TripStatus.CLOSED)
check("close_period: period marked closed", storeC.period_closed(1))
expect_failure("close_period: already closed -> Conflict", FailureCode.CONFLICT,
                lambda: payment.close_period(storeC, 1, "finance1"))

# retry semantics: a trip closed but not audited (simulate) is skipped by retry, not re-audited
storeC2 = make_store()
tidX = trip_desk.file_trip(storeC2, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
tidY = trip_desk.file_trip(storeC2, "staff2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)


class PartiallyFailingStore(FakeStore):
    def __init__(self):
        super().__init__()
        self.audit_fail_for = None

    def append_audit(self, entry):
        if self.audit_fail_for is not None and entry.subject_id == self.audit_fail_for:
            raise Failure(FailureCode.UNAVAILABLE, "audit down")
        super().append_audit(entry)


storeC3 = PartiallyFailingStore()
storeC3.add_department(Department("D1", "director1", 10_000_000))
storeC3.add_staff(Staff("staff1", "S1", "D1", "sup1", Role.STAFF, True))
storeC3.add_staff(Staff("staff2", "S2", "D1", "sup1", Role.STAFF, True))
storeC3.add_staff(Staff("sup1", "Sup1", "D1", "director1", Role.SUPERVISOR, True))
storeC3.add_staff(Staff("director1", "Dir1", "D1", None, Role.DIRECTOR, True))
storeC3.add_staff(Staff("finance1", "Fin1", "D1", None, Role.FINANCE, True))
tA = trip_desk.file_trip(storeC3, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
tB = trip_desk.file_trip(storeC3, "staff2", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
storeC3.audit_fail_for = tB
expect_failure("close_period: fails on second trip's audit", FailureCode.UNAVAILABLE,
                lambda: payment.close_period(storeC3, 1, "finance1"))
check("close_period partial: first trip closed", storeC3.trip(tA).status is TripStatus.CLOSED)
check("close_period partial: second trip's save went through (closed) despite audit failure",
      storeC3.trip(tB).status is TripStatus.CLOSED)
check("close_period partial: period NOT closed yet", not storeC3.period_closed(1))
storeC3.audit_fail_for = None
payment.close_period(storeC3, 1, "finance1")  # retry
check("close_period retry: period now closed", storeC3.period_closed(1))
check("close_period retry: no duplicate audit entries for tA/tB closings",
      sum(1 for e in storeC3._audit if e.subject_id in (tA, tB)) == 1)  # only tA's close was audited; tB's close-audit never retried

# single early close
storeD = make_store()
tidE = trip_desk.file_trip(storeD, "staff1", 1, Region.ISLAND, 1, Vehicle.CAR, 0)
trip_desk.close_trip(storeD, tidE, "finance1", "trip cancelled")
check("close_trip: status Closed", storeD.trip(tidE).status is TripStatus.CLOSED)
check("close_trip: audited with reason", any(e.reason == "trip cancelled" for e in storeD._audit))
expect_failure("close_trip: not finance -> Unauthorized", FailureCode.UNAUTHORIZED,
                lambda: trip_desk.close_trip(storeD, tidE, "staff1", "x"))

# --- statement / spend ---
storeS = make_store()
storeS.add_department(Department("D1", "director1", 1_000_000))
tid = trip_desk.file_trip(storeS, "staff1", 1, Region.ISLAND, 10, Vehicle.CAR, 0)  # 90,000
trip_desk.approve_trip(storeS, FakeRegistry(), tid, "sup1", 1)
trip_desk.approve_trip(storeS, FakeRegistry(), tid, "director1", 1)
stmt = queries.statement(storeS, "D1", 1)
check("statement: spend includes trip", stmt.spend == 90_000)
check("statement: remaining reflects trip", stmt.remaining == 1_000_000 - 90_000)
check("statement: one row for the trip", len(stmt.rows) == 1 and stmt.rows[0].id == tid and stmt.rows[0].total == 90_000)
check("queries.spend: matches statement", queries.spend(storeS, "D1", 1) == 90_000)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
