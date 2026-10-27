"""Filing, amending, approving, reconciling, and closing trip plans."""
from . import lines, routing, trips
from .audit import Entry, Subject
from .budget import department_spend
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Money, Period, ReportId, Role
from .records import Region, Vehicle, in_force
from .registry import Registry
from .reports import ReportStatus
from .review import may_act, required_for
from .staff import is_finance
from .trips import Plan, Reconciliation, Trip, TripStatus


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> ReportId:
    plan = Plan(region, days, vehicle, km)
    committed = trips.priced(plan)
    who = store.staff(badge)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if any(t.badge == badge and t.status is not TripStatus.CLOSED for t in store.trips_for(who.department, period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    id = store.next_id()
    store.save_trip(Trip(id, badge, who.department, period, plan, committed, TripStatus.REQUESTED))
    return id


def amend_trip(store: Store, trip_id: ReportId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    plan = Plan(region, days, vehicle, km)
    committed = trips.priced(plan)
    t = store.trip(trip_id)
    if t.badge != badge or not store.staff(badge).active:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed the trip may amend it")
    if t.status not in trips.OPEN:
        raise Failure(FailureCode.CONFLICT, "the trip is reconciled or closed")
    amended = trips.amend(t, plan, committed)
    store.save_trip(amended)
    if t.status is TripStatus.APPROVED:
        store.append_audit(Entry(badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended; approvals cleared"))
    return amended.status


def approve_trip(store: Store, reg: Registry, trip_id: ReportId, approver: Badge, today: Period) -> TripStatus:
    who = store.staff(approver)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    t = store.trip(trip_id)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by its requester")
    on_behalf = None
    if not may_act(store, t, who):
        required = required_for(store, t)
        if required is None or not any(d.delegate == who.badge and in_force(d, today) for d in reg.delegations_from(required)):
            raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
        on_behalf = required
    behalf = f" on behalf of {on_behalf} in period {today}" if on_behalf else ""
    if len(t.approvals) + 1 < routing.steps_for(t.committed):
        store.save_trip(trips.add_approval(t, who.badge))
        store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED, "approved; awaiting the next approver" + behalf))
        return TripStatus.REQUESTED
    approved = trips.approve(t)                           # as for reports and advances: the final approver is the audit's who
    reports = store.reports_for(t.department, t.period)
    within = department_spend(store, t.department, t.period) + trips.counted(approved, reports) <= store.department(t.department).budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(approved)
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED,
                             ("approved" if within else "approved; budget override") + behalf))
    return TripStatus.APPROVED


def reconcile_trip(store: Store, reg: Registry, trip_id: ReportId, report_id: ReportId, finance_badge: Badge) -> Money:
    who = _finance(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period or r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not an approved or paid report of this trip's staff member and period")
    unmatched = [x for x in reg.txns_for(t.period) if x.badge == t.badge and x.matched is None]
    actual = lines.total(r.lines) + sum(x.amount for x in unmatched)
    rec = Reconciliation(t.committed, actual, r.id, tuple(x.id for x in unmatched))
    if t.status is TripStatus.RECONCILED and t.reconciliation == rec:
        store.save_trip(t)                                    # unchanged: the same value, no audit
        return actual
    before = t.status
    store.save_trip(trips.reconcile(t, rec))
    reason = "reconciled" if actual <= t.committed else f"reconciled; actual exceeds commitment by {actual - t.committed}"
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: ReportId, finance_badge: Badge, reason: str) -> None:
    who = _finance(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in trips.OPEN:
        raise Failure(FailureCode.CONFLICT, "the trip is reconciled or closed")
    store.save_trip(trips.close(t))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, t.status, TripStatus.CLOSED, reason))


def close_open_trips(store: Store, who: Badge, period: Period) -> None:
    """Close every open trip of `period`, each saved then audited. A retry skips the ones already closed."""
    for t in store.trips_in(period):
        if t.status in trips.OPEN:
            store.save_trip(trips.close(t))
            store.append_audit(Entry(who, Subject.TRIP, t.id, t.status, TripStatus.CLOSED, "period closed"))


def _finance(store: Store, badge: Badge):
    who = store.staff(badge)
    if not is_finance(who):
        raise Failure(FailureCode.UNAUTHORIZED, "only active finance staff may do this")
    return who
