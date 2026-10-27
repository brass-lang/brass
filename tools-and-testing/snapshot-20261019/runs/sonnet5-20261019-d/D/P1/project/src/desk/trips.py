"""Trip plans: filed before travel, approved like a report, amended, reconciled against an expense report, or closed."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Money, Period, ReportId, TripId
from .records import MILEAGE, PER_DIEM, Region, TxnId, Vehicle

MAX_APPROVALS = 2      # as a report's: a third approval completes the chain
MAX_DAYS = 30
MAX_KM = 2_000


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
    transactions: Sequence[TxnId] = ()


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


def priced(region: Region, days: int, vehicle: Vehicle, km: int) -> Money:
    if not (0 <= days <= MAX_DAYS and 0 <= km <= MAX_KM and (days > 0 or km > 0)):
        raise Failure(FailureCode.INVALID_INPUT,
                     "a trip plan covers 0 to 30 per diem days and 0 to 2,000 km, with at least one of them positive")
    return PER_DIEM[region] * days + MILEAGE[vehicle] * km


def add_approval(t: Trip, who: Badge) -> Trip:
    if t.status is not TripStatus.REQUESTED or len(t.approvals) >= MAX_APPROVALS:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting another approval")
    return replace(t, approvals=(*t.approvals, who))


def approve(t: Trip) -> Trip:
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    return replace(t, status=TripStatus.APPROVED)


def amend(t: Trip, plan: Plan, committed: Money) -> Trip:
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be amended")
    return replace(t, plan=plan, committed=committed, approvals=(), status=TripStatus.REQUESTED)


def close(t: Trip) -> Trip:
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not open")
    return replace(t, status=TripStatus.CLOSED)


def reconcile(t: Trip, reconciliation: Reconciliation) -> Trip:
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    return replace(t, status=TripStatus.RECONCILED, reconciliation=reconciliation)
