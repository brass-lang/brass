"""Cash advances: requested before a trip, approved like a report of that amount, paid by finance, and settled against the report filed afterwards."""
from . import lines, records, reports, routing
from .audit import Entry
from .budget import department_spend
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Ledger, Store
from .ids import MONEY_MAX, Badge, Money, Period, ReportId, Role
from .records import Advance, AdvanceId, AdvanceStatus
from .reports import ReportStatus
from .review import required_approver
from .staff import Staff

SETTLED = "settled"        # what pay_against returns when the advance covered the whole report
OUTSTANDING_AFTER = 2      # periods after its own that a paid advance may stay unsettled


def request_advance(store: Store, badge: Badge, period: Period, amount: Money) -> AdvanceId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not 1 <= amount <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is for at least one cent")
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
    """Pay an approved report less a paid advance, and settle the advance. Returns the ledger reference, or "settled" when nothing was paid."""
    who = finance_staff(store, finance_badge)
    r = store.report(report_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid, or is already settled")
    if a.badge != r.badge or a.period != r.period:
        raise Failure(FailureCode.CONFLICT, "the advance is not the submitter's for the report's period")
    total = lines.total(r.lines)
    if a.amount >= total:
        reference, owed, result = a.reference, a.amount - total, SETTLED
    else:
        reference = ledger.pay(r.badge, total - a.amount, r.id)
        owed, result = 0, reference
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
    store.save_advance(records.move_advance(a, AdvanceStatus.SETTLED, owed=owed))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
    return result


def outstanding_advances(store: Store, today: Period) -> list[AdvanceId]:
    return [a.id for a in store.paid_advances() if a.status is AdvanceStatus.PAID and a.period + OUTSTANDING_AFTER < today]


def may_approve(store: Store, a: Advance, who: Staff) -> bool:
    """Is `who` the advance's next approver, as for a report of its amount from its requester? Raises Conflict when no one can be."""
    required = required_approver(store, a.badge, a.department, len(a.approvals) + 1)
    if required is None:
        return who.role is Role.FINANCE
    return who.badge == required


def _gate(store: Store, advance_id: AdvanceId, approver: Badge) -> tuple[Advance, Staff]:
    who = active_staff(store, approver)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting approval")
    if store.period_closed(a.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == a.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "an advance cannot be approved by its requester")
    if not may_approve(store, a, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    return a, who


def _final_approval(store: Store, a: Advance, who: Staff) -> AdvanceStatus:
    dept = store.department(a.department)
    within = department_spend(store, a.department, a.period) + a.amount <= dept.budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(records.move_advance(a, AdvanceStatus.APPROVED))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return AdvanceStatus.APPROVED
