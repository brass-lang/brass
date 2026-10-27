"""Trip plans: filed before travel, committing their cost against the department's budget once approved, reconciled against actual spend after."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Money, Period, ReportId, TripId
from .records import MILEAGE, PER_DIEM, Region, TxnId, Vehicle

MAX_DAYS = 30
MAX_KM = 2_000


class TripStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    RECONCILED = "Reconciled"
    CLOSED = "Closed"


TRANSITIONS = {
    TripStatus.REQUESTED: {TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.CLOSED},
    TripStatus.APPROVED: {TripStatus.REQUESTED, TripStatus.RECONCILED, TripStatus.CLOSED},
    TripStatus.RECONCILED: {TripStatus.RECONCILED},
    TripStatus.CLOSED: set(),
}


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
    approvals: Sequence[Badge] = ()
    status: TripStatus = TripStatus.REQUESTED
    reconciliation: Optional[Reconciliation] = None


def price(region: Region, days: int, vehicle: Vehicle, km: int) -> Money:
    return PER_DIEM[region] * days + MILEAGE[vehicle] * km


def plan_valid(days: int, km: int) -> bool:
    return 0 <= days <= MAX_DAYS and 0 <= km <= MAX_KM and (days > 0 or km > 0)


def _enter(t: Trip, status: TripStatus, **fields) -> Trip:
    if status not in TRANSITIONS[t.status]:
        raise Failure(FailureCode.CONFLICT, f"a {t.status.value} trip cannot become {status.value}")
    return replace(t, status=status, **fields)


def add_approval(t: Trip, who: Badge) -> Trip:
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting another approval")
    return replace(t, approvals=(*t.approvals, who))


def approve(t: Trip) -> Trip:
    return _enter(t, TripStatus.APPROVED)


def amend(t: Trip, plan: Plan, committed: Money) -> Trip:
    return _enter(t, TripStatus.REQUESTED, plan=plan, committed=committed, approvals=())


def reconcile(t: Trip, recon: Reconciliation) -> Trip:
    return _enter(t, TripStatus.RECONCILED, reconciliation=recon)


def close(t: Trip) -> Trip:
    return _enter(t, TripStatus.CLOSED)
