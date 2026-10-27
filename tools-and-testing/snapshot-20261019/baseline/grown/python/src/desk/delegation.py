"""Supervisors and directors lending their purchase-order approvals to someone else for a run of periods."""
from dataclasses import replace

from .checks import active_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Period, Role
from .records import Delegation, DelegationId
from .registry import Registry

MAX_SPAN = 11      # last - first: at most twelve periods


def grant_delegation(store: Store, reg: Registry, delegator: Badge, delegate: Badge, first: Period, last: Period) -> DelegationId:
    giver = active_staff(store, delegator)
    if giver.role not in (Role.SUPERVISOR, Role.DIRECTOR):
        raise Failure(FailureCode.UNAUTHORIZED, "only supervisors and directors may delegate")
    taker = active_staff(store, delegate)
    if taker.badge == giver.badge:
        raise Failure(FailureCode.INVALID_INPUT, "a delegation cannot be to oneself")
    if not (first <= last and last - first <= MAX_SPAN):
        raise Failure(FailureCode.INVALID_INPUT, "a delegation covers one to twelve periods")
    if any(not d.revoked and d.first <= last and first <= d.last for d in reg.delegations_from(giver.badge)):
        raise Failure(FailureCode.CONFLICT, "a delegation already covers part of that range")
    id = store.next_id()
    reg.save_delegation(Delegation(id, giver.badge, taker.badge, first, last, False))
    return id


def revoke_delegation(store: Store, reg: Registry, delegation_id: DelegationId, badge: Badge) -> None:
    active_staff(store, badge)
    d = reg.delegation(delegation_id)
    if d.delegator != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the delegator may revoke a delegation")
    if d.revoked:
        raise Failure(FailureCode.CONFLICT, "the delegation is already revoked")
    reg.save_delegation(replace(d, revoked=True))
