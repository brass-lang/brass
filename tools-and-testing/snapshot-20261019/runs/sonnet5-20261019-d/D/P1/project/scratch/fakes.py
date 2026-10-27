"""In-memory Store/Registry/Ledger for exercising the desk package."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk.errors import Failure, FailureCode
from desk.staff import Staff, Department


class FakeStore:
    def __init__(self):
        self._staff = {}
        self._departments = {}
        self._reports = {}
        self._advances = {}
        self._trips = {}
        self._audit = []
        self._closed_periods = set()
        self._next = 0

    def add_staff(self, s: Staff):
        self._staff[s.badge] = s

    def add_department(self, d: Department):
        self._departments[d.id] = d

    def staff(self, badge):
        if badge not in self._staff:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self._staff[badge]

    def department(self, id):
        if id not in self._departments:
            raise Failure(FailureCode.NOT_FOUND, "no such department")
        return self._departments[id]

    def report(self, id):
        if id not in self._reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self._reports[id]

    def reports_for(self, department, period):
        return [r for r in self._reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        from desk.reports import ReportStatus
        return [r for r in self._reports.values() if r.status is ReportStatus.SUBMITTED]

    def period_closed(self, period):
        return period in self._closed_periods

    def next_id(self):
        self._next += 1
        return f"id{self._next}"

    def save_report(self, report):
        self._reports[report.id] = report

    def append_audit(self, entry):
        self._audit.append(entry)

    def close_period(self, period):
        self._closed_periods.add(period)

    def advance(self, id):
        if id not in self._advances:
            raise Failure(FailureCode.NOT_FOUND, "no such advance")
        return self._advances[id]

    def advances_for(self, department, period):
        return [a for a in self._advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        from desk.advances import AdvanceStatus
        return [a for a in self._advances.values() if a.status is AdvanceStatus.PAID]

    def save_advance(self, advance):
        self._advances[advance.id] = advance

    def trip(self, id):
        if id not in self._trips:
            raise Failure(FailureCode.NOT_FOUND, "no such trip")
        return self._trips[id]

    def trips_for(self, department, period):
        return [t for t in self._trips.values() if t.department == department and t.period == period]

    def trips_in(self, period):
        return [t for t in self._trips.values() if t.period == period]

    def save_trip(self, trip):
        self._trips[trip.id] = trip


class FakeRegistry:
    def __init__(self):
        self._txns = {}
        self._delegations = {}
        self._next = 1000

    def txn(self, id):
        return self._txns[id]

    def txns_for(self, period):
        return [t for t in self._txns.values() if t.period == period]

    def save_txn(self, txn):
        self._txns[txn.id] = txn

    def delegation(self, id):
        return self._delegations[id]

    def delegations_from(self, badge):
        return [d for d in self._delegations.values() if d.delegator == badge]

    def save_delegation(self, d):
        self._delegations[d.id] = d

    def next_id(self):
        self._next += 1
        return f"rid{self._next}"

    # unused registry methods (not needed by trip tests) intentionally omitted


class FakeLedger:
    def __init__(self):
        self.payments = []

    def pay(self, badge, amount, key):
        ref = f"ref-{key}"
        self.payments.append((badge, amount, key))
        return ref
