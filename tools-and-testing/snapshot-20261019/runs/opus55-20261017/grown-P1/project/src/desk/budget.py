from typing import Sequence

from .host import Store
from .ids import DepartmentId, Period
from .lines import budgeted_total
from .records import advance_spend
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report]) -> int:
    return sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))


def department_spend(store: Store, department: DepartmentId, period: Period) -> int:
    """Approved and paid reports, plus approved and paid advances not yet settled."""
    return spend_of(store.reports_for(department, period)) + advance_spend(store.advances_for(department, period))
