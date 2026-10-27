"""A minimal in-memory Store/Registry for exercising trip_desk.py and friends."""
import sys
sys.path.insert(0, "/private/tmp/rerun-sonnet5-20261019-d/D/P3/project/src")

from desk.errors import Failure, FailureCode
from desk.records import CardTxn, Delegation


class FakeStore:
    def __init__(self):
        self._staff = {}
        self._departments = {}
        self._reports = {}
        self._advances = {}
        self._trips = {}
        self._closed_periods = set()
        self._audit = []
        self._next = 1000

    # staff / departments
    def add_staff(self, s):
        self._staff[s.badge] = s

    def add_department(self, d):
        self._departments[d.id] = d

    def staff(self, badge):
        if badge not in self._staff:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self._staff[badge]

    def department(self, id):
        if id not in self._departments:
            raise Failure(FailureCode.NOT_FOUND, "no such department")
        return self._departments[id]

    # reports
    def report(self, id):
        if id not in self._reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self._reports[id]

    def reports_for(self, department, period):
        return [r for r in self._reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        return list(self._reports.values())

    def save_report(self, report):
        self._reports[report.id] = report

    # advances
    def advance(self, id):
        if id not in self._advances:
            raise Failure(FailureCode.NOT_FOUND, "no such advance")
        return self._advances[id]

    def advances_for(self, department, period):
        return [a for a in self._advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        return list(self._advances.values())

    def save_advance(self, advance):
        self._advances[advance.id] = advance

    # trips
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

    # periods / ids / audit
    def period_closed(self, period):
        return period in self._closed_periods

    def close_period(self, period):
        self._closed_periods.add(period)

    def next_id(self):
        self._next += 1
        return str(self._next)

    def append_audit(self, entry):
        self._audit.append(entry)


class FailingAuditStore(FakeStore):
    """A store whose append_audit fails on demand, to test write-ordering."""
    def __init__(self):
        super().__init__()
        self.fail_audit_next = False

    def append_audit(self, entry):
        if self.fail_audit_next:
            self.fail_audit_next = False
            raise Failure(FailureCode.UNAVAILABLE, "audit sink is down")
        super().append_audit(entry)


class FakeRegistry:
    def __init__(self):
        self._txns = {}
        self._delegations = {}
        self._next = 5000

    def add_txn(self, t):
        self._txns[t.id] = t

    def txn(self, id):
        return self._txns[id]

    def txns_for(self, period):
        return [t for t in self._txns.values() if t.period == period]

    def save_txn(self, t):
        self._txns[t.id] = t

    def delegation(self, id):
        return self._delegations[id]

    def delegations_from(self, badge):
        return [d for d in self._delegations.values() if d.delegator == badge]

    def save_delegation(self, d):
        self._delegations[d.id] = d

    def next_txn_id(self):
        self._next += 1
        return str(self._next)
