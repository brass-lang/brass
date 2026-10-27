from typing import Sequence

from .advances import Advance
from .advances import counts_as_spend as advance_counts_as_spend
from .host import Store
from .ids import DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report]) -> int:
    return sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))


def advance_spend_of(advances: Sequence[Advance]) -> int:
    return sum(a.amount for a in advances if advance_counts_as_spend(a))


def committed_spend(store: Store, department: DepartmentId, period: Period) -> int:
    return spend_of(store.reports_for(department, period)) + advance_spend_of(store.advances_for(department, period))
