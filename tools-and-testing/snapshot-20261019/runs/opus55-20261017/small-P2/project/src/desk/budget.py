from typing import Sequence

from . import advances as advances_
from .advances import Advance
from .lines import budgeted_total
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report], advances: Sequence[Advance] = ()) -> int:
    return (sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
            + sum(a.amount for a in advances if advances_.counts_as_spend(a)))
