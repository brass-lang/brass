from typing import Optional, Sequence

from . import advances
from .advances import Advance
from .host import Store
from .ids import Badge, DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend
from .trips import Trip, TripStatus


def spend_of(reports: Sequence[Report], advs: Sequence[Advance]) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a)))


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    return spend_of(store.reports_for(department, period), store.advances_for(department, period))


def covered_by_reports(store: Store, trip: Trip) -> int:
    """The staff member's approved and paid reports' budgeted total for the trip's period."""
    return sum(budgeted_total(r.lines) for r in store.reports_for(trip.department, trip.period)
              if r.badge == trip.badge and counts_as_spend(r))


def trip_commitment(store: Store, trip: Trip, pending: int = 0) -> int:
    """What `trip` would count toward its department's budget, once `pending` more of its badge's spend is covered."""
    return max(0, trip.committed - covered_by_reports(store, trip) - pending)


def department_commitment(store: Store, department: DepartmentId, period: Period,
                          pending_badge: Optional[Badge] = None, pending_amount: int = 0) -> int:
    """Department spend for the period, including each Approved trip's remaining commitment.

    `pending_badge`/`pending_amount` let a report or advance about to be approved count toward
    the same badge's trip commitment, so that amount is not charged twice.
    """
    total = department_spend(store, department, period)
    for t in store.trips_for(department, period):
        if t.status is not TripStatus.APPROVED:
            continue
        pending = pending_amount if pending_badge is not None and t.badge == pending_badge else 0
        total += trip_commitment(store, t, pending)
    return total
