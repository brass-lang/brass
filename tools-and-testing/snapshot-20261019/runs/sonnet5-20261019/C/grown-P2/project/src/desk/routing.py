from typing import Optional

from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, DepartmentId, Role

SUPERVISOR_ONLY_UP_TO = 50_000
DIRECTOR_UP_TO = 500_000

STEP_ROLES = (Role.SUPERVISOR, Role.DIRECTOR, Role.FINANCE)


def steps_for(total: int) -> int:
    if total <= SUPERVISOR_ONLY_UP_TO:
        return 1
    if total <= DIRECTOR_UP_TO:
        return 2
    return 3


def role_for(step: int) -> Role:
    return STEP_ROLES[step - 1]


def required_approver(store: Store, submitter: Badge, department: DepartmentId, approvals_count: int) -> Optional[Badge]:
    """The badge required for the next step, or None when any active finance staff member will do."""
    role = role_for(approvals_count + 1)
    if role is Role.FINANCE:
        return None
    if role is Role.SUPERVISOR:
        who = store.staff(submitter)
        if who.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the submitter has no supervisor")
        return stand_in(store, who.supervisor)
    return stand_in(store, store.department(department).director)


def stand_in(store: Store, required: Badge) -> Badge:
    person = store.staff(required)
    if person.active:
        return required
    if person.supervisor is not None and store.staff(person.supervisor).active:
        return person.supervisor
    raise Failure(FailureCode.CONFLICT, f"no active approver stands in for {required}")
