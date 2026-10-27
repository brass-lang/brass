import sys
sys.path.insert(0, "src")
sys.path.insert(0, "scratch")

from harness import build_store, FakeLedger
from desk.advances import request_advance, approve_advance, pay_advance, pay_against, outstanding_advances
from desk.records import AdvanceStatus
from desk.errors import Failure, FailureCode
from desk.reports import ReportStatus
from desk.review import open_draft, submit, approve
from desk.lines import Line
from desk.ids import Category
from desk.queries import spend, statement

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

def test_request_and_approve_small():
    s = build_store()
    aid = request_advance(s, "staff1", 1, 10_000)
    a = s.advance(aid)
    check(a.status is AdvanceStatus.REQUESTED, "status")
    check(a.badge == "staff1" and a.department == "eng" and a.amount == 10_000, "fields")
    check(s.audit_log == [], "requesting is not audited")

    status = approve_advance(s, aid, "sup1")  # <= 50000 => 1 step, supervisor only
    check(status is AdvanceStatus.APPROVED, "approved after 1 step")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.APPROVED, "store updated")
    check(len(s.audit_log) == 1, "one audit entry")
    e = s.audit_log[0]
    check(e.who == "sup1" and e.report == aid and e.to_status is AdvanceStatus.APPROVED, "entry fields")
    print("test_request_and_approve_small OK")

def test_approve_requires_right_person():
    s = build_store()
    aid = request_advance(s, "staff1", 1, 10_000)
    try:
        approve_advance(s, aid, "dir1")
        raise AssertionError("should have failed")
    except Failure as f:
        check(f.code is FailureCode.UNAUTHORIZED, "wrong approver -> unauthorized")
    print("test_approve_requires_right_person OK")

def test_requester_cannot_approve():
    s = build_store()
    aid = request_advance(s, "staff1", 1, 10_000)
    try:
        approve_advance(s, aid, "staff1")
        raise AssertionError("should have failed")
    except Failure as f:
        check(f.code is FailureCode.UNAUTHORIZED, "requester cannot approve")
    print("test_requester_cannot_approve OK")

def test_multi_step_approval():
    s = build_store()
    aid = request_advance(s, "staff1", 1, 100_000)  # >50000 <=500000 => 2 steps: supervisor, director
    status = approve_advance(s, aid, "sup1")
    check(status is AdvanceStatus.REQUESTED, "still requested after step 1")
    a = s.advance(aid)
    check(a.approvals == ("sup1",), "approval recorded")
    check(len(s.audit_log) == 1 and s.audit_log[0].reason == "approved; awaiting the next approver", "interim audit")

    status = approve_advance(s, aid, "dir1")
    check(status is AdvanceStatus.APPROVED, "approved after step 2")
    check(len(s.audit_log) == 2, "two audit entries")
    print("test_multi_step_approval OK")

def test_closed_period_blocks_request_and_approve():
    s = build_store()
    s.close_period(1)
    try:
        request_advance(s, "staff1", 1, 10_000)
        raise AssertionError("should fail - closed period")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "closed period request")

    s2 = build_store()
    aid = request_advance(s2, "staff1", 1, 10_000)
    s2.close_period(1)
    try:
        approve_advance(s2, aid, "sup1")
        raise AssertionError("should fail - closed period")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "closed period approve")
    print("test_closed_period_blocks_request_and_approve OK")

def test_budget_blocks_unless_finance():
    s = build_store()
    from dataclasses import replace
    s.departments["eng"] = replace(s.departments["eng"], budget=5_000)
    aid = request_advance(s, "staff1", 1, 10_000)
    try:
        approve_advance(s, aid, "sup1")
        raise AssertionError("should fail - over budget")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "over budget conflict")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.REQUESTED, "rejected approval does not change status")
    print("test_budget_blocks_unless_finance OK (supervisor-only step has no finance override)")

def test_budget_override_by_finance_on_final_step():
    s = build_store()
    from dataclasses import replace
    s.departments["eng"] = replace(s.departments["eng"], budget=500_000)
    aid = request_advance(s, "staff1", 1, 600_000)  # >500,000 -> 3 steps: sup, dir, finance
    approve_advance(s, aid, "sup1")
    approve_advance(s, aid, "dir1")
    status = approve_advance(s, aid, "fin1")
    check(status is AdvanceStatus.APPROVED, "finance overrides budget on the final (finance) step")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.APPROVED, "approved despite over-budget")
    check(s.audit_log[-1].reason == "approved; budget override", "override reason recorded")
    print("test_budget_override_by_finance_on_final_step OK")

