from typing import Sequence

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


def _reported_total(store: Store, badge: Badge, department: DepartmentId, period: Period) -> int:
    return sum(budgeted_total(r.lines) for r in store.reports_for(department, period)
               if r.badge == badge and counts_as_spend(r))


def trip_remaining_if_approved(store: Store, t: Trip) -> int:
    """What `t` would count toward the budget once (or as long as) it is approved."""
    reported = _reported_total(store, t.badge, t.department, t.period)
    return max(0, t.committed - reported)


def trip_counts(store: Store, t: Trip) -> int:
    return trip_remaining_if_approved(store, t) if t.status is TripStatus.APPROVED else 0


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    trips = store.trips_for(department, period)
    return (spend_of(store.reports_for(department, period), store.advances_for(department, period))
            + sum(trip_counts(store, t) for t in trips))


def spend_with_pending_report(store: Store, r: Report) -> int:
    """Department spend as it will be once `r` (not yet saved as approved) is approved.

    A trip of the same staff member and period counts by what it would count once `r`
    is approved, so `r`'s amount is not charged against the budget twice.
    """
    base = spend_of(store.reports_for(r.department, r.period), store.advances_for(r.department, r.period))
    extra = budgeted_total(r.lines)
    trip_total = 0
    for t in store.trips_for(r.department, r.period):
        if t.status is not TripStatus.APPROVED:
            continue
        reported = _reported_total(store, t.badge, t.department, t.period)
        if t.badge == r.badge:
            reported += extra
        trip_total += max(0, t.committed - reported)
    return base + extra + trip_total
