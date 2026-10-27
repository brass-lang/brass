"""Filing, amending, approving, reconciling, and closing trip plans."""
from . import budget, lines, routing, trips
from .audit import Entry, Subject
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Period, Role, TripId
from .records import CardStatus, Region, Vehicle, in_force
from .registry import Registry
from .reports import ReportStatus
from .review import required_for
from .trips import Plan, Reconciliation, Trip, TripStatus

OPEN_TRIP = (TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.RECONCILED)


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> TripId:
    committed = trips.priced(region, days, vehicle, km)
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if any(t.badge == who.badge and t.status in OPEN_TRIP for t in store.trips_for(who.department, period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    id = store.next_id()
    store.save_trip(Trip(id, who.badge, who.department, period, Plan(region, days, vehicle, km), committed))
    return id


def amend_trip(store: Store, trip_id: TripId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    t = store.trip(trip_id)
    if badge != t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed the trip may amend it")
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is reconciled or closed")
    committed = trips.priced(region, days, vehicle, km)
    before = t.status
    updated = trips.amend(t, Plan(region, days, vehicle, km), committed)
    store.save_trip(updated)
    if before is TripStatus.APPROVED:
        store.append_audit(Entry(badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended"))
    return updated.status


def approve_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> TripStatus:
    who = active_staff(store, approver)
    t = store.trip(trip_id)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by the staff member who filed it")
    required = required_for(store, t)
    delegator = None
    if required is None:
        if who.role is not Role.FINANCE:
            raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
    elif who.badge != required:
        if not any(d.delegate == who.badge and in_force(d, today) for d in reg.delegations_from(required)):
            raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
        delegator = required
    if len(t.approvals) + 1 >= routing.steps_for(t.committed):
        return _final_approval(store, t, who, delegator, today)
    store.save_trip(trips.add_approval(t, who.badge))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED,
                             _reason("approved; awaiting the next approver", delegator, today)))
    return TripStatus.REQUESTED


def _final_approval(store: Store, t: Trip, who, delegator, today: Period) -> TripStatus:
    within = budget.department_commitment(store, t.department, t.period) + budget.trip_commitment(store, t) \
        <= store.department(t.department).budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(trips.approve(t))
    reason = "approved" if within else "approved; budget override"
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED,
                             _reason(reason, delegator, today)))
    return TripStatus.APPROVED


def _reason(base: str, delegator, today: Period) -> str:
    if delegator is None:
        return base
    return f"{base}; on behalf of {delegator} for period {today}"


def reconcile_trip(store: Store, reg: Registry, trip_id: TripId, report_id, finance_badge: Badge) -> int:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is not this staff member's report for the trip's period")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not approved or paid")
    txns = [x for x in reg.txns_for(t.period) if x.badge == t.badge and x.status in (CardStatus.OPEN, CardStatus.DISPUTED)]
    actual = lines.total(r.lines) + sum(x.amount for x in txns)
    recon = Reconciliation(t.committed, actual, r.id, tuple(x.id for x in txns))
    before = t.status
    prior = t.reconciliation
    store.save_trip(trips.reconcile(t, recon))
    if prior != recon:
        reason = "reconciled"
        if actual > t.committed:
            reason += "; the actual amount exceeds the committed amount"
        store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: TripId, finance_badge: Badge, reason: str) -> None:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not open")
    before = t.status
    store.save_trip(trips.close(t))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.CLOSED, reason))
