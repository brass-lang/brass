import sys
sys.path.insert(0, "src")

from desk.ids import Category, Role
from desk.lines import Line
from desk.staff import Staff, Department
from desk.reports import Report, ReportStatus
from desk.records import Advance, AdvanceStatus
from desk.errors import Failure, FailureCode


class FakeStore:
    def __init__(self):
        self.staffs = {}
        self.departments = {}
        self.reports = {}
        self.advances = {}
        self.closed_periods = set()
        self.audit_log = []
        self._next = 0

    def staff(self, badge):
        if badge not in self.staffs:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self.staffs[badge]

    def report(self, id):
        return self.reports[id]

    def department(self, id):
        return self.departments[id]

    def reports_for(self, department, period):
        return [r for r in self.reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        return [r for r in self.reports.values() if r.status == ReportStatus.SUBMITTED]

    def period_closed(self, period):
        return period in self.closed_periods

    def next_id(self):
        self._next += 1
        return str(self._next)

    def save_report(self, report):
        self.reports[report.id] = report

    def append_audit(self, entry):
        self.audit_log.append(entry)

    def close_period(self, period):
        self.closed_periods.add(period)

    def advance(self, id):
        return self.advances[id]

    def advances_for(self, department, period):
        return [a for a in self.advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        return [a for a in self.advances.values() if a.status == AdvanceStatus.PAID]

    def save_advance(self, advance):
        self.advances[advance.id] = advance


class FakeLedger:
    def __init__(self):
        self.calls = []

    def pay(self, badge, amount, key):
        self.calls.append((badge, amount, key))
        return f"ref-{key}"


def build_store():
    s = FakeStore()
    s.departments["eng"] = Department("eng", "dir1", 1_000_000)
    s.staffs["staff1"] = Staff("staff1", "Staffer", "eng", "sup1", Role.STAFF, True)
    s.staffs["sup1"] = Staff("sup1", "Super", "eng", "dir1", Role.SUPERVISOR, True)
    s.staffs["dir1"] = Staff("dir1", "Director", "eng", None, Role.DIRECTOR, True)
    s.staffs["fin1"] = Staff("fin1", "Finance", "eng", None, Role.FINANCE, True)
    return s


if __name__ == "__main__":
    print("harness module loaded ok")
