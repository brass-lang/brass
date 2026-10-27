import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from fake_host import FakeStore, FakeLedger
from desk.staff import Staff, Department
from desk.ids import Role
from desk.lines import Line, Category
from desk import review, payment, queries
from desk.reports import ReportStatus
from desk.advances import AdvanceStatus
from desk.errors import Failure, FailureCode


def mkstore():
    store = FakeStore()
    store.add_department(Department("DEPT", "DIR1", 1_000_000))
    store.add_staff(Staff("STAFF1", "Grant", "DEPT", "SUP1", Role.STAFF, True))
    store.add_staff(Staff("SUP1", "Sattler", "DEPT", "DIR1", Role.SUPERVISOR, True))
    store.add_staff(Staff("DIR1", "Hammond", "DEPT", None, Role.DIRECTOR, True))
    store.add_staff(Staff("FIN1", "Arnold", "DEPT", None, Role.FINANCE, True))
    return store


def test_request_and_approve_small_advance():
    store = mkstore()
    aid = review.request_advance(store, "STAFF1", 5, 10_000)
    a = store.advance(aid)
    assert a.status is AdvanceStatus.REQUESTED
    assert a.amount == 10_000
    assert a.department == "DEPT"
    # small amount -> only supervisor needed (<=50000)
    status = review.approve_advance(store, aid, "SUP1")
    assert status is AdvanceStatus.APPROVED
    a = store.advance(aid)
    assert a.status is AdvanceStatus.APPROVED
    assert len(store._audit) == 1
    print("test_request_and_approve_small_advance OK")


def test_approve_refusals():
    store = mkstore()
    aid = review.request_advance(store, "STAFF1", 5, 10_000)
    try:
        review.approve_advance(store, aid, "STAFF1")
        assert False
    except Failure as f:
        assert f.code is FailureCode.UNAUTHORIZED
    try:
        review.approve_advance(store, aid, "DIR1")  # not the required approver (supervisor step)
        assert False
    except Failure as f:
        assert f.code is FailureCode.UNAUTHORIZED
    store.close_period_for_setup(5)
    try:
        review.approve_advance(store, aid, "SUP1")
        assert False
    except Failure as f:
        assert f.code is FailureCode.CONFLICT
    print("test_approve_refusals OK")


def test_multi_step_advance():
    store = mkstore()
    aid = review.request_advance(store, "STAFF1", 5, 100_000)  # > 50000 -> supervisor+director
    review.approve_advance(store, aid, "SUP1")
    a = store.advance(aid)
    assert a.status is AdvanceStatus.REQUESTED
    assert a.approvals == ("SUP1",)
    status = review.approve_advance(store, aid, "DIR1")
    assert status is AdvanceStatus.APPROVED
    print("test_multi_step_advance OK")


def test_budget_block_and_finance_override():
    store = mkstore()
    # big advance exceeding budget, needs finance step (>500000)
    aid = review.request_advance(store, "STAFF1", 5, 2_000_000)
    review.approve_advance(store, aid, "SUP1")
    review.approve_advance(store, aid, "DIR1")
    try:
        review.approve_advance(store, aid, "FIN1")
    except Failure:
        assert False, "finance should be able to override budget"
    a = store.advance(aid)
    assert a.status is AdvanceStatus.APPROVED
    print("test_budget_block_and_finance_override OK")


def test_pay_advance_and_against_full_cover():
    store = mkstore()
    ledger = FakeLedger()
    aid = review.request_advance(store, "STAFF1", 5, 50_000)
    review.approve_advance(store, aid, "SUP1")
    ref = payment.pay_advance(store, ledger, aid, "FIN1")
    assert ledger.calls[-1] == ("STAFF1", 50_000, aid, ref)
    a = store.advance(aid)
    assert a.status is AdvanceStatus.PAID
    assert a.reference == ref

    # build and approve a small report for 30000 (less than advance)
    rid = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid, "STAFF1")
    review.approve(store, rid, "SUP1")
    r = store.report(rid)
    assert r.status is ReportStatus.APPROVED

    result = payment.pay_against(store, ledger, rid, aid, "FIN1")
    assert result == "settled"
    r = store.report(rid)
    a = store.advance(aid)
    assert r.status is ReportStatus.PAID
    assert r.reference == ref  # took advance's ledger reference
    assert a.status is AdvanceStatus.SETTLED
    assert a.owed == 20_000
    # no new ledger call made
    assert len(ledger.calls) == 1
    print("test_pay_advance_and_against_full_cover OK")


def test_pay_against_partial_cover():
    store = mkstore()
    ledger = FakeLedger()
    aid = review.request_advance(store, "STAFF1", 5, 10_000)
    review.approve_advance(store, aid, "SUP1")
    payment.pay_advance(store, ledger, aid, "FIN1")

    rid = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid, "STAFF1")
    review.approve(store, rid, "SUP1")

    result = payment.pay_against(store, ledger, rid, aid, "FIN1")
    assert result != "settled"
    r = store.report(rid)
    a = store.advance(aid)
    assert r.status is ReportStatus.PAID
    assert r.reference == result
    assert a.status is AdvanceStatus.SETTLED
    assert a.owed == 0
    assert ledger.calls[-1] == ("STAFF1", 20_000, rid, result)
    print("test_pay_against_partial_cover OK")


