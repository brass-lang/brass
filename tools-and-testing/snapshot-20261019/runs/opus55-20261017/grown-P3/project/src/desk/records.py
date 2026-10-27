"""The records the grown desk keeps beside reports: vendors, purchase orders, card transactions, delegations, cost centers, card limits, policy exceptions, cash advances."""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence

from .errors import Failure, FailureCode
from .ids import Badge, Category, DepartmentId, Money, Period, ReportId

VendorId = str
PoId = str
TxnId = str
DelegationId = str
CostCenterId = str
EntityId = str
ExceptionId = str
AdvanceId = str

MAX_TEXT = 200
MAX_PO_APPROVALS = 2   # as a report's: the last approval completes the chain
MAX_ADVANCE_APPROVALS = 2   # likewise


class Region(Enum):
    ISLAND = "Island"
    MAINLAND = "Mainland"
    OFFSITE = "Offsite"


class Vehicle(Enum):
    CAR = "Car"
    TRUCK = "Truck"
    BOAT = "Boat"


class PoStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    RECEIVED = "Received"
    CLOSED = "Closed"


class CardStatus(Enum):
    OPEN = "Open"
    MATCHED = "Matched"
    DISPUTED = "Disputed"


class ExceptionStatus(Enum):
    PENDING = "Pending"
    GRANTED = "Granted"
    DENIED = "Denied"


class AdvanceStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    PAID = "Paid"
    SETTLED = "Settled"


PER_DIEM = {Region.ISLAND: 9_000, Region.MAINLAND: 6_000, Region.OFFSITE: 12_000}     # cents per day
MILEAGE = {Vehicle.CAR: 60, Vehicle.TRUCK: 90, Vehicle.BOAT: 250}                     # cents per kilometre

PO_TRANSITIONS = {
    PoStatus.REQUESTED: {PoStatus.APPROVED, PoStatus.REJECTED},
    PoStatus.APPROVED: {PoStatus.RECEIVED},
    PoStatus.RECEIVED: {PoStatus.CLOSED},
    PoStatus.REJECTED: set(),
    PoStatus.CLOSED: set(),
}

CARD_TRANSITIONS = {
    CardStatus.OPEN: {CardStatus.MATCHED, CardStatus.DISPUTED},
    CardStatus.DISPUTED: {CardStatus.OPEN},
    CardStatus.MATCHED: set(),
}

EXCEPTION_TRANSITIONS = {
    ExceptionStatus.PENDING: {ExceptionStatus.GRANTED, ExceptionStatus.DENIED},
    ExceptionStatus.GRANTED: set(),
    ExceptionStatus.DENIED: set(),
}

ADVANCE_TRANSITIONS = {
    AdvanceStatus.REQUESTED: {AdvanceStatus.APPROVED},
    AdvanceStatus.APPROVED: {AdvanceStatus.PAID},
    AdvanceStatus.PAID: {AdvanceStatus.SETTLED},
    AdvanceStatus.SETTLED: set(),
}


@dataclass(frozen=True)
class Vendor:
    id: VendorId
    name: str
    active: bool


@dataclass(frozen=True)
class PurchaseOrder:
    id: PoId
    vendor: VendorId
    requested_by: Badge
    department: DepartmentId
    period: Period
    amount: Money
    status: PoStatus
    approvals: Sequence[Badge] = ()
    received: Money = 0                  # set only once Received


@dataclass(frozen=True)
class CardTxn:
    id: TxnId
    badge: Badge                         # the card holder
    period: Period
    amount: Money
    category: Category
    merchant: str
    status: CardStatus
    matched: Optional[ReportId] = None


@dataclass(frozen=True)
class Delegation:
    id: DelegationId
    delegator: Badge
    delegate: Badge
    first: Period
    last: Period
    revoked: bool = False


@dataclass(frozen=True)
class Entity:
    id: EntityId
    name: str


@dataclass(frozen=True)
class CostCenter:
    id: CostCenterId
    entity: EntityId
    name: str


@dataclass(frozen=True)
class CardLimit:
    badge: Badge
    limit: Money


@dataclass(frozen=True)
class PolicyException:
    id: ExceptionId
    report: ReportId
    position: int                        # 1-based line position
    badge: Badge                         # who asked
    reason: str
    status: ExceptionStatus
    decided_by: Optional[Badge] = None


@dataclass(frozen=True)
class Advance:
    id: AdvanceId
    badge: Badge                         # who asked
    department: DepartmentId
    period: Period
    amount: Money
    status: AdvanceStatus
    approvals: Sequence[Badge] = ()
    reference: Optional[str] = None      # set only once Paid
    owed: Optional[Money] = None         # set only once Settled: what the staff member owes back, 0 when the report covered it


def _move(record, transitions, status, **fields):
    if status not in transitions[record.status]:
        raise Failure(FailureCode.CONFLICT, f"a {record.status.value} record cannot become {status.value}")
    return replace(record, status=status, **fields)


def advance_po(po: PurchaseOrder, status: PoStatus, **fields) -> PurchaseOrder:
    return _move(po, PO_TRANSITIONS, status, **fields)


def add_po_approval(po: PurchaseOrder, who: Badge) -> PurchaseOrder:
    if po.status is not PoStatus.REQUESTED or len(po.approvals) >= MAX_PO_APPROVALS:
        raise Failure(FailureCode.CONFLICT, "the purchase order is not awaiting another approval")
    return replace(po, approvals=(*po.approvals, who))


def advance_txn(t: CardTxn, status: CardStatus, **fields) -> CardTxn:
    return _move(t, CARD_TRANSITIONS, status, **fields)


def settle_exception(e: PolicyException, status: ExceptionStatus, decided_by: Badge) -> PolicyException:
    return _move(e, EXCEPTION_TRANSITIONS, status, decided_by=decided_by)


def move_advance(a: Advance, status: AdvanceStatus, **fields) -> Advance:
    return _move(a, ADVANCE_TRANSITIONS, status, **fields)


def add_advance_approval(a: Advance, who: Badge) -> Advance:
    if a.status is not AdvanceStatus.REQUESTED or len(a.approvals) >= MAX_ADVANCE_APPROVALS:
        raise Failure(FailureCode.CONFLICT, "the advance is not awaiting another approval")
    return replace(a, approvals=(*a.approvals, who))


def in_force(d: Delegation, period: Period) -> bool:
    return not d.revoked and d.first <= period <= d.last


def committed(po: PurchaseOrder) -> Money:
    if po.status is PoStatus.APPROVED:
        return po.amount
    if po.status in (PoStatus.RECEIVED, PoStatus.CLOSED):
        return po.received
    return 0


def commitments_of(pos: Sequence[PurchaseOrder]) -> int:
    return sum(committed(po) for po in pos)


def advance_counts(a: Advance) -> bool:
    """Approved and paid advances count against the budget; a settled one gives way to its report."""
    return a.status in (AdvanceStatus.APPROVED, AdvanceStatus.PAID)


def advance_spend(advances: Sequence[Advance]) -> int:
    return sum(a.amount for a in advances if advance_counts(a))


def text_ok(text: str) -> bool:
    return 1 <= len(text) <= MAX_TEXT
