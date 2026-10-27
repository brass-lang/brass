"""Raising, approving, receiving, and closing purchase orders against a department's PO allowance."""
from . import records, routing
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import MONEY_MAX, Badge, DepartmentId, Money, Period, Role
from .records import PoId, PoStatus, PurchaseOrder, VendorId, commitments_of, in_force
from .registry import Registry
from .staff import Staff


def raise_po(store: Store, reg: Registry, badge: Badge, vendor_id: VendorId, amount: Money, period: Period) -> PoId:
    who = active_staff(store, badge)
    if not reg.vendor(vendor_id).active:
        raise Failure(FailureCode.CONFLICT, "the vendor is not active")
    if not 1 <= amount <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "a purchase order is for at least one cent")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    id = store.next_id()
    reg.save_po(PurchaseOrder(id, vendor_id, who.badge, who.department, period, amount, PoStatus.REQUESTED, (), 0))
    return id


def approve_po(store: Store, reg: Registry, po_id: PoId, approver: Badge) -> PoStatus:
    po, who = _gate(store, reg, po_id, approver)
    if len(po.approvals) + 1 >= routing.steps_for(po.amount):
        if commitments_of(reg.pos_for(po.department, po.period)) + po.amount > reg.allowance(po.department, po.period):
            raise Failure(FailureCode.CONFLICT, "the department's PO allowance for this period would be exceeded")
        reg.save_po(records.advance_po(po, PoStatus.APPROVED))
        return PoStatus.APPROVED
    reg.save_po(records.add_po_approval(po, who.badge))
    return PoStatus.REQUESTED


def reject_po(store: Store, reg: Registry, po_id: PoId, approver: Badge) -> None:
    po, _ = _gate(store, reg, po_id, approver)
    reg.save_po(records.advance_po(po, PoStatus.REJECTED))


def receive_po(store: Store, reg: Registry, po_id: PoId, badge: Badge, received_amount: Money) -> None:
    active_staff(store, badge)
    po = reg.po(po_id)
    if po.requested_by != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the requester may receive a purchase order")
    if po.status is not PoStatus.APPROVED:
        raise Failure(FailureCode.CONFLICT, "the purchase order is not approved")
    if not 1 <= received_amount <= po.amount:
        raise Failure(FailureCode.INVALID_INPUT, "the received amount is from one cent to the ordered amount")
    reg.save_po(records.advance_po(po, PoStatus.RECEIVED, received=received_amount))


def close_po(store: Store, reg: Registry, po_id: PoId, finance_badge: Badge) -> None:
    finance_staff(store, finance_badge)
    po = reg.po(po_id)
    if po.status is not PoStatus.RECEIVED:
        raise Failure(FailureCode.CONFLICT, "the purchase order is not received")
    reg.save_po(records.advance_po(po, PoStatus.CLOSED))


def po_commitments(store: Store, reg: Registry, department: DepartmentId, period: Period) -> int:
    dept = store.department(department)
    return commitments_of(reg.pos_for(dept.id, period))


def accepted_for(store: Store, reg: Registry, po: PurchaseOrder, who: Staff) -> bool:
    """May `who` act on the PO's next step? Raises Conflict when no one can."""
    role = routing.role_for(len(po.approvals) + 1)
    if role is Role.FINANCE:
        return who.role is Role.FINANCE
    if role is Role.SUPERVISOR:
        requester = store.staff(po.requested_by)
        if requester.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the requester has no supervisor")
        required = requester.supervisor
    else:
        required = store.department(po.department).director
    person = store.staff(required)
    delegates = [d.delegate for d in reg.delegations_from(person.badge) if in_force(d, po.period)]
    if person.active:
        return who.badge == person.badge or who.badge in delegates
    if not delegates:
        raise Failure(FailureCode.CONFLICT, f"{required} is inactive and has no delegate in force")
    return who.badge in delegates


def _gate(store: Store, reg: Registry, po_id: PoId, approver: Badge) -> tuple[PurchaseOrder, Staff]:
    who = active_staff(store, approver)
    po = reg.po(po_id)
    if po.status is not PoStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the purchase order is not awaiting approval")
    if store.period_closed(po.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == po.requested_by:
        raise Failure(FailureCode.UNAUTHORIZED, "a purchase order cannot be approved by its requester")
    if not accepted_for(store, reg, po, who):
        raise Failure(FailureCode.UNAUTHORIZED, "not this purchase order's next approver")
    return po, who
