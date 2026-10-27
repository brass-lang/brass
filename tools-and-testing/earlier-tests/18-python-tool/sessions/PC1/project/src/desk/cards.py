"""Corporate card transactions: imported by finance, matched by the holder to a report line, or disputed."""
from . import records
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import MONEY_MAX, Badge, Category, Money, Period, ReportId
from .records import CardStatus, CardTxn, TxnId, text_ok
from .registry import Registry
from .reports import ReportStatus

MATCHABLE = (ReportStatus.SUBMITTED, ReportStatus.APPROVED, ReportStatus.PAID)


def import_txn(store: Store, reg: Registry, finance_badge: Badge, badge: Badge, period: Period, amount: Money,
               category: Category, merchant: str) -> TxnId:
    finance_staff(store, finance_badge)
    holder = store.staff(badge)
    if not 1 <= amount <= MONEY_MAX or not text_ok(merchant):
        raise Failure(FailureCode.INVALID_INPUT, "a transaction needs an amount of at least one cent and a merchant of 1 to 200 characters")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    id = store.next_id()
    reg.save_txn(CardTxn(id, holder.badge, period, amount, category, merchant, CardStatus.OPEN, None))
    return id


def match_txn(store: Store, reg: Registry, txn_id: TxnId, report_id: ReportId, badge: Badge) -> None:
    t = _own_open(store, reg, txn_id, badge)
    r = store.report(report_id)
    if r.badge != t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "the report is not the card holder's")
    if r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is for another period")
    if r.status not in MATCHABLE:
        raise Failure(FailureCode.CONFLICT, "the report is not submitted, approved, or paid")
    if not any(l.category is t.category and l.amount == t.amount for l in r.lines):
        raise Failure(FailureCode.INVALID_INPUT, "no line of the report has the transaction's category and amount")
    reg.save_txn(records.advance_txn(t, CardStatus.MATCHED, matched=r.id))


def dispute_txn(store: Store, reg: Registry, txn_id: TxnId, badge: Badge) -> None:
    t = _own_open(store, reg, txn_id, badge)
    reg.save_txn(records.advance_txn(t, CardStatus.DISPUTED))


def unmatched(reg: Registry, period: Period) -> list[TxnId]:
    return [t.id for t in reg.txns_for(period) if t.status is CardStatus.OPEN]


def _own_open(store: Store, reg: Registry, txn_id: TxnId, badge: Badge) -> CardTxn:
    active_staff(store, badge)
    t = reg.txn(txn_id)
    if t.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the card holder may act on this transaction")
    if t.status is not CardStatus.OPEN:
        raise Failure(FailureCode.CONFLICT, "the transaction is not open")
    return t
