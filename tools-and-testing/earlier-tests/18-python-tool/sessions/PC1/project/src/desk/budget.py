from typing import Sequence

from . import records
from .lines import budgeted_total
from .records import Advance
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report]) -> int:
    return sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))


def advance_spend_of(advances: Sequence[Advance]) -> int:
    return sum(a.amount for a in advances if records.counts_as_spend(a))
