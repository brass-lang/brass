from dataclasses import dataclass
from enum import Enum
from typing import Union

from .advances import AdvanceStatus
from .trips import TripStatus
from .ids import Badge, ReportId
from .reports import ReportStatus

Status = Union[ReportStatus, AdvanceStatus, TripStatus]


class Subject(Enum):
    REPORT = "Report"
    ADVANCE = "Advance"
    TRIP = "Trip"


@dataclass(frozen=True)
class Entry:
    who: Badge
    subject: Subject
    subject_id: ReportId             # a report's, an advance's, or a trip's id, per subject
    from_status: Status
    to_status: Status
    reason: str
