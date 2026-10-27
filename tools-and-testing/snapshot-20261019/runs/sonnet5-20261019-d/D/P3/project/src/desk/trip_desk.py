"""Filing, approving, amending, reconciling, and closing trip plans. A trip commits its cost against the department's
budget while Approved; reconciling it afterwards is a record for review and changes no budget."""
from typing import Optional

from . import budget, lines, routing, trips
from .allowances import MAX_DAYS, MAX_KM
from .audit import Entry, Subject
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Period, Role, TripId
from .records import MILEAGE, PER_DIEM, CardStatus, Region, Vehicle, in_force
from .registry import Registry
from .reports import ReportId, ReportStatus
from .staff import Staff
from .trips import Plan, Reconciliation, Trip, TripStatus

OPEN_STATUSES = (TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.RECONCILED)


def _price(region: Region, days: int, vehicle: Vehicle, km: int) -> int:
    return PER_DIEM[region] * days + MILEAGE[vehicle] * km


def _valid_plan(days: int, km: int) -> bool:
    return 0 <= days <= MAX_DAYS and 0 <= km <= MAX_KM and (days > 0 or km > 0)


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> TripId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not _valid_plan(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan needs 0 to 30 per diem days and 0 to 2,000 km, and at least one positive")
    if any(t.badge == badge and t.status in OPEN_STATUSES for t in store.trips_in(period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    committed = _price(region, days, vehicle, km)
    id = store.next_id()
    store.save_trip(Trip(id, badge, who.department, period, Plan(region, days, vehicle, km), committed, TripStatus.REQUESTED))
    return id


def amend_trip(store: Store, trip_id: TripId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    t = store.trip(trip_id)
    if t.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed this trip may amend it")
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be amended")
    if not _valid_plan(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan needs 0 to 30 per diem days and 0 to 2,000 km, and at least one positive")
    committed = _price(region, days, vehicle, km)
    was_approved = t.status is TripStatus.APPROVED
    updated = trips.amend(t, Plan(region, days, vehicle, km), committed)
    store.save_trip(updated)
    if was_approved:
        store.append_audit(Entry(badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended"))
    return updated.status


def approve_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> TripStatus:
    t, who, delegated_for = _gate(store, reg, trip_id, approver, today)
    if len(t.approvals) + 1 >= routing.steps_for(t.committed):
        return _final_trip_approval(store, t, who, delegated_for, today)
    store.save_trip(trips.add_approval(t, who.badge))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED,
                             _reason("approved; awaiting the next approver", delegated_for, today)))
    return TripStatus.REQUESTED


def reconcile_trip(store: Store, reg: Registry, trip_id: TripId, report_id: ReportId, finance_badge: Badge) -> int:
    finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is not by the same staff member for the same period")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not approved or paid")
    unmatched = [tx for tx in reg.txns_for(t.period) if tx.badge == t.badge and tx.status is not CardStatus.MATCHED]
    actual = lines.total(r.lines) + sum(tx.amount for tx in unmatched)
    recon = Reconciliation(t.committed, actual, r.id, tuple(tx.id for tx in unmatched))
    previous = t.reconciliation
    before_status = t.status
    store.save_trip(trips.reconcile(t, recon))
    if previous != recon:
        reason = "reconciled" if actual <= t.committed else "reconciled; actual exceeds committed"
        store.append_audit(Entry(finance_badge, Subject.TRIP, t.id, before_status, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: TripId, finance_badge: Badge, reason: str) -> None:
    finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be closed")
    before = t.status
    store.save_trip(trips.close(t))
    store.append_audit(Entry(finance_badge, Subject.TRIP, t.id, before, TripStatus.CLOSED, reason))


def _final_trip_approval(store: Store, t: Trip, who: Staff, delegated_for: Optional[Badge], today: Period) -> TripStatus:
    dept_reports = store.reports_for(t.department, t.period)
    covered = budget.trip_coverage(t, dept_reports)
    trip_amount = max(0, t.committed - covered)
    spend = budget.department_spend(store, t.department, t.period)
    within = spend + trip_amount <= store.department(t.department).budget
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(trips.approve(t))
    reason = "approved" if within else "approved; budget override"
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED, _reason(reason, delegated_for, today)))
    return TripStatus.APPROVED


def _reason(base: str, delegated_for: Optional[Badge], today: Period) -> str:
    if delegated_for is None:
        return base
    return f"{base}; approved for {delegated_for} under a delegation in force for period {today}"


def _required_badge(store: Store, t: Trip) -> Optional[Badge]:
    """The badge required for the next step, or None when any active finance staff member will do."""
    role = routing.role_for(len(t.approvals) + 1)
    if role is Role.FINANCE:
        return None
    if role is Role.SUPERVISOR:
        submitter = store.staff(t.badge)
        if submitter.supervisor is None:
            raise Failure(FailureCode.CONFLICT, "the staff member has no supervisor")
        required = submitter.supervisor
    else:
        required = store.department(t.department).director
    person = store.staff(required)
    if person.active:
        return required
    if person.supervisor is not None and store.staff(person.supervisor).active:
        return person.supervisor
    raise Failure(FailureCode.CONFLICT, f"no active approver stands in for {required}")


def _gate(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> tuple[Trip, Staff, Optional[Badge]]:
    who = active_staff(store, approver)
    t = store.trip(trip_id)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by the staff member who filed it")
    required = _required_badge(store, t)
    if required is None:
        if who.role is not Role.FINANCE:
            raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
        return t, who, None
    if who.badge == required:
        return t, who, None
    delegation = next((d for d in reg.delegations_from(required) if d.delegate == who.badge and in_force(d, today)), None)
    if delegation is None:
        raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
    return t, who, required
