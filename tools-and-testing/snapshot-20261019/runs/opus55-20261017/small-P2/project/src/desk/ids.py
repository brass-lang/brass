from enum import Enum

Money = int          # whole cents, 0 to 1,000,000,000
Period = int         # month index, 1 to 1200
Badge = str          # 1 to 20 characters
ReportId = str
AdvanceId = str      # drawn from the same sequence as report ids
DepartmentId = str

MONEY_MAX = 1_000_000_000
PERIOD_MAX = 1200


class Role(Enum):
    STAFF = "Staff"
    SUPERVISOR = "Supervisor"
    DIRECTOR = "Director"
    FINANCE = "Finance"


class Category(Enum):
    FEED = "Feed"
    VETERINARY = "Veterinary"
    CONTAINMENT = "Containment"
    EQUIPMENT = "Equipment"
    TRAVEL = "Travel"
    OTHER = "Other"
