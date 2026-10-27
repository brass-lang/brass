from dataclasses import dataclass
from typing import Union

from .advances import AdvanceStatus
from .ids import Badge, ReportId
from .reports import ReportStatus

Status = Union[ReportStatus, AdvanceStatus]


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId                     # an advance's state changes use the advance's id here
    from_status: Status
    to_status: Status
    reason: str
