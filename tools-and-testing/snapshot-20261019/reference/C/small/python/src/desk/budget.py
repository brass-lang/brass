from typing import Sequence

from . import advances
from .advances import Advance
from .host import Store
from .ids import DepartmentId, Period
from .lines import budgeted_total
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report], advs: Sequence[Advance]) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advs if advances.counts_as_spend(a)))


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    return spend_of(store.reports_for(department, period), store.advances_for(department, period))
