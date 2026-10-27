from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Period, ReportId
from .lines import Line

MAX_LINES = 50
MAX_APPROVALS = 2      # a third approval completes the chain, so a Submitted report never holds three


class ReportStatus(Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CHANGES_REQUESTED = "ChangesRequested"
    PAID = "Paid"


TRANSITIONS = {
    ReportStatus.DRAFT: {ReportStatus.SUBMITTED},
    ReportStatus.SUBMITTED: {ReportStatus.APPROVED, ReportStatus.REJECTED, ReportStatus.CHANGES_REQUESTED},
    ReportStatus.CHANGES_REQUESTED: {ReportStatus.SUBMITTED},
    ReportStatus.APPROVED: {ReportStatus.PAID},
    ReportStatus.REJECTED: set(),
    ReportStatus.PAID: set(),
}


@dataclass(frozen=True)
class Report:
    id: ReportId
    badge: Badge
    department: DepartmentId
    period: Period
    lines: Sequence[Line]
    status: ReportStatus
    approvals: Sequence[Badge] = ()
    reference: Optional[str] = None      # set only once Paid


def _enter(r: Report, status: ReportStatus, **fields) -> Report:
    if status not in TRANSITIONS[r.status]:
        raise Failure(FailureCode.CONFLICT, f"a {r.status.value} report cannot become {status.value}")
    return replace(r, status=status, **fields)


def editable(r: Report) -> bool:
    return r.status in (ReportStatus.DRAFT, ReportStatus.CHANGES_REQUESTED)


def add_line(r: Report, line: Line) -> Report:
    if not editable(r) or len(r.lines) >= MAX_LINES:
        raise Failure(FailureCode.CONFLICT, "the report cannot take another line")
    return replace(r, lines=(*r.lines, line))


def submit(r: Report) -> Report:
    return _enter(r, ReportStatus.SUBMITTED, approvals=())


def add_approval(r: Report, who: Badge) -> Report:
    if r.status is not ReportStatus.SUBMITTED or len(r.approvals) >= MAX_APPROVALS:
        raise Failure(FailureCode.CONFLICT, "the report is not awaiting another approval")
    return replace(r, approvals=(*r.approvals, who))


def approve(r: Report) -> Report:
    return _enter(r, ReportStatus.APPROVED)


def reject(r: Report) -> Report:
    return _enter(r, ReportStatus.REJECTED)


def request_changes(r: Report) -> Report:
    return _enter(r, ReportStatus.CHANGES_REQUESTED, approvals=())


def resubmit(r: Report) -> Report:
    return _enter(r, ReportStatus.SUBMITTED, approvals=())


def pay(r: Report, reference: str) -> Report:
    return _enter(r, ReportStatus.PAID, reference=reference)


def counts_as_spend(r: Report) -> bool:
    return r.status in (ReportStatus.APPROVED, ReportStatus.PAID)
