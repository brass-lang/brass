"""Trip plans: filed before travel, committing against the budget; approved like a report; reconciled against its expense report after."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Money, Period, ReportId
from .records import Region, TxnId, Vehicle

TripId = str


class TripStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    RECONCILED = "Reconciled"
    CLOSED = "Closed"


@dataclass(frozen=True)
class Plan:
    region: Region
    days: int
    vehicle: Vehicle
    km: int


@dataclass(frozen=True)
class Reconciliation:
    committed: Money
    actual: Money
    report: ReportId
    transactions: Sequence[TxnId]


@dataclass(frozen=True)
class Trip:
    id: TripId
    badge: Badge
    department: DepartmentId
    period: Period
    plan: Plan
    committed: Money
    status: TripStatus
    approvals: Sequence[Badge] = ()
    reconciliation: Optional[Reconciliation] = None


def add_approval(t: Trip, who: Badge) -> Trip:
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    return replace(t, approvals=(*t.approvals, who))


def approve(t: Trip) -> Trip:
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    return replace(t, status=TripStatus.APPROVED)


def amend(t: Trip, plan: Plan, committed: Money) -> Trip:
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be amended")
    return replace(t, plan=plan, committed=committed, approvals=(), status=TripStatus.REQUESTED)


def reconcile(t: Trip, r: Reconciliation) -> Trip:
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    return replace(t, status=TripStatus.RECONCILED, reconciliation=r)


def close(t: Trip) -> Trip:
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be closed")
    return replace(t, status=TripStatus.CLOSED)


def counts_as_spend(t: Trip) -> bool:
    return t.status is TripStatus.APPROVED
