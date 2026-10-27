"""Filing, approving, amending, reconciling, and closing trip plans. Approval follows a report's routing and
budget rules, with delegation added: a supervisor or director's required approval may be given instead by
someone holding their delegation, in force for today, the period in which the approval happens."""
from typing import Optional

from . import lines, routing, trips
from .audit import Entry, Subject
from .budget import department_spend, staff_budgeted_total
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Money, Period, ReportId, Role, TripId
from .records import CardStatus, Region, Vehicle, in_force, text_ok
from .registry import Registry
from .reports import ReportStatus
from .review import required_for
from .staff import Staff
from .trips import Plan, Reconciliation, Trip, TripStatus


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> TripId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not trips.plan_valid(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan covers 0 to 30 per diem days and 0 to 2,000 km, with at least one positive")
    blocking = (TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.RECONCILED)
    if any(t.badge == badge and t.status in blocking for t in store.trips_for(who.department, period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    plan = Plan(region, days, vehicle, km)
    id = store.next_id()
    store.save_trip(Trip(id, badge, who.department, period, plan, trips.price(plan), TripStatus.REQUESTED, ()))
    return id


def amend_trip(store: Store, trip_id: TripId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    t = store.trip(trip_id)
    if t.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed the trip may amend it")
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not requested or approved")
    if not trips.plan_valid(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan covers 0 to 30 per diem days and 0 to 2,000 km, with at least one positive")
    plan = Plan(region, days, vehicle, km)
    before = t.status
    store.save_trip(trips.amend(t, plan, trips.price(plan)))
    if before is TripStatus.APPROVED:
        store.append_audit(Entry(badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended"))
    return TripStatus.REQUESTED


def approve_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> TripStatus:
    who = active_staff(store, approver)
    t = store.trip(trip_id)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by its filer")
    delegator = _accepted(store, reg, t, who, today)

    if len(t.approvals) + 1 >= routing.steps_for(t.committed):
        return _final_trip_approval(store, t, who, delegator, today)
    store.save_trip(trips.add_approval(t, who.badge))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED,
                             _reason("approved; awaiting the next approver", delegator, today)))
    return TripStatus.REQUESTED


def reconcile_trip(store: Store, reg: Registry, trip_id: TripId, report_id: ReportId, finance_badge: Badge) -> Money:
    finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved or reconciled")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is not by the trip's staff member for its period")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not approved or paid")

    unmatched = [x for x in reg.txns_for(t.period) if x.badge == t.badge and x.status is not CardStatus.MATCHED]
    actual = lines.total(r.lines) + sum(x.amount for x in unmatched)
    recon = Reconciliation(t.committed, actual, r.id, tuple(x.id for x in unmatched))

    before = t.status
    changed = t.reconciliation != recon
    store.save_trip(trips.reconcile(t, recon))
    if before is not TripStatus.RECONCILED or changed:
        reason = "reconciled" if actual <= t.committed else "reconciled; the actual amount exceeds the committed amount"
        store.append_audit(Entry(finance_badge, Subject.TRIP, t.id, before, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: TripId, finance_badge: Badge, reason: str) -> None:
    finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip is not requested or approved")
    if not text_ok(reason):
        raise Failure(FailureCode.INVALID_INPUT, "a reason is 1 to 200 characters")
    before = t.status
    store.save_trip(trips.close(t))
    store.append_audit(Entry(finance_badge, Subject.TRIP, t.id, before, TripStatus.CLOSED, reason))


def _accepted(store: Store, reg: Registry, t: Trip, who: Staff, today: Period) -> Optional[Badge]:
    """Is `who` accepted for the trip's next approval step? Returns the delegator's badge when `who`
    acted under a delegation, else None. Raises Unauthorized when `who` is not accepted."""
    required = required_for(store, t)
    if required is None:
        if who.role is not Role.FINANCE:
            raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
        return None
    if who.badge == required:
        return None
    if any(d.delegate == who.badge and in_force(d, today) for d in reg.delegations_from(required)):
        return required
    raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")


def _reason(base: str, delegator: Optional[Badge], today: Period) -> str:
    if delegator is None:
        return base
    return f"{base}; on behalf of {delegator} under a delegation in force for period {today}"


def _final_trip_approval(store: Store, t: Trip, who: Staff, delegator: Optional[Badge], today: Period) -> TripStatus:
    amount = trip_counted_once_approved(store, t)
    within = department_spend(store, t.department, t.period) + amount <= store.department(t.department).budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(trips.approve(t))
    base = "approved" if within else "approved; budget override"
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED,
                             _reason(base, delegator, today)))
    return TripStatus.APPROVED


def trip_counted_once_approved(store: Store, t: Trip) -> int:
    covered = staff_budgeted_total(store.reports_for(t.department, t.period), t.badge)
    return max(0, t.committed - covered)