def test_settle_conflicts():
    store = mkstore()
    ledger = FakeLedger()
    aid = review.request_advance(store, "STAFF1", 5, 10_000)
    review.approve_advance(store, aid, "SUP1")
    # not yet paid -> Conflict
    rid = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid, "STAFF1")
    review.approve(store, rid, "SUP1")
    try:
        payment.pay_against(store, ledger, rid, aid, "FIN1")
        assert False
    except Failure as f:
        assert f.code is FailureCode.CONFLICT

    payment.pay_advance(store, ledger, aid, "FIN1")
    # different period report
    aid2 = review.request_advance(store, "STAFF1", 6, 10_000)
    review.approve_advance(store, aid2, "SUP1")
    payment.pay_advance(store, ledger, aid2, "FIN1")
    rid2 = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid2, "STAFF1")
    review.approve(store, rid2, "SUP1")
    try:
        payment.pay_against(store, ledger, rid2, aid2, "FIN1")  # advance period 6, report period 5
        assert False
    except Failure as f:
        assert f.code is FailureCode.CONFLICT

    # settle once only
    payment.pay_against(store, ledger, rid, aid, "FIN1")
    rid3 = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid3, "STAFF1")
    review.approve(store, rid3, "SUP1")
    try:
        payment.pay_against(store, ledger, rid3, aid, "FIN1")  # already settled
        assert False
    except Failure as f:
        assert f.code is FailureCode.CONFLICT
    print("test_settle_conflicts OK")


def test_spend_and_statement_include_advances():
    store = mkstore()
    ledger = FakeLedger()
    aid = review.request_advance(store, "STAFF1", 5, 100_000)
    review.approve_advance(store, aid, "SUP1")
    review.approve_advance(store, aid, "DIR1")
    assert queries.spend(store, "DEPT", 5) == 100_000
    st = queries.statement(store, "DEPT", 5)
    assert st.spend == 100_000
    assert st.remaining == 900_000
    assert len(st.rows) == 1
    assert st.rows[0].id == aid
    assert st.rows[0].total == 100_000
    assert st.rows[0].budgeted == 100_000

    payment.pay_advance(store, ledger, aid, "FIN1")
    assert queries.spend(store, "DEPT", 5) == 100_000  # still counts while Paid

    rid = review.open_draft(store, "STAFF1", 5, Line(Category.OTHER, 30_000, "fuel", True))
    review.submit(store, rid, "STAFF1")
    review.approve(store, rid, "SUP1")
    payment.pay_against(store, ledger, rid, aid, "FIN1")
    # advance settled -> stops counting; report now counts instead
    assert queries.spend(store, "DEPT", 5) == 30_000
    print("test_spend_and_statement_include_advances OK")


def test_outstanding_advances():
    store = mkstore()
    ledger = FakeLedger()
    aid1 = review.request_advance(store, "STAFF1", 1, 10_000)
    review.approve_advance(store, aid1, "SUP1")
    payment.pay_advance(store, ledger, aid1, "FIN1")

    aid2 = review.request_advance(store, "STAFF1", 17, 10_000)
    review.approve_advance(store, aid2, "SUP1")
    payment.pay_advance(store, ledger, aid2, "FIN1")

    today = 18
    out = queries.outstanding_advances(store, today)
    # period 1 + 2 = 3 < 18 -> outstanding; period 17 + 2 = 19, not < 18 -> not outstanding
    assert out == [aid1], out
    print("test_outstanding_advances OK")


def test_request_advance_refusals():
    store = mkstore()
    store.add_staff(Staff("INACTIVE1", "Nedry", "DEPT", "SUP1", Role.STAFF, False))
    try:
        review.request_advance(store, "INACTIVE1", 5, 10_000)
        assert False
    except Failure as f:
        assert f.code is FailureCode.UNAUTHORIZED
    store.close_period_for_setup(9)
    try:
        review.request_advance(store, "STAFF1", 9, 10_000)
        assert False
    except Failure as f:
        assert f.code is FailureCode.CONFLICT
    try:
        review.request_advance(store, "STAFF1", 5, 0)
        assert False
    except Failure as f:
        assert f.code is FailureCode.INVALID_INPUT
    print("test_request_advance_refusals OK")


def test_pay_advance_ignores_closed_period():
    store = mkstore()
    ledger = FakeLedger()
    aid = review.request_advance(store, "STAFF1", 5, 10_000)
    review.approve_advance(store, aid, "SUP1")
    store.close_period_for_setup(5)
    ref = payment.pay_advance(store, ledger, aid, "FIN1")
    assert ref
    print("test_pay_advance_ignores_closed_period OK")


if __name__ == "__main__":
    test_request_and_approve_small_advance()
    test_approve_refusals()
    test_multi_step_advance()
    test_budget_block_and_finance_override()
    test_pay_advance_and_against_full_cover()
    test_pay_against_partial_cover()
    test_settle_conflicts()
    test_spend_and_statement_include_advances()
    test_outstanding_advances()
    test_request_advance_refusals()
    test_pay_advance_ignores_closed_period()
    print("ALL OK")
