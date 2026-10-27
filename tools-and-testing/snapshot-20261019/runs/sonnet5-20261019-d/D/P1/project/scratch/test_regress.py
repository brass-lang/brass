import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fakes import FakeStore, FakeRegistry, FakeLedger
from desk.ids import Role, Category
from desk.staff import Staff, Department
from desk import review, payment, queries, advance_desk
from desk.lines import Line
from desk.reports import Report, ReportStatus
from desk.errors import Failure, FailureCode

def mk():
    store = FakeStore()
    store.add_department(Department("D1", "dir1", budget=100_00))
    store.add_staff(Staff("staff1", "Staff One", "D1", "sup1", Role.STAFF, True))
    store.add_staff(Staff("sup1", "Sup One", "D1", "dir1", Role.SUPERVISOR, True))
    store.add_staff(Staff("dir1", "Dir One", "D1", None, Role.DIRECTOR, True))
    store.add_staff(Staff("fin1", "Fin One", "D1", None, Role.FINANCE, True))
    return store

def expect_failure(fn, code):
    try:
        fn()
        raise AssertionError("expected failure")
    except Failure as f:
        assert f.code is code, f"expected {code} got {f.code}: {f.message}"

store = mk()
rid = store.next_id()
r = Report(rid, "staff1", "D1", 1, (Line(Category.OTHER, 5000, "x", True),), ReportStatus.SUBMITTED)
store.save_report(r)
status = review.approve(store, rid, "sup1")
assert status is ReportStatus.APPROVED
print("plain report approval unchanged OK")

# budget exceeded without trips still refused for non-finance
store = mk()
rid = store.next_id()
r = Report(rid, "staff1", "D1", 1, (Line(Category.OTHER, 20000, "x", True),), ReportStatus.SUBMITTED)
store.save_report(r)
expect_failure(lambda: review.approve(store, rid, "sup1"), FailureCode.CONFLICT)
print("plain over-budget report refused for non-finance OK")

# advance approval unchanged
store = mk()
aid = advance_desk.request_advance(store, "staff1", 1, 5000)
status = advance_desk.approve_advance(store, aid, "sup1")
assert status.value == "Approved"
print("plain advance approval unchanged OK")

print("ALL REGRESSION CHECKS PASSED")
