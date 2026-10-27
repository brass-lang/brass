"""Cash advances, start to finish: request, approval along the report chain, payment, settlement against a report."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from . import lines, reports, routing
from .audit import Entry
from .budget import spend_of
from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Period, ReportId, Role
from .reports import ReportStatus


class AdvanceStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    PAID = "Paid"
    SETTLED = "Settled"


@dataclass(frozen=True)
class Advance:
    id: ReportId
    badge: Badge
    department: DepartmentId
    period: Period
    amount: int
    status: AdvanceStatus
    approvals: Sequence[Badge] = ()
    reference: Optional[str] = None
    owed: Optional[int] = None


def advanced(advances) -> int:
    """What open advances hold against a budget: approved or paid, not yet settled."""
    return sum(a.amount for a in advances if a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID))


def request_advance(store, badge: Badge, period: Period, amount: int) -> ReportId:
    if amount < 1:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is at least 1 cent")
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    new_id = store.next_id()
    store.save_advance(Advance(new_id, badge, who.department, period, amount, AdvanceStatus.REQUESTED))
    return new_id


def approve_advance(store, advance_id: ReportId, approver: Badge) -> AdvanceStatus:
    who = store.staff(approver)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting approval")
    if store.period_closed(a.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == a.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "an advance cannot be approved by its requester")
    step = len(a.approvals) + 1
    role = routing.role_for(step)
    if role is Role.FINANCE:
        allowed = who.role is Role.FINANCE
    elif role is Role.SUPERVISOR:
        requester = store.staff(a.badge)
        if requester.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the requester has no supervisor")
        allowed = who.badge == _active_or_up(store, requester.supervisor)
    else:
        allowed = who.badge == _active_or_up(store, store.department(a.department).director)
    if not allowed:
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    if step < routing.steps_for(a.amount):
        store.save_advance(replace(a, approvals=(*a.approvals, who.badge)))
        store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED, "approved; awaiting the next approver"))
        return AdvanceStatus.REQUESTED
    dept = store.department(a.department)
    used = spend_of(store.reports_for(a.department, a.period)) + advanced(store.advances_for(a.department, a.period))
    over = used + a.amount > dept.budget
    if over and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(replace(a, status=AdvanceStatus.APPROVED))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED, "approved; budget override" if over else "approved"))
    return AdvanceStatus.APPROVED


def _active_or_up(store, badge: Badge) -> Badge:
    person = store.staff(badge)
    if person.active:
        return badge
    if person.supervisor is not None and store.staff(person.supervisor).active:
        return person.supervisor
    raise Failure(FailureCode.CONFLICT, "no active approver stands in")


def pay_advance(store, ledger, advance_id: ReportId, finance_badge: Badge) -> str:
    who = store.staff(finance_badge)
    if not (who.active and who.role is Role.FINANCE):
        raise Failure(FailureCode.UNAUTHORIZED, "only active finance staff may pay")
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(replace(a, status=AdvanceStatus.PAID, reference=reference))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
    return reference


def pay_against(store, ledger, report_id: ReportId, advance_id: ReportId, finance_badge: Badge) -> str:
    who = store.staff(finance_badge)
    if not (who.active and who.role is Role.FINANCE):
        raise Failure(FailureCode.UNAUTHORIZED, "only active finance staff may pay")
    r = store.report(report_id)
    a = store.advance(advance_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid, or is already settled")
    if (a.badge, a.period) != (r.badge, r.period):
        raise Failure(FailureCode.CONFLICT, "an advance settles only a report by the same staff member in the same period")
    total = lines.total(r.lines)
    if total > a.amount:
        reference = ledger.pay(r.badge, total - a.amount, r.id)
        owed, result = 0, reference
    else:
        reference, owed, result = a.reference, a.amount - total, "settled"
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid against an advance"))
    store.save_advance(replace(a, status=AdvanceStatus.SETTLED, owed=owed))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
    return result


def outstanding_advances(store, today: Period) -> list:
    return [a.id for a in store.paid_advances() if a.status is AdvanceStatus.PAID and a.period + 2 < today]
