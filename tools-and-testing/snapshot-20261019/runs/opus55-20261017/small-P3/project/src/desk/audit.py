from dataclasses import dataclass
from typing import Union

from .advances import AdvanceStatus
from .ids import Badge, ReportId
from .reports import ReportStatus

Status = Union[ReportStatus, AdvanceStatus]


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId                # a report's id, or an advance's
    from_status: Status
    to_status: Status
    reason: str
