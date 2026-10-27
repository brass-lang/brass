"""Read-only views."""
from dataclasses import dataclass
from typing import Sequence

from . import lines
from . import advances
from .budget import department_commitment, trip_commitment
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, DepartmentId, Period, ReportId
from .advances import AdvanceStatus
from .reports import ReportStatus, counts_as_spend
from .review import may_act
from .trips import TripStatus


def spend(store: Store, department: DepartmentId, period: Period) -> int:
    dept = store.department(department)
    return department_commitment(store, dept.id, period)


@dataclass(frozen=True)
class Row:
    id: ReportId
    badge: Badge
    status: ReportStatus | AdvanceStatus | TripStatus
    total: int
    budgeted: int


@dataclass(frozen=True)
class Statement:
    department: DepartmentId
    period: Period
    budget: int
    spend: int
    remaining: int                 # negative after a finance override
    rows: Sequence[Row]


def statement(store: Store, department: DepartmentId, period: Period) -> Statement:
    dept = store.department(department)
    reports = store.reports_for(dept.id, period)
    advs = store.advances_for(dept.id, period)
    rows = tuple(Row(r.id, r.badge, r.status, lines.total(r.lines), lines.budgeted_total(r.lines)) for r in reports if counts_as_spend(r)) \
        + tuple(Row(a.id, a.badge, a.status, a.amount, a.amount) for a in advs if advances.counts_as_spend(a))
    for t in store.trips_for(dept.id, period):
        if t.status is not TripStatus.APPROVED:
            continue
        amount = trip_commitment(store, t)
        if amount > 0:
            rows = rows + (Row(t.id, t.badge, t.status, amount, amount),)
    spent = department_commitment(store, dept.id, period)
    return Statement(dept.id, period, dept.budget, spent, dept.budget - spent, rows)


def outstanding_advances(store: Store, today: Period) -> list[ReportId]:
    return [a.id for a in store.paid_advances() if advances.outstanding(a, today)]


def pending_for(store: Store, approver: Badge) -> list[ReportId]:
    who = store.staff(approver)
    if not who.active:
        return []
    pending = []
    for r in store.submitted_reports():
        if r.status is not ReportStatus.SUBMITTED or r.badge == who.badge:
            continue
        try:
            if may_act(store, r, who):
                pending.append(r.id)
        except Failure as f:
            if f.code is not FailureCode.CONFLICT:        # no determinable approver: not pending for anyone
                raise
    return pending
