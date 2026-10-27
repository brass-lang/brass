"""Trip plans: filed before a trip, approved like a report of their committed amount, then reconciled or closed."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, DepartmentId, Money, Period, ReportId
from .lines import budgeted_total
from .records import MILEAGE, PER_DIEM, Region, TxnId, Vehicle
from .reports import Report, counts_as_spend

MAX_DAYS = 30
MAX_KM = 2_000


class TripStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    RECONCILED = "Reconciled"
    CLOSED = "Closed"


TRANSITIONS = {
    TripStatus.REQUESTED: {TripStatus.APPROVED, TripStatus.CLOSED},
    TripStatus.APPROVED: {TripStatus.REQUESTED, TripStatus.RECONCILED, TripStatus.CLOSED},
    TripStatus.RECONCILED: set(),
    TripStatus.CLOSED: set(),
}
OPEN = (TripStatus.REQUESTED, TripStatus.APPROVED)


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
    txns: tuple[TxnId, ...]


@dataclass(frozen=True)
class Trip:
    id: ReportId
    badge: Badge
    department: DepartmentId
    period: Period
    plan: Plan
    committed: Money
    status: TripStatus
    approvals: Sequence[Badge] = ()
    reconciliation: Optional[Reconciliation] = None      # set once Reconciled


def priced(plan: Plan) -> Money:
    """The committed amount: per diem plus mileage. Raises InvalidInput outside the plan's ranges."""
    if not (0 <= plan.days <= MAX_DAYS and 0 <= plan.km <= MAX_KM):
        raise Failure(FailureCode.INVALID_INPUT, "per diem covers 0 to 30 days and mileage 0 to 2,000 km")
    if plan.days == 0 and plan.km == 0:
        raise Failure(FailureCode.INVALID_INPUT, "a trip has per diem days, kilometres, or both")
    return (PER_DIEM[plan.region] * plan.days if plan.days else 0) + (MILEAGE[plan.vehicle] * plan.km if plan.km else 0)


def _enter(t: Trip, status: TripStatus, **fields) -> Trip:
    if status not in TRANSITIONS[t.status]:
        raise Failure(FailureCode.CONFLICT, f"a {t.status.value} trip cannot become {status.value}")
    return replace(t, status=status, **fields)


def add_approval(t: Trip, who: Badge) -> Trip:
    return replace(t, approvals=(*t.approvals, who))


def approve(t: Trip) -> Trip:
    return _enter(t, TripStatus.APPROVED)


def amend(t: Trip, plan: Plan, committed: Money) -> Trip:
    """Reprice and clear approvals; an Approved trip returns to Requested in the same record."""
    if t.status is TripStatus.APPROVED:
        return _enter(t, TripStatus.REQUESTED, plan=plan, committed=committed, approvals=())
    return replace(t, plan=plan, committed=committed, approvals=())


def reconcile(t: Trip, r: Reconciliation) -> Trip:
    if t.status is TripStatus.RECONCILED:
        return replace(t, reconciliation=r)                   # a repeat replaces, no transition
    return _enter(t, TripStatus.RECONCILED, reconciliation=r)


def close(t: Trip) -> Trip:
    return _enter(t, TripStatus.CLOSED)


def counted(t: Trip, reports: Sequence[Report]) -> Money:
    """What an Approved trip counts against the budget: its commitment less its staff member's counted reports."""
    if t.status is not TripStatus.APPROVED:
        return 0
    covered = sum(budgeted_total(r.lines) for r in reports if r.badge == t.badge and r.period == t.period and counts_as_spend(r))
    return max(0, t.committed - covered)
