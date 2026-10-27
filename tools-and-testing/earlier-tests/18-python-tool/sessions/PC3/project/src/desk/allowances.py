"""Per diem and mileage: a Travel line priced from the fixed rate tables. Validated at submit, like any line."""
from . import reports
from .checks import active_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Category, ReportId
from .lines import Line
from .records import MILEAGE, PER_DIEM, Region, Vehicle

MAX_DAYS = 30
MAX_KM = 2_000


def add_per_diem(store: Store, report_id: ReportId, badge: Badge, region: Region, days: int) -> None:
    r = _editable(store, report_id, badge)
    if not 1 <= days <= MAX_DAYS:
        raise Failure(FailureCode.INVALID_INPUT, "per diem covers 1 to 30 days")
    store.save_report(reports.add_line(r, Line(Category.TRAVEL, PER_DIEM[region] * days, "per diem", True)))


def add_mileage(store: Store, report_id: ReportId, badge: Badge, vehicle: Vehicle, km: int) -> None:
    r = _editable(store, report_id, badge)
    if not 1 <= km <= MAX_KM:
        raise Failure(FailureCode.INVALID_INPUT, "mileage covers 1 to 2,000 km")
    store.save_report(reports.add_line(r, Line(Category.TRAVEL, MILEAGE[vehicle] * km, "mileage", True)))


def _editable(store: Store, report_id: ReportId, badge: Badge) -> reports.Report:
    active_staff(store, badge)
    r = store.report(report_id)
    if r.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the submitter may act on this report")
    if not reports.editable(r):
        raise Failure(FailureCode.CONFLICT, "the report is not editable")
    if len(r.lines) >= reports.MAX_LINES:
        raise Failure(FailureCode.INVALID_INPUT, "a report holds at most 50 lines")
    return r
