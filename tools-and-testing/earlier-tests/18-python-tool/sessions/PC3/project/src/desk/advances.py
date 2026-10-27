"""Cash advances: requested ahead of a trip, approved and paid like a report, then settled against the report they funded."""
from typing import Optional

from . import lines, records, reports, routing
from .audit import Entry
from .budget import department_spend
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Ledger, Store
from .ids import MONEY_MAX, Badge, Money, Period, ReportId, Role
from .records import Advance, AdvanceId, AdvanceStatus
from .reports import ReportStatus
from .staff import Staff


def request_advance(store: Store, badge: Badge, period: Period, amount: Money) -> AdvanceId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not 1 <= amount <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is for at least one cent")
    id = store.next_id()
    store.save_advance(Advance(id, badge, who.department, period, amount, AdvanceStatus.REQUESTED))
    return id


def approve_advance(store: Store, advance_id: AdvanceId, approver: Badge) -> AdvanceStatus:
    a, who = _gate(store, advance_id, approver)
    if len(a.approvals) + 1 >= routing.steps_for(a.amount):
        return _final_approval(store, a, who)
    store.save_advance(records.add_advance_approval(a, who.badge))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED,
                             "approved; awaiting the next approver"))
    return AdvanceStatus.REQUESTED


def pay_advance(store: Store, ledger: Ledger, advance_id: AdvanceId, finance_badge: Badge) -> str:
    who = finance_staff(store, finance_badge)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(records.pay_advance(a, reference))
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
        raise Failure(FailureCode.CONFLICT, "the advance is not for this report")
    report_total = lines.total(r.lines)
    if a.amount >= report_total:
        store.save_report(reports.pay(r, a.reference))
        store.save_advance(records.settle_advance(a, a.amount - report_total))
        store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
        store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
        return "settled"
    reference = ledger.pay(r.badge, report_total - a.amount, r.id)
    store.save_report(reports.pay(r, reference))
    store.save_advance(records.settle_advance(a, 0))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
    return reference


def outstanding_advances(store: Store, today: Period) -> list[AdvanceId]:
    return [a.id for a in store.paid_advances() if records.advance_outstanding(a, today)]


def _gate(store: Store, advance_id: AdvanceId, approver: Badge) -> tuple[Advance, Staff]:
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
    if not _may_act(store, a, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    return a, who


def _may_act(store: Store, a: Advance, who: Staff) -> bool:
    required = _required_for(store, a)
    if required is None:
        return who.role is Role.FINANCE
    return who.badge == required


def _required_for(store: Store, a: Advance) -> Optional[Badge]:
    role = routing.role_for(len(a.approvals) + 1)
    if role is Role.FINANCE:
        return None
    if role is Role.SUPERVISOR:
        requester = store.staff(a.badge)
        if requester.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the requester has no supervisor")
        return _stand_in(store, requester.supervisor)
    return _stand_in(store, store.department(a.department).director)


def _stand_in(store: Store, required: Badge) -> Badge:
    person = store.staff(required)
    if person.active:
        return required
    if person.supervisor is not None and store.staff(person.supervisor).active:
        return person.supervisor
    raise Failure(FailureCode.CONFLICT, f"no active approver stands in for {required}")


def _final_approval(store: Store, a: Advance, who: Staff) -> AdvanceStatus:
    dept = store.department(a.department)
    within = department_spend(store, a.department, a.period) + a.amount <= dept.budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(records.approve_advance(a))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return AdvanceStatus.APPROVED
