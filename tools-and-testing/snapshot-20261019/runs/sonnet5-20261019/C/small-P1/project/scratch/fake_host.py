"""A minimal in-memory Store/Ledger for exercising the desk package in tests."""
import itertools
from dataclasses import dataclass
from typing import Dict, List, Sequence

from desk.advances import Advance
from desk.errors import Failure, FailureCode
from desk.ids import AdvanceId, Badge, DepartmentId, Period, ReportId
from desk.reports import Report
from desk.staff import Department, Staff


class FakeStore:
    def __init__(self):
        self._staff: Dict[Badge, Staff] = {}
        self._departments: Dict[DepartmentId, Department] = {}
        self._reports: Dict[ReportId, Report] = {}
        self._advances: Dict[AdvanceId, Advance] = {}
        self._closed_periods: set = set()
        self._audit: List = []
        self._counter = itertools.count(1)

    # setup helpers
    def add_staff(self, s: Staff) -> None:
        self._staff[s.badge] = s

    def add_department(self, d: Department) -> None:
        self._departments[d.id] = d

    def close_period_for_setup(self, period: Period) -> None:
        self._closed_periods.add(period)

    # Store protocol
    def staff(self, badge: Badge) -> Staff:
        if badge not in self._staff:
            raise Failure(FailureCode.NOT_FOUND, f"no such staff member {badge}")
        return self._staff[badge]

    def report(self, id: ReportId) -> Report:
        if id not in self._reports:
            raise Failure(FailureCode.NOT_FOUND, f"no such report {id}")
        return self._reports[id]

    def advance(self, id: AdvanceId) -> Advance:
        if id not in self._advances:
            raise Failure(FailureCode.NOT_FOUND, f"no such advance {id}")
        return self._advances[id]

    def department(self, id: DepartmentId) -> Department:
        if id not in self._departments:
            raise Failure(FailureCode.NOT_FOUND, f"no such department {id}")
        return self._departments[id]

    def reports_for(self, department: DepartmentId, period: Period) -> Sequence[Report]:
        return [r for r in self._reports.values() if r.department == department and r.period == period][:1000]

    def advances_for(self, department: DepartmentId, period: Period) -> Sequence[Advance]:
        return [a for a in self._advances.values() if a.department == department and a.period == period][:1000]

    def submitted_reports(self) -> Sequence[Report]:
        from desk.reports import ReportStatus
        return [r for r in self._reports.values() if r.status is ReportStatus.SUBMITTED]

    def paid_advances(self) -> Sequence[Advance]:
        from desk.advances import AdvanceStatus
        return [a for a in self._advances.values() if a.status is AdvanceStatus.PAID][:1000]

    def period_closed(self, period: Period) -> bool:
        return period in self._closed_periods

    def next_id(self) -> ReportId:
        return f"ID{next(self._counter)}"

    def save_report(self, report: Report) -> None:
        self._reports[report.id] = report

    def save_advance(self, advance: Advance) -> None:
        self._advances[advance.id] = advance

    def append_audit(self, entry) -> None:
        self._audit.append(entry)

    def close_period(self, period: Period) -> None:
        self._closed_periods.add(period)


class FakeLedger:
    def __init__(self):
        self.calls = []
        self._counter = itertools.count(1)

    def pay(self, badge: Badge, amount: int, key) -> str:
        ref = f"LEDGER{next(self._counter)}"
        self.calls.append((badge, amount, key, ref))
        return ref
