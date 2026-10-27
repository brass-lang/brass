"""Is a period ready to close? It reports; it closes nothing."""
from dataclasses import dataclass

from .host import Store
from .ids import Period
from .records import CardStatus, PoStatus
from .registry import Registry
from .reports import ReportStatus


@dataclass(frozen=True)
class Readiness:
    period: Period
    closed: bool
    open_card_txns: int
    requested_pos: int
    submitted_reports: int
    ready: bool


def period_readiness(store: Store, reg: Registry, period: Period) -> Readiness:
    closed = store.period_closed(period)
    open_txns = sum(1 for t in reg.txns_for(period) if t.status is CardStatus.OPEN)
    requested = sum(1 for d in reg.departments() for po in reg.pos_for(d, period) if po.status is PoStatus.REQUESTED)
    submitted = sum(1 for r in store.submitted_reports() if r.period == period and r.status is ReportStatus.SUBMITTED)
    return Readiness(period, closed, open_txns, requested, submitted,
                     not closed and open_txns == 0 and requested == 0 and submitted == 0)
