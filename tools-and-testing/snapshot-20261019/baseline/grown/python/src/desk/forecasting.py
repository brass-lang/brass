"""Where a department's period is heading: committed, pending, and the headroom left."""
from dataclasses import dataclass

from . import lines
from .host import Store
from .ids import DepartmentId, Money, Period
from .records import commitments_of
from .registry import Registry
from .reports import ReportStatus, counts_as_spend


@dataclass(frozen=True)
class Forecast:
    department: DepartmentId
    period: Period
    budget: Money
    committed: int
    pending: int
    projected: int
    headroom: int                  # negative when projected exceeds budget


def forecast(store: Store, reg: Registry, department: DepartmentId, period: Period) -> Forecast:
    dept = store.department(department)
    reports = store.reports_for(dept.id, period)
    committed = sum(lines.total(r.lines) for r in reports if counts_as_spend(r)) + commitments_of(reg.pos_for(dept.id, period))
    pending = sum(lines.total(r.lines) for r in reports if r.status is ReportStatus.SUBMITTED)
    projected = committed + pending
    return Forecast(dept.id, period, dept.budget, committed, pending, projected, dept.budget - projected)
