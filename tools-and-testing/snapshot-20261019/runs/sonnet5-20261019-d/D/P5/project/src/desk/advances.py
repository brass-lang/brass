"""Cash advances: requested before a trip, approved like a report, paid, then settled against the trip's report."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Money, Period, ReportId

OUTSTANDING_AFTER = 2      # periods after its own that a paid advance may stay unsettled


class AdvanceStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    PAID = "Paid"
    SETTLED = "Settled"


TRANSITIONS = {
    AdvanceStatus.REQUESTED: {AdvanceStatus.APPROVED},
    AdvanceStatus.APPROVED: {AdvanceStatus.PAID},
    AdvanceStatus.PAID: {AdvanceStatus.SETTLED},
    AdvanceStatus.SETTLED: set(),
}


@dataclass(frozen=True)
class Advance:
    id: ReportId
    badge: Badge
    department: DepartmentId
    period: Period
    amount: Money
    status: AdvanceStatus
    approvals: Sequence[Badge] = ()
    reference: Optional[str] = None      # set once Paid
    owed: Optional[int] = None           # set once Settled: what the staff member owes back


def _enter(a: Advance, status: AdvanceStatus, **fields) -> Advance:
    if status not in TRANSITIONS[a.status]:
        raise Failure(FailureCode.CONFLICT, f"a {a.status.value} advance cannot become {status.value}")
    return replace(a, status=status, **fields)


def add_approval(a: Advance, who: Badge) -> Advance:
    if a.status is not AdvanceStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting approval")
    return replace(a, approvals=(*a.approvals, who))


def approve(a: Advance) -> Advance:
    return _enter(a, AdvanceStatus.APPROVED)


def pay(a: Advance, reference: str) -> Advance:
    return _enter(a, AdvanceStatus.PAID, reference=reference)


def settle(a: Advance, owed: int) -> Advance:
    return _enter(a, AdvanceStatus.SETTLED, owed=owed)


def counts_as_spend(a: Advance) -> bool:
    return a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID)


def outstanding(a: Advance, today: Period) -> bool:
    return a.status is AdvanceStatus.PAID and a.period + OUTSTANDING_AFTER < today
