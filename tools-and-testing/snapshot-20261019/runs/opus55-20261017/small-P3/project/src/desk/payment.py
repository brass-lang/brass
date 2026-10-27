"""Paying approved reports and advances, settling advances, and closing periods. Finance only."""
from . import advances, lines, reports
from .advances import AdvanceStatus
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


def pay_advance(store: Store, ledger: Ledger, advance_id: ReportId, finance_badge: Badge) -> str:
    who = _finance(store, finance_badge)
    a = store.advance(advance_id)
    if a.status is not AdvanceStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the advance is not approved")
    reference = ledger.pay(a.badge, a.amount, a.id)
    store.save_advance(advances.pay(a, reference))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.APPROVED, AdvanceStatus.PAID, "paid"))
    return reference


SETTLED = "settled"


def pay_against(store: Store, ledger: Ledger, report_id: ReportId, advance_id: ReportId, finance_badge: Badge) -> str:
    """Pays an approved report less one of its submitter's paid advances, and settles the advance.
    Returns the ledger reference, or SETTLED when the advance covered the whole report and nothing was paid."""
    who = _finance(store, finance_badge)
    r = store.report(report_id)
    a = store.advance(advance_id)
    if r.status is not ReportStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the report is not approved")
    if a.status is not AdvanceStatus.PAID:
        raise Failure(FailureCode.CONFLICT, "the advance is not paid, or is already settled")
    if a.badge != r.badge or a.period != r.period:
        raise Failure(FailureCode.CONFLICT, "the advance is not the report submitter's for the report's period")
    due = lines.total(r.lines)
    if a.amount >= due:
        reference, result, owed = a.reference, SETTLED, a.amount - due
    else:
        reference = ledger.pay(r.badge, due - a.amount, r.id)
        result, owed = reference, 0
    store.save_report(reports.pay(r, reference))
    store.append_audit(Entry(who.badge, r.id, ReportStatus.APPROVED, ReportStatus.PAID, f"paid against advance {a.id}"))
    store.save_advance(advances.settle(a, owed))
    store.append_audit(Entry(who.badge, a.id, AdvanceStatus.PAID, AdvanceStatus.SETTLED, f"settled against report {r.id}"))
    return result


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
