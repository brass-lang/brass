"""Filing, amending, approving, reconciling, and closing trip plans. Approval follows a report's routing and budget rules; its required approver may act through a delegation."""
from typing import Optional

from . import lines, routing, trips
from .audit import Entry, Subject
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Period, ReportId, Role, TripId
from .lines import budgeted_total
from .records import CardStatus, Region, Vehicle, in_force
from .registry import Registry
from .reports import ReportStatus, counts_as_spend as report_counts_as_spend
from .review import may_act, required_for, within_budget
from .staff import Staff
from .trips import Plan, Reconciliation, Trip, TripStatus


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> TripId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not trips.plan_valid(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip needs at least one of per diem days or kilometres")
    open_statuses = (TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.RECONCILED)
    if any(t.badge == badge and t.status in open_statuses for t in store.trips_for(who.department, period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    committed = trips.price(region, days, vehicle, km)
    id = store.next_id()
    store.save_trip(Trip(id, badge, who.department, period, Plan(region, days, vehicle, km), committed))
    return id


def amend_trip(store: Store, trip_id: TripId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    who = active_staff(store, badge)
    t = store.trip(trip_id)
    if t.badge != who.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed this trip may amend it")
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not open for amendment")
    if not trips.plan_valid(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip needs at least one of per diem days or kilometres")
    committed = trips.price(region, days, vehicle, km)
    before = t.status
    updated = trips.amend(t, Plan(region, days, vehicle, km), committed)
    store.save_trip(updated)
    if before is TripStatus.APPROVED:
        store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended"))
    return updated.status


def approve_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> TripStatus:
    t = store.trip(trip_id)
    who, delegated_for = _gate(store, reg, t, approver, today)
    if len(t.approvals) + 1 >= routing.steps_for(t.committed):
        return _final_approval(store, t, who, delegated_for, today)
    store.save_trip(trips.add_approval(t, who.badge))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED,
                             _reason("approved; awaiting the next approver", delegated_for, today)))
    return TripStatus.REQUESTED


def reconcile_trip(store: Store, reg: Registry, trip_id: TripId, report_id: ReportId, finance_badge: Badge) -> int:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved or reconciled")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is not the staff member's for this period")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not approved or paid")
    txns = [x for x in reg.txns_for(t.period) if x.badge == t.badge and x.status is not CardStatus.MATCHED]
    actual = lines.total(r.lines) + sum(x.amount for x in txns)
    recon = Reconciliation(t.committed, actual, report_id, tuple(x.id for x in txns))
    before = t.status
    unchanged = t.reconciliation == recon
    store.save_trip(trips.reconcile(t, recon))
    if before is TripStatus.APPROVED or not unchanged:
        reason = "reconciled; actual exceeds committed" if actual > t.committed else "reconciled"
        store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: TripId, finance_badge: Badge, reason: str) -> None:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not open to close")
    before = t.status
    store.save_trip(trips.close(t))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.CLOSED, reason))


def _covered(store: Store, t: Trip) -> int:
    return sum(budgeted_total(r.lines) for r in store.reports_for(t.department, t.period)
              if r.badge == t.badge and report_counts_as_spend(r))


def _gate(store: Store, reg: Registry, t: Trip, approver: Badge, today: Period) -> tuple[Staff, Optional[Badge]]:
    who = active_staff(store, approver)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by the staff member who filed it")
    if may_act(store, t, who):
        return who, None
    required = required_for(store, t)
    if required is not None and any(d.delegate == who.badge for d in reg.delegations_from(required) if in_force(d, today)):
        return who, required
    raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")


def _final_approval(store: Store, t: Trip, who: Staff, delegated_for: Optional[Badge], today: Period) -> TripStatus:
    amount = max(0, t.committed - _covered(store, t))
    within = within_budget(store, t.department, t.period, amount)
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(trips.approve(t))
    reason = "approved" if within else "approved; budget override"
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED, _reason(reason, delegated_for, today)))
    return TripStatus.APPROVED


def _reason(base: str, delegated_for: Optional[Badge], today: Period) -> str:
    if delegated_for is None:
        return base
    return f"{base}; on behalf of {delegated_for} for period {today}"
