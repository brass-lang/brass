"""The vendors purchase orders are raised against. Finance onboards and deactivates them."""
from dataclasses import replace

from .checks import finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge
from .records import PoStatus, Vendor, VendorId, text_ok
from .registry import Registry


def onboard_vendor(store: Store, reg: Registry, finance_badge: Badge, name: str) -> VendorId:
    finance_staff(store, finance_badge)
    if not text_ok(name):
        raise Failure(FailureCode.INVALID_INPUT, "a vendor name is 1 to 200 characters")
    id = store.next_id()
    reg.save_vendor(Vendor(id, name, True))
    return id


def deactivate_vendor(store: Store, reg: Registry, finance_badge: Badge, vendor_id: VendorId) -> None:
    finance_staff(store, finance_badge)
    v = reg.vendor(vendor_id)
    if not v.active:
        raise Failure(FailureCode.CONFLICT, "the vendor is already inactive")
    if any(po.status in (PoStatus.REQUESTED, PoStatus.APPROVED) for po in reg.pos_of_vendor(v.id)):
        raise Failure(FailureCode.CONFLICT, "the vendor has purchase orders still open")
    reg.save_vendor(replace(v, active=False))


def vendor_spend(reg: Registry, vendor_id: VendorId) -> int:
    v = reg.vendor(vendor_id)
    return sum(po.received for po in reg.pos_of_vendor(v.id) if po.status in (PoStatus.RECEIVED, PoStatus.CLOSED))
