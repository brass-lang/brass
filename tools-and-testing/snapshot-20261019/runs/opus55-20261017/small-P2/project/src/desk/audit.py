from dataclasses import dataclass

from typing import Union

from .advances import AdvanceStatus
from .ids import AdvanceId, Badge, ReportId
from .reports import ReportStatus


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: Union[ReportId, AdvanceId]          # an advance's entries carry the advance's id here
    from_status: Union[ReportStatus, AdvanceStatus]
    to_status: Union[ReportStatus, AdvanceStatus]
    reason: str
