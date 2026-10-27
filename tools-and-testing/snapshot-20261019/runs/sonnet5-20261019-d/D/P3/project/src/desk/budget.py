from typing import Optional, Sequence

from . import advances
from .advances import Advance
from .host import Store
from .ids import DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend
from .trips import Trip, TripStatus


def spend_of(reports: Sequence[Report], advs: Sequence[Advance]) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a)))


def trip_coverage(trip: Trip, reports: Sequence[Report]) -> int:
    """How much of the trip's commitment the staff member's own approved and paid reports already cover."""
    return sum(budgeted_total(r.lines) for r in reports if r.badge == trip.badge and counts_as_spend(r))


def trip_remaining(trip: Trip, reports: Sequence[Report], *, pretend: Optional[Report] = None) -> int:
    """What the trip counts against its department's budget: 0 unless Approved, and never below 0."""
    if trip.status is not TripStatus.APPROVED:
        return 0
    covered = trip_coverage(trip, reports)
    if pretend is not None and pretend.badge == trip.badge:
        covered += budgeted_total(pretend.lines)
    return max(0, trip.committed - covered)


def trips_spend(trips: Sequence[Trip], reports: Sequence[Report], *, pretend: Optional[Report] = None) -> int:
    return sum(trip_remaining(t, reports, pretend=pretend) for t in trips)


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    reports = store.reports_for(department, period)
    advs = store.advances_for(department, period)
    trips = store.trips_for(department, period)
    return spend_of(reports, advs) + trips_spend(trips, reports)
