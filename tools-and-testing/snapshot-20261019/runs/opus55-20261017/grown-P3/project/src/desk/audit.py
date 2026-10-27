from dataclasses import dataclass

from .ids import Badge, ReportId
from .records import AdvanceStatus
from .reports import ReportStatus


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId                     # or an advance's id
    from_status: ReportStatus | AdvanceStatus
    to_status: ReportStatus | AdvanceStatus
    reason: str