def test_pay_advance():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")
    ref = pay_advance(s, ledger, aid, "fin1")
    check(ledger.calls == [("staff1", 10_000, aid)], "ledger called with full amount and advance id as key")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.PAID and a.reference == ref, "paid status + reference")
    check(s.audit_log[-1].to_status is AdvanceStatus.PAID, "paid audit entry")
    print("test_pay_advance OK")

def test_pay_advance_closed_period_allowed():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")
    s.close_period(1)
    ref = pay_advance(s, ledger, aid, "fin1")
    check(ref is not None, "paying an advance ignores closed period")
    print("test_pay_advance_closed_period_allowed OK")

def make_report(s, badge, period, amount):
    rid = open_draft(s, badge, period, Line(Category.OTHER, amount, "x", True))
    submit(s, rid, badge)
    return rid

def test_pay_against_partial():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 4_000)
    approve_advance(s, aid, "sup1")
    pay_advance(s, ledger, aid, "fin1")

    rid = make_report(s, "staff1", 1, 10_000)
    approve(s, rid, "sup1")  # <=50000 -> 1 step
    result = pay_against(s, ledger, rid, aid, "fin1")
    check(result != "settled", "partial coverage pays via ledger")
    check(ledger.calls[-1] == ("staff1", 6_000, rid), "ledger paid the difference")
    r = s.report(rid)
    check(r.status is ReportStatus.PAID and r.reference == result, "report paid with new reference")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.SETTLED and a.owed == 0, "advance settled, owed 0 (report covered it)")
    check(s.audit_log[-2].report == rid and s.audit_log[-2].to_status is ReportStatus.PAID, "report paid entry")
    check(s.audit_log[-1].report == aid and s.audit_log[-1].to_status is AdvanceStatus.SETTLED, "advance settled entry")
    print("test_pay_against_partial OK")

def test_pay_against_full_coverage():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")
    advance_ref = pay_advance(s, ledger, aid, "fin1")

    rid = make_report(s, "staff1", 1, 4_000)
    approve(s, rid, "sup1")
    calls_before = len(ledger.calls)
    result = pay_against(s, ledger, rid, aid, "fin1")
    check(result == "settled", "advance covers whole report -> 'settled'")
    check(len(ledger.calls) == calls_before, "nothing paid through ledger")
    r = s.report(rid)
    check(r.reference == advance_ref, "report takes the advance's ledger reference")
    a = s.advance(aid)
    check(a.status is AdvanceStatus.SETTLED and a.owed == 6_000, "owed = difference")
    print("test_pay_against_full_coverage OK")

def test_pay_against_exact_match():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")
    advance_ref = pay_advance(s, ledger, aid, "fin1")
    rid = make_report(s, "staff1", 1, 10_000)
    approve(s, rid, "sup1")
    calls_before = len(ledger.calls)
    result = pay_against(s, ledger, rid, aid, "fin1")
    check(result == "settled", "exact match -> settled")
    check(len(ledger.calls) == calls_before, "nothing paid")
    a = s.advance(aid)
    check(a.owed == 0, "owed 0 on exact match")
    print("test_pay_against_exact_match OK")

def test_pay_against_rules():
    s = build_store()
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 4_000)
    approve_advance(s, aid, "sup1")
    pay_advance(s, ledger, aid, "fin1")
    rid = make_report(s, "staff1", 1, 10_000)
    # report not approved yet
    try:
        pay_against(s, ledger, rid, aid, "fin1")
        raise AssertionError("should fail - report not approved")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "report not approved")
    approve(s, rid, "sup1")
    # settle once
    pay_against(s, ledger, rid, aid, "fin1")
    # settle again should fail
    try:
        pay_against(s, ledger, rid, aid, "fin1")
        raise AssertionError("should fail - already settled")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "already settled")
    print("test_pay_against_rules OK")

def test_pay_against_wrong_badge_or_period():
    s = build_store()
    s.staffs["staff2"] = s.staffs["staff1"].__class__("staff2", "Other", "eng", "sup1", s.staffs["staff1"].role, True)
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 4_000)
    approve_advance(s, aid, "sup1")
    pay_advance(s, ledger, aid, "fin1")
    rid = make_report(s, "staff2", 1, 10_000)
    approve(s, rid, "sup1")
    try:
        pay_against(s, ledger, rid, aid, "fin1")
        raise AssertionError("should fail - different badge")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "different badge conflict")
    print("test_pay_against_wrong_badge_or_period OK")

