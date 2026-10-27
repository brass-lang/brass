from typing import Optional, Sequence

from . import advances
from .advances import Advance
from .host import Store
from .ids import Badge, DepartmentId, Money, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend
from .trips import Trip, TripStatus


def spend_of(reports: Sequence[Report], advs: Sequence[Advance]) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a)))


def _covered(reports: Sequence[Report], badge: Badge) -> int:
    return sum(budgeted_total(r.lines) for r in reports if r.badge == badge and counts_as_spend(r))


def trip_remaining(t: Trip, reports: Sequence[Report], pending: Optional[tuple[Badge, Money]] = None) -> int:
    """What `t` still counts against the budget: its committed amount less the staff member's covering reports, never below zero.

    `pending` adds a not-yet-saved report's budgeted amount for its badge, so a report's own final
    approval step counts a trip it stands beside without charging that report's amount twice.
    """
    covered = _covered(reports, t.badge)
    if pending is not None and pending[0] == t.badge:
        covered += pending[1]
    return max(0, t.committed - covered)


def trips_spend(trips: Sequence[Trip], reports: Sequence[Report], pending: Optional[tuple[Badge, Money]] = None) -> int:
    return sum(trip_remaining(t, reports, pending) for t in trips if t.status is TripStatus.APPROVED)


def department_spend(store: Store, department: DepartmentId, period: Period,
                     pending: Optional[tuple[Badge, Money]] = None) -> int:
    reports = store.reports_for(department, period)
    advs = store.advances_for(department, period)
    return spend_of(reports, advs) + trips_spend(store.trips_for(department, period), reports, pending)
