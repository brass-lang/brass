from typing import Sequence

from . import advances, trips
from .advances import Advance
from .host import Store
from .ids import DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend
from .trips import Trip


def spend_of(reports: Sequence[Report], advs: Sequence[Advance], trps: Sequence[Trip] = ()) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a))
            + sum(trips.counted(t, reports) for t in trps))


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    return spend_of(store.reports_for(department, period), store.advances_for(department, period), store.trips_for(department, period))


def spend_with(store: Store, department: DepartmentId, period: Period, report: Report) -> int:
    """Department spend as it would be once `report` is approved: a trip beside it counts what remains of its commitment."""
    others = [r for r in store.reports_for(department, period) if r.id != report.id]
    return spend_of([*others, report], store.advances_for(department, period), store.trips_for(department, period))
