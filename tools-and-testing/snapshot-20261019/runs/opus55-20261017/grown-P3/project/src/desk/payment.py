"""Paying approved reports and closing periods. Finance only."""
from . import lines, reports
from .audit import Entry
from .errors import Failure, FailureCode
from .host import Ledger, Store
from .ids import Badge, Period, ReportId
from .reports import ReportStatus
from .staff import Staff, is_finance


def pay(store: Store, ledger: Ledger, report_id: ReportId, finance_badge: Badge) -> str:
    who = _finance(store, finance_badge)
    r = store.report(report_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    reference = ledger.pay(r.badge, lines.total(r.lines), r.id)
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
    return reference


def close_period(store: Store, period: Period, finance_badge: Badge) -> None:
    _finance(store, finance_badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is already closed")
    store.close_period(period)


def _finance(store: Store, badge: Badge) -> Staff:
    who = store.staff(badge)
    if not is_finance(who):
        raise Failure(FailureCode.UNAUTHORIZED, "only active finance staff may do this")
    return who
