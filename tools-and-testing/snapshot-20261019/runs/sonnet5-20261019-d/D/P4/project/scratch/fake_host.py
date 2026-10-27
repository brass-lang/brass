"""A minimal in-memory Store/Registry/Ledger for exercising trip_desk.py by hand. Test-only, not part of the package."""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.errors import Failure, FailureCode
from desk.records import CardTxn, Delegation


class FakeStore:
    def __init__(self):
        self.staffs = {}
        self.departments = {}
        self.reports = {}
        self.advances = {}
        self.trips = {}
        self.closed_periods = set()
        self.audit = []
        self._id = 0
        self.delegations = {}
        self.txns = {}

    # --- ids ---
    def next_id(self):
        self._id += 1
        return str(self._id)

    # --- staff/department ---
    def add_staff(self, s):
        self.staffs[s.badge] = s

    def add_department(self, d):
        self.departments[d.id] = d

    def staff(self, badge):
        if badge not in self.staffs:
            raise Failure(FailureCode.NOT_FOUND, "no such staff")
        return self.staffs[badge]

    def department(self, id):
        if id not in self.departments:
            raise Failure(FailureCode.NOT_FOUND, "no such department")
        return self.departments[id]

    # --- reports ---
    def report(self, id):
        if id not in self.reports:
            raise Failure(FailureCode.NOT_FOUND, "no such report")
        return self.reports[id]

    def reports_for(self, department, period):
        return [r for r in self.reports.values() if r.department == department and r.period == period]

    def submitted_reports(self):
        return list(self.reports.values())

    def save_report(self, report):
        self.reports[report.id] = report

    # --- advances ---
    def advance(self, id):
        return self.advances[id]

    def advances_for(self, department, period):
        return [a for a in self.advances.values() if a.department == department and a.period == period]

    def paid_advances(self):
        return list(self.advances.values())

    def save_advance(self, advance):
        self.advances[advance.id] = advance

    # --- trips ---
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

    # --- period ---
    def period_closed(self, period):
        return period in self.closed_periods

    def close_period(self, period):
        self.closed_periods.add(period)

    # --- audit ---
    def append_audit(self, entry):
        self.audit.append(entry)


class FakeRegistry:
    def __init__(self, store: FakeStore):
        self.store = store
        self.delegations = {}

    def save_delegation(self, d):
        self.delegations[d.id] = d

    def delegation(self, id):
        return self.delegations[id]

    def delegations_from(self, badge):
        return [d for d in self.delegations.values() if d.delegator == badge]

    def save_txn(self, t):
        self.store.txns[t.id] = t

    def txn(self, id):
        return self.store.txns[id]

    def txns_for(self, period):
        return [t for t in self.store.txns.values() if t.period == period]

    # Unused by our trip tests; present for Protocol completeness.
    def vendor(self, id): raise NotImplementedError
    def po(self, id): raise NotImplementedError
    def pos_for(self, department, period): return []
    def cost_center(self, id): raise NotImplementedError
    def departments_of(self, cost_center): return []
    def entity(self, id): raise NotImplementedError
    def allowance(self, department, period): return 0
    def pos_of_vendor(self, vendor): return []
    def card_limit(self, badge): raise Failure(FailureCode.NOT_FOUND, "none set")
    def departments(self): return list(self.store.departments.keys())
    def exception(self, id): raise NotImplementedError
    def exceptions_for(self, report): return []
    def save_po(self, po): raise NotImplementedError
    def save_vendor(self, v): raise NotImplementedError
    def save_card_limit(self, l): raise NotImplementedError
    def save_exception(self, e): raise NotImplementedError


class FakeLedger:
    def __init__(self):
        self.payments = []

    def pay(self, badge, amount, key):
        self.payments.append((badge, amount, key))
        return f"REF-{key}"
