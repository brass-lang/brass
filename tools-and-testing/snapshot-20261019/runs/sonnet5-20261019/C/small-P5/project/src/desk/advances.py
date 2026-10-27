from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import AdvanceId, Badge, DepartmentId, Money, Period

MAX_APPROVALS = 2      # a third approval completes the chain, so a Requested advance never holds three


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
    id: AdvanceId
    badge: Badge
    department: DepartmentId
    period: Period
    amount: Money
    status: AdvanceStatus
    approvals: Sequence[Badge] = ()
    reference: Optional[str] = None      # set only once Paid
    owed: Money = 0                      # set only once Settled; 0 when the report covered it


def _enter(a: Advance, status: AdvanceStatus, **fields) -> Advance:
    if status not in TRANSITIONS[a.status]:
        raise Failure(FailureCode.CONFLICT, f"a {a.status.value} advance cannot become {status.value}")
    return replace(a, status=status, **fields)


def add_approval(a: Advance, who: Badge) -> Advance:
    if a.status is not AdvanceStatus.REQUESTED or len(a.approvals) >= MAX_APPROVALS:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting another approval")
    return replace(a, approvals=(*a.approvals, who))


def approve(a: Advance) -> Advance:
    return _enter(a, AdvanceStatus.APPROVED)


def pay(a: Advance, reference: str) -> Advance:
    return _enter(a, AdvanceStatus.PAID, reference=reference)


def settle(a: Advance, owed: Money) -> Advance:
    return _enter(a, AdvanceStatus.SETTLED, owed=owed)


def counts_as_spend(a: Advance) -> bool:
    return a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID)
