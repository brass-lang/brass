from dataclasses import dataclass
from typing import Union

from .ids import Badge, ReportId
from .records import AdvanceStatus
from .reports import ReportStatus

Status = Union[ReportStatus, AdvanceStatus]


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId                     # or an advance's id
    from_status: Status
    to_status: Status
    reason: str
