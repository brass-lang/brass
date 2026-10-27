"""Drafting, submitting, and reviewing expense reports; requesting and approving cash advances."""
from typing import Optional, Sequence

from . import advances, lines, reports, routing
from .advances import Advance, AdvanceId, AdvanceStatus
from .audit import Entry
from .budget import advance_spend_of, spend_of
from .errors import Failure, FailureCode
from .host import Store
from .ids import MONEY_MAX, Badge, DepartmentId, Money, Period, ReportId, Role
from .lines import Line
from .reports import Report, ReportStatus
from .staff import Staff


def open_draft(store: Store, badge: Badge, period: Period, first_line: Line) -> ReportId:
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    id = store.next_id()
    store.save_report(Report(id, badge, who.department, period, (first_line,), ReportStatus.DRAFT))
    return id


def add_line(store: Store, report_id: ReportId, badge: Badge, line: Line) -> None:
    r = _own(store, report_id, badge)
    if not reports.editable(r):
        raise Failure(FailureCode.CONFLICT, "the report is not editable")
    if len(r.lines) >= reports.MAX_LINES:
        raise Failure(FailureCode.INVALID_INPUT, "a report holds at most 50 lines")
    store.save_report(reports.add_line(r, line))


def submit(store: Store, report_id: ReportId, badge: Badge) -> None:
    r = _own(store, report_id, badge)
    if r.status is not ReportStatus.DRAFT:
        raise Failure(FailureCode.CONFLICT, "the report is not a draft")
    _open_and_valid(store, r)
    store.save_report(reports.submit(r))
    store.append_audit(Entry(badge, r.id, ReportStatus.DRAFT, ReportStatus.SUBMITTED, "submitted"))


def resubmit(store: Store, report_id: ReportId, badge: Badge) -> None:
    r = _own(store, report_id, badge)
    if r.status is not ReportStatus.CHANGES_REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the report is not awaiting changes")
    _open_and_valid(store, r)
    store.save_report(reports.resubmit(r))
    store.append_audit(Entry(badge, r.id, ReportStatus.CHANGES_REQUESTED, ReportStatus.SUBMITTED, "resubmitted"))


def approve(store: Store, report_id: ReportId, approver: Badge) -> ReportStatus:
    r, who = _gate(store, report_id, approver)
    if len(r.approvals) + 1 >= routing.steps_for(lines.total(r.lines)):
        return _final_approval(store, r, who)
    store.save_report(reports.add_approval(r, who.badge))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.SUBMITTED, ReportStatus.SUBMITTED, "approved; awaiting the next approver"))
    return ReportStatus.SUBMITTED


def reject(store: Store, report_id: ReportId, approver: Badge, reason: str) -> None:
    r, who = _gate(store, report_id, approver)
    store.save_report(reports.reject(r))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.SUBMITTED, ReportStatus.REJECTED, reason))


def request_changes(store: Store, report_id: ReportId, approver: Badge, reason: str) -> None:
    r, who = _gate(store, report_id, approver)
    store.save_report(reports.request_changes(r))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.SUBMITTED, ReportStatus.CHANGES_REQUESTED, reason))


def may_act(store: Store, r: Report, who: Staff) -> bool:
    """Is `who` the required approver for the report's next step? Raises Conflict when no one can be."""
    required = _required_for(store, r)
    if required is None:
        return who.role is Role.FINANCE
    return who.badge == required


def _own(store: Store, report_id: ReportId, badge: Badge) -> Report:
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    r = store.report(report_id)
    if r.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the submitter may act on this report")
    return r


def _open_and_valid(store: Store, r: Report) -> None:
    if store.period_closed(r.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not lines.all_valid(r.lines):
        raise Failure(FailureCode.INVALID_INPUT, "a line is over its limit or lacks a required receipt")


def _gate(store: Store, report_id: ReportId, approver: Badge) -> tuple[Report, Staff]:
    who = store.staff(approver)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    r = store.report(report_id)
    if r.status is not ReportStatus.SUBMITTED:
        raise Failure(FailureCode.CONFLICT, "the report is not awaiting approval")
    if store.period_closed(r.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == r.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a report cannot be approved by its submitter")
    if not may_act(store, r, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this report's next approver")
    return r, who


def _required_for(store: Store, r: Report) -> Optional[Badge]:
    """The badge required for the next step, or None when any active finance staff member will do."""
    return _required_for_step(store, r.approvals, r.badge, r.department)


def _required_for_step(store: Store, approvals: Sequence[Badge], submitter_badge: Badge, department: DepartmentId) -> Optional[Badge]:
    role = routing.role_for(len(approvals) + 1)
    if role is Role.FINANCE:
        return None
    if role is Role.SUPERVISOR:
        submitter = store.staff(submitter_badge)
        if submitter.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the submitter has no supervisor")
        return _stand_in(store, submitter.supervisor)
    return _stand_in(store, store.department(department).director)


def _stand_in(store: Store, required: Badge) -> Badge:
    person = store.staff(required)
    if person.active:
        return required
    if person.supervisor is not None and store.staff(person.supervisor).active:
        return person.supervisor
    raise Failure(FailureCode.CONFLICT, f"no active approver stands in for {required}")


def _final_approval(store: Store, r: Report, who: Staff) -> ReportStatus:
    dept = store.department(r.department)
    committed = spend_of(store.reports_for(r.department, r.period)) + advance_spend_of(store.advances_for(r.department, r.period))
    within = committed + lines.budgeted_total(r.lines) <= dept.budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_report(reports.approve(r))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.SUBMITTED, ReportStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return ReportStatus.APPROVED


def request_advance(store: Store, badge: Badge, period: Period, amount: Money) -> AdvanceId:
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not 1 <= amount <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "an advance is for at least one cent")
    id = store.next_id()
    store.save_advance(Advance(id, who.badge, who.department, period, amount, AdvanceStatus.REQUESTED))
    return id


def approve_advance(store: Store, advance_id: AdvanceId, approver: Badge) -> AdvanceStatus:
    a, who = _gate_advance(store, advance_id, approver)
    if len(a.approvals) + 1 >= routing.steps_for(a.amount):
        return _final_advance_approval(store, a, who)
    store.save_advance(advances.add_approval(a, who.badge))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.REQUESTED, "approved; awaiting the next approver"))
    return AdvanceStatus.REQUESTED


def _gate_advance(store: Store, advance_id: AdvanceId, approver: Badge) -> tuple[Advance, Staff]:
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
    required = _required_for_step(store, a.approvals, a.badge, a.department)
    if required is None:
        if who.role is not Role.FINANCE:
            raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    elif who.badge != required:
        raise Failure(FailureCode.UNAUTHORIZED, "not this advance's next approver")
    return a, who


def _final_advance_approval(store: Store, a: Advance, who: Staff) -> AdvanceStatus:
    dept = store.department(a.department)
    committed = spend_of(store.reports_for(a.department, a.period)) + advance_spend_of(store.advances_for(a.department, a.period))
    within = committed + a.amount <= dept.budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_advance(advances.approve(a))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.REQUESTED, AdvanceStatus.APPROVED,
                             "approved" if within else "approved; budget override"))
    return AdvanceStatus.APPROVED
