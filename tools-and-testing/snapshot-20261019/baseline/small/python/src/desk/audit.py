from dataclasses import dataclass

from .ids import Badge, ReportId
from .reports import ReportStatus


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId
    from_status: ReportStatus
    to_status: ReportStatus
    reason: str
