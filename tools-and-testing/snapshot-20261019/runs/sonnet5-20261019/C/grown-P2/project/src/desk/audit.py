from dataclasses import dataclass
from enum import Enum

from .ids import Badge, ReportId


@dataclass(frozen=True)
class Entry:
    who: Badge
    report: ReportId              # a report id, or an advance id for an advance's entries
    from_status: Enum
    to_status: Enum
    reason: str
