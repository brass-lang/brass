from typing import Sequence

from .lines import budgeted_total
from .records import advance_spend_of
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report]) -> int:
    return sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))


def department_spend(store, department, period) -> int:
    """Approved and paid reports, plus approved and paid (not yet settled) advances."""
    return spend_of(store.reports_for(department, period)) + advance_spend_of(store.advances_for(department, period))
