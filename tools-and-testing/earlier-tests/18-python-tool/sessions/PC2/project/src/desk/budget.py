from typing import Sequence

from .lines import budgeted_total
from .records import Advance, counts_as_advance_spend
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report], advances: Sequence[Advance] = ()) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advances if counts_as_advance_spend(a)))
