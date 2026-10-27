"""Cost centers: groups of departments under a legal entity."""
from dataclasses import dataclass
from typing import Sequence

from . import lines
from .host import Store
from .ids import DepartmentId, Money, Period
from .records import CostCenterId, EntityId
from .registry import Registry
from .reports import counts_as_spend


@dataclass(frozen=True)
class CostCenterSummary:
    cost_center: CostCenterId
    entity: EntityId
    entity_name: str
    departments: Sequence[DepartmentId]
    approved_total: Money


def cost_center_summary(store: Store, reg: Registry, cost_center_id: CostCenterId, period: Period) -> CostCenterSummary:
    cc = reg.cost_center(cost_center_id)
    ent = reg.entity(cc.entity)
    departments = tuple(reg.departments_of(cc.id))
    approved = sum(lines.total(r.lines) for d in departments for r in store.reports_for(d, period) if counts_as_spend(r))
    return CostCenterSummary(cc.id, ent.id, ent.name, departments, approved)
