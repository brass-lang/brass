from dataclasses import dataclass
from typing import Optional

from .ids import Badge, DepartmentId, Money, Role


@dataclass(frozen=True)
class Staff:
    badge: Badge
    name: str
    department: DepartmentId
    supervisor: Optional[Badge]
    role: Role
    active: bool


@dataclass(frozen=True)
class Department:
    id: DepartmentId
    director: Badge
    budget: Money


def is_finance(s: Staff) -> bool:
    return s.active and s.role is Role.FINANCE
