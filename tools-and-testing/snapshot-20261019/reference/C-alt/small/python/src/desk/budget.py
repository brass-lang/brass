from typing import Sequence

from .lines import budgeted_total
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report]) -> int:
    return sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
