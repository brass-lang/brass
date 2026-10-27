from typing import Sequence

from . import advances
from .advances import Advance
from .host import Store
from .ids import Badge, DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend
from .trips import Trip, TripStatus


def staff_budgeted_total(reports: Sequence[Report], badge: Badge) -> int:
    return sum(budgeted_total(r.lines) for r in reports if r.badge == badge and counts_as_spend(r))


def trip_counted(trip: Trip, reports: Sequence[Report], extra_for_badge: int = 0) -> int:
    """What `trip` counts against its budget: its committed amount, less the staff member's
    approved and paid reports for the period (plus `extra_for_badge`, a report not yet
    approved that will count once it is), never below zero. Zero when not Approved."""
    if trip.status is not TripStatus.APPROVED:
        return 0
    covered = staff_budgeted_total(reports, trip.badge) + extra_for_badge
    return max(0, trip.committed - covered)


def spend_of(reports: Sequence[Report], advs: Sequence[Advance], trips: Sequence[Trip] = ()) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a))
            + sum(trip_counted(t, reports) for t in trips))


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    return spend_of(store.reports_for(department, period), store.advances_for(department, period),
                    store.trips_for(department, period))


def department_spend_after_report(store: Store, department: DepartmentId, period: Period, badge: Badge, amount: int) -> int:
    """`department_spend` as it will read once a report of `amount` for `badge`/`period` is approved,
    so a trip of that staff member isn't charged for the same money twice."""
    reports = store.reports_for(department, period)
    advs = store.advances_for(department, period)
    trips = store.trips_for(department, period)
    base = (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a)))
    trip_total = sum(trip_counted(t, reports, amount if t.badge == badge else 0) for t in trips)
    return base + trip_total + amount
