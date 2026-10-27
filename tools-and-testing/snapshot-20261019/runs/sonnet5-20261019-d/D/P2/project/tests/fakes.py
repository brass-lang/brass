"""A minimal in-memory Store/Registry/Ledger for exercising entry points."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from desk.errors import Failure, FailureCode


class FakeStore:
    def __init__(self):
        self.staff_by_badge = {}
        self.departments = {}
        self.reports = {}
        self.advances = {}
        self.trips = {}
        self.closed_periods = set()
        self.audit = []
        self._next = 1

    def add_staff(self, s):
        self.staff_by_badge[s.badge] = s

    def add_department(self, d):
        self.departments[d.id] = d

    def staff(self, badge):
        if badge not in self.staff_by_badge:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self.staff_by_badge[badge]

    def report(self, id):
        if id not in self.reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self.reports[id]

    def department(self, id):
        if id not in self.departments:
            raise Failure(FailureCode.NOT_FOUND, "no such department")
        return self.departments[id]

    def reports_for(self, department, period):
        return [r for r in self.reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        return list(self.reports.values())

    def period_closed(self, period):
        return period in self.closed_periods

    def next_id(self):
        id = str(self._next)
        self._next += 1
        return id

    def save_report(self, report):
        self.reports[report.id] = report

    def append_audit(self, entry):
        self.audit.append(entry)

    def close_period(self, period):
        self.closed_periods.add(period)

    def advance(self, id):
        if id not in self.advances:
            raise Failure(FailureCode.NOT_FOUND, "no such advance")
        return self.advances[id]

    def advances_for(self, department, period):
        return [a for a in self.advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        return list(self.advances.values())

    def save_advance(self, advance):
        self.advances[advance.id] = advance

    def trip(self, id):
        if id not in self.trips:
            raise Failure(FailureCode.NOT_FOUND, "no such trip")
        return self.trips[id]

    def trips_for(self, department, period):
        return [t for t in self.trips.values() if t.department == department and t.period == period]

    def trips_in(self, period):
        return [t for t in self.trips.values() if t.period == period]

    def save_trip(self, trip):
        self.trips[trip.id] = trip


class FakeRegistry:
    def __init__(self):
        self.delegations = {}
        self.txns = {}
        self._next = 1000

    def delegations_from(self, badge):
        return [d for d in self.delegations.values() if d.delegator == badge]

    def delegation(self, id):
        return self.delegations[id]

    def save_delegation(self, d):
        self.delegations[d.id] = d

    def txn(self, id):
        return self.txns[id]

    def txns_for(self, period):
        return [t for t in self.txns.values() if t.period == period]

    def save_txn(self, t):
        self.txns[t.id] = t

    def next_delegation_id(self):
        id = str(self._next)
        self._next += 1
        return id


class FakeLedger:
    def pay(self, badge, amount, key):
        return f"ref-{key}"
