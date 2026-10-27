"""A department's period at a glance: report counts, open card transactions, PO commitments."""
from dataclasses import dataclass

from .errors import Failure, FailureCode
from .host import Store
from .ids import DepartmentId, Money, Period
from .records import CardStatus, commitments_of
from .registry import Registry
from .reports import ReportStatus


@dataclass(frozen=True)
class PeriodSummary:
    department: DepartmentId
    period: Period
    submitted: int
    approved: int
    paid: int
    open_card_txns: int
    po_committed: Money


def period_summary(store: Store, reg: Registry, department: DepartmentId, period: Period) -> PeriodSummary:
    dept = store.department(department)
    statuses = [r.status for r in store.reports_for(dept.id, period)]
    open_txns = 0
    for t in reg.txns_for(period):
        if t.status is not CardStatus.OPEN:
            continue
        try:
            holder = store.staff(t.badge)
        except Failure as f:
            if f.code is not FailureCode.NOT_FOUND:        # a holder no longer on file is skipped
                raise
            continue
        if holder.department == dept.id:
            open_txns += 1
    return PeriodSummary(dept.id, period,
                         statuses.count(ReportStatus.SUBMITTED), statuses.count(ReportStatus.APPROVED), statuses.count(ReportStatus.PAID),
                         open_txns, commitments_of(reg.pos_for(dept.id, period)))
