"""Read-only views."""
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from . import lines
from .budget import spend_of
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, DepartmentId, Period, ReportId
from .records import counts_as_spend as advance_counts_as_spend
from .reports import ReportStatus, counts_as_spend
from .review import may_act


def spend(store: Store, department: DepartmentId, period: Period) -> int:
    dept = store.department(department)
    return spend_of(store.reports_for(dept.id, period), store.advances_for(dept.id, period))


@dataclass(frozen=True)
class Row:
    id: ReportId
    badge: Badge
    status: Enum
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
    advances = store.advances_for(dept.id, period)
    rows = tuple(Row(r.id, r.badge, r.status, lines.total(r.lines), lines.budgeted_total(r.lines)) for r in reports if counts_as_spend(r))
    advance_rows = tuple(Row(a.id, a.badge, a.status, a.amount, a.amount) for a in advances if advance_counts_as_spend(a))
    spent = spend_of(reports, advances)
    return Statement(dept.id, period, dept.budget, spent, dept.budget - spent, rows + advance_rows)


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
