"""Paying approved reports and advances, settling advances against reports, and closing periods. Finance only."""
from . import advances, lines, reports
from .advances import AdvanceStatus
from .audit import Entry
from .errors import Failure, FailureCode
from .host import Ledger, Store
from .ids import AdvanceId, Badge, Period, ReportId
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


def pay_advance(store: Store, ledger: Ledger, advance_id: AdvanceId, finance_badge: Badge) -> str:
    who = _finance(store, finance_badge)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(advances.pay(a, reference))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
    return reference


def pay_against(store: Store, ledger: Ledger, report_id: ReportId, advance_id: AdvanceId, finance_badge: Badge) -> str:
    who = _finance(store, finance_badge)
    r = store.report(report_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid")
    if a.badge != r.badge:
        raise Failure(FailureCode.CONFLICT, "the advance belongs to a different staff member")
    if a.period != r.period:
        raise Failure(FailureCode.CONFLICT, "the advance is for a different period")

    total = lines.total(r.lines)
    if a.amount >= total:
        store.save_report(reports.pay(r, a.reference))
        store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID,
                                 f"settled against advance {a.id}"))
        store.save_advance(advances.settle(a, a.amount - total))
        store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED,
                                 f"settled against report {r.id}"))
        return "settled"

    remainder = total - a.amount
    reference = ledger.pay(r.badge, remainder, r.id)
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID,
                             f"paid; settled against advance {a.id}"))
    store.save_advance(advances.settle(a, 0))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED,
                             f"settled against report {r.id}"))
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
