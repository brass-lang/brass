from typing import Sequence

from .advances import Advance, counts_as_spend as advance_counts_as_spend
from .lines import budgeted_total
from .reports import Report, counts_as_spend


def spend_of(reports: Sequence[Report], advances: Sequence[Advance] = ()) -> int:
    report_spend = sum(budgeted_total(r.lines) for r in reports if counts_as_spend(r))
    advance_spend = sum(a.amount for a in advances if advance_counts_as_spend(a))
    return report_spend + advance_spend
