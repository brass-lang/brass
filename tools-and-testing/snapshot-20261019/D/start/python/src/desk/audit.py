from dataclasses import dataclass
from enum import Enum
from typing import Union

from .advances import AdvanceStatus
from .ids import Badge, ReportId
from .reports import ReportStatus

Status = Union[ReportStatus, AdvanceStatus]


class Subject(Enum):
    REPORT = "Report"
    ADVANCE = "Advance"


@dataclass(frozen=True)
class Entry:
    who: Badge
    subject: Subject
    subject_id: ReportId             # a report's or an advance's id, per subject
    from_status: Status
    to_status: Status
    reason: str