def test_budget_counts_advance():
    s = build_store()
    from dataclasses import replace
    s.departments["eng"] = replace(s.departments["eng"], budget=15_000)
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")  # approved; counts 10000 against budget
    rid = make_report(s, "staff1", 1, 6_000)
    try:
        approve(s, rid, "sup1")  # 10000 + 6000 = 16000 > 15000
        raise AssertionError("should fail - advance counts against budget")
    except Failure as f:
        check(f.code is FailureCode.CONFLICT, "advance counted in report's budget check")
    check(spend(s, "eng", 1) == 10_000, "spend includes approved advance")
    st = statement(s, "eng", 1)
    check(st.spend == 10_000 and st.remaining == 5_000, "statement totals include advance")
    check(len(st.rows) == 1 and st.rows[0].id == aid and st.rows[0].total == 10_000 and st.rows[0].budgeted == 10_000, "advance row in statement")
    print("test_budget_counts_advance OK")

def test_settled_advance_stops_counting():
    s = build_store()
    from dataclasses import replace
    s.departments["eng"] = replace(s.departments["eng"], budget=20_000)
    ledger = FakeLedger()
    aid = request_advance(s, "staff1", 1, 10_000)
    approve_advance(s, aid, "sup1")
    pay_advance(s, ledger, aid, "fin1")
    rid = make_report(s, "staff1", 1, 10_000)
    approve(s, rid, "sup1")
    check(spend(s, "eng", 1) == 20_000, "both advance(paid) and report(approved) count")
    pay_against(s, ledger, rid, aid, "fin1")
    check(spend(s, "eng", 1) == 10_000, "settled advance stops counting, report(paid) counts instead")
    print("test_settled_advance_stops_counting OK")

def test_outstanding_advances():
    s = build_store()
    ledger = FakeLedger()
    aid1 = request_advance(s, "staff1", 1, 1_000)
    approve_advance(s, aid1, "sup1")
    pay_advance(s, ledger, aid1, "fin1")  # period 1, paid, not settled

    aid2 = request_advance(s, "staff1", 5, 1_000)
    approve_advance(s, aid2, "sup1")
    pay_advance(s, ledger, aid2, "fin1")  # period 5

    check(outstanding_advances(s, 4) == [aid1], "period 1 + 2 < 4 -> outstanding; period 5 not yet")
    check(outstanding_advances(s, 3) == [], "period+2 < today is strict: 1+2=3, not < 3")
    check(outstanding_advances(s, 8) == [aid1, aid2], "both outstanding later, store order")
    print("test_outstanding_advances OK")

def test_amount_validation():
    s = build_store()
    try:
        request_advance(s, "staff1", 1, 0)
        raise AssertionError("should fail - amount 0")
    except Failure as f:
        check(f.code is FailureCode.INVALID_INPUT, "amount must be >=1")
    print("test_amount_validation OK")

def test_inactive_staff_cannot_request():
    s = build_store()
    from dataclasses import replace
    s.staffs["staff1"] = replace(s.staffs["staff1"], active=False)
    try:
        request_advance(s, "staff1", 1, 1_000)
        raise AssertionError("should fail - inactive")
    except Failure as f:
        check(f.code is FailureCode.UNAUTHORIZED, "inactive staff cannot request")
    print("test_inactive_staff_cannot_request OK")


if __name__ == "__main__":
    test_request_and_approve_small()
    test_approve_requires_right_person()
    test_requester_cannot_approve()
    test_multi_step_approval()
    test_closed_period_blocks_request_and_approve()
    test_budget_blocks_unless_finance()
    test_budget_override_by_finance_on_final_step()
    test_pay_advance()
    test_pay_advance_closed_period_allowed()
    test_pay_against_partial()
    test_pay_against_full_coverage()
    test_pay_against_exact_match()
    test_pay_against_rules()
    test_pay_against_wrong_badge_or_period()
    test_budget_counts_advance()
    test_settled_advance_stops_counting()
    test_outstanding_advances()
    test_amount_validation()
    test_inactive_staff_cannot_request()
    print("ALL OK")
