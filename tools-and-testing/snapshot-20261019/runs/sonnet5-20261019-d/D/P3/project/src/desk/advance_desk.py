"""Requesting and approving cash advances. Approval follows the routing and budget rules of a report of that amount."""
from . import advances, routing
from .advances import Advance, AdvanceStatus
from .audit import Entry, Subject
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Money, Period, ReportId, Role
from .review import may_act, within_budget


def request_advance(store: Store, badge: Badge, period: Period, amount: Money) -> ReportId:
    if amount < 1:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is at least 1 cent")
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    id = store.next_id()
    store.save_advance(Advance(id, badge, who.department, period, amount, AdvanceStatus.REQUESTED))
    return id


def approve_advance(store: Store, advance_id: ReportId, approver: Badge) -> AdvanceStatus:
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
    if not may_act(store, a, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    if len(a.approvals) + 1 < routing.steps_for(a.amount):
        store.save_advance(advances.add_approval(a, who.badge))
        store.append_audit(Entry(who.badge, Subject.ADVANCE, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED, "approved; awaiting the next approver"))
        return AdvanceStatus.REQUESTED
    within = within_budget(store, a.department, a.period, a.amount)
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(advances.approve(a))
    store.append_audit(Entry(who.badge, Subject.ADVANCE, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return AdvanceStatus.APPROVED
