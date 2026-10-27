"""Paying approved reports and closing periods. Finance only."""
from . import advances, lines, reports
from .advances import AdvanceStatus
from .audit import Entry, Subject
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
    store.append_audit(Entry(who.badge, Subject.REPORT, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid"))
    return reference


def pay_advance(store: Store, ledger: Ledger, advance_id: ReportId, finance_badge: Badge) -> str:
    who = _finance(store, finance_badge)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(advances.pay(a, reference))
    store.append_audit(Entry(who.badge, Subject.ADVANCE, a.id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
    return reference


SETTLED = "settled"


def pay_against(store: Store, ledger: Ledger, report_id: ReportId, advance_id: ReportId, finance_badge: Badge) -> str:
    """Pay an approved report less a paid advance, settling the advance. Returns the reference, or SETTLED when nothing was paid."""
    who = _finance(store, finance_badge)
    r = store.report(report_id)
    a = store.advance(advance_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid, or is already settled")
    if a.badge != r.badge or a.period != r.period:
        raise Failure(FailureCode.CONFLICT, "an advance settles only a report by the same staff member in the same period")
    due = lines.total(r.lines) - a.amount
    reference = ledger.pay(r.badge, due, r.id) if due > 0 else a.reference
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, Subject.REPORT, r.id, ReportStatus.APPROVED, ReportStatus.PAID, "paid against an advance"))
    store.save_advance(advances.settle(a, max(0, -due)))
    store.append_audit(Entry(who.badge, Subject.ADVANCE, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, "settled"))
    return reference if due > 0 else SETTLED


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
