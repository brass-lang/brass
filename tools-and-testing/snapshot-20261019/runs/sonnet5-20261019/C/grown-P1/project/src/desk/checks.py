"""The staff checks the grown desk's entry points share."""
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Role
from .staff import Staff


def active_staff(store: Store, badge: Badge) -> Staff:
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    return who


def finance_staff(store: Store, badge: Badge) -> Staff:
    who = active_staff(store, badge)
    if who.role is not Role.FINANCE:
        raise Failure(FailureCode.UNAUTHORIZED, "only finance staff may do this")
    return who
