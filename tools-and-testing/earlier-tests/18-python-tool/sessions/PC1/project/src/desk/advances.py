"""Cash advances: requested before a trip, approved like a report, paid by finance, and settled against the expense report that follows."""
from . import budget, lines, records, reports, routing
from .audit import Entry
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Ledger, Store
from .ids import MONEY_MAX, Badge, Money, Period, ReportId, Role
from .records import Advance, AdvanceId, AdvanceStatus
from .reports import ReportStatus
from .review import may_act
from .staff import Staff


def request_advance(store: Store, badge: Badge, period: Period, amount: Money) -> AdvanceId:
    who = active_staff(store, badge)
    if not 1 <= amount <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is for at least one cent")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    id = store.next_id()
    store.save_advance(Advance(id, who.badge, who.department, period, amount, AdvanceStatus.REQUESTED))
    return id


def approve_advance(store: Store, advance_id: AdvanceId, approver: Badge) -> AdvanceStatus:
    a, who = _gate(store, advance_id, approver)
    if len(a.approvals) + 1 >= routing.steps_for(a.amount):
        return _final_approval(store, a, who)
    store.save_advance(records.add_advance_approval(a, who.badge))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED, "approved; awaiting the next approver"))
    return AdvanceStatus.REQUESTED


def pay_advance(store: Store, ledger: Ledger, advance_id: AdvanceId, finance_badge: Badge) -> str:
    who = finance_staff(store, finance_badge)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(records.move_advance(a, AdvanceStatus.PAID, reference=reference))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
    return reference


def pay_against(store: Store, ledger: Ledger, report_id: ReportId, advance_id: AdvanceId, finance_badge: Badge) -> str:
    who = finance_staff(store, finance_badge)
    r = store.report(report_id)
    a = store.advance(advance_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid")
    if a.badge != r.badge or a.period != r.period:
        raise Failure(FailureCode.CONFLICT, "the advance is not the report's")
    report_total = lines.total(r.lines)
    if a.amount >= report_total:
        reference = a.reference
        owed = a.amount - report_total
        result = "settled"
    else:
        reference = ledger.pay(r.badge, report_total - a.amount, r.id)
        owed = 0
        result = reference
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
    store.save_advance(records.move_advance(a, AdvanceStatus.SETTLED, owed=owed))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
    return result


def outstanding_advances(store: Store, today: Period) -> list[AdvanceId]:
    return [a.id for a in store.paid_advances() if a.period + 2 < today]


def _gate(store: Store, advance_id: AdvanceId, approver: Badge) -> tuple[Advance, Staff]:
    who = active_staff(store, approver)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting approval")
    if store.period_closed(a.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == a.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "an advance cannot be approved by its requester")
    if not may_act(store, a, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    return a, who


def _final_approval(store: Store, a: Advance, who: Staff) -> AdvanceStatus:
    dept = store.department(a.department)
    spend = budget.spend_of(store.reports_for(a.department, a.period)) + budget.advance_spend_of(store.advances_for(a.department, a.period))
    within = spend + a.amount <= dept.budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(records.move_advance(a, AdvanceStatus.APPROVED))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return AdvanceStatus.APPROVED
