from dataclasses import dataclass
from typing import Union

from .ids import Badge, ReportId
from .records import AdvanceStatus
from .reports import ReportStatus


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId                     # an advance's id, for an advance's entries
    from_status: Union[ReportStatus, AdvanceStatus]
    to_status: Union[ReportStatus, AdvanceStatus]
    reason: str
