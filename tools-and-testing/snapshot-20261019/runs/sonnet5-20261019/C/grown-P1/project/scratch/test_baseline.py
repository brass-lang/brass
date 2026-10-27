import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk.errors import Failure, FailureCode
from desk.ids import Role, Category
from desk.staff import Staff, Department
from desk.lines import Line
from desk.reports import ReportStatus
from desk import review, payment, queries
from test_advances import FakeStore, FakeLedger, setup, expect_failure


def test_basic_report_flow_unaffected_by_advances_code():
    store = setup()
    ledger = FakeLedger()
    rid = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 10_000, "t", True))
    review.submit(store, rid, "staffer")
    status = review.approve(store, rid, "sup1")
    assert status is ReportStatus.APPROVED
    ref = payment.pay(store, ledger, rid, "finance1")
    r = store.report(rid)
    assert r.status is ReportStatus.PAID and r.reference == ref
    assert queries.spend(store, "DEPT", 1) == 10_000
    stmt = queries.statement(store, "DEPT", 1)
    assert stmt.spend == 10_000 and len(stmt.rows) == 1
    assert stmt.rows[0].id == rid


def test_report_budget_exceeded_without_finance():
    store = setup()
    store.departments["DEPT"] = Department("DEPT", "director1", 5_000)
    rid = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 10_000, "t", True))
    review.submit(store, rid, "staffer")
    expect_failure(lambda: review.approve(store, rid, "sup1"), FailureCode.CONFLICT)


def test_report_pending_for():
    store = setup()
    rid = review.open_draft(store, "staffer", 1, Line(Category.OTHER, 10_000, "t", True))
    review.submit(store, rid, "staffer")
    pending = queries.pending_for(store, "sup1")
    assert pending == [rid]


if __name__ == "__main__":
    test_basic_report_flow_unaffected_by_advances_code()
    print("OK test_basic_report_flow_unaffected_by_advances_code")
    test_report_budget_exceeded_without_finance()
    print("OK test_report_budget_exceeded_without_finance")
    test_report_pending_for()
    print("OK test_report_pending_for")
    print("ALL PASS")
