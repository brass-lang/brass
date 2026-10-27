"""Filing, amending, approving, reconciling, and closing trip plans. A trip commits against the budget like a report would."""
from . import budget, review, routing, trips
from .allowances import MAX_DAYS, MAX_KM
from .audit import Entry, Subject
from .checks import active_staff, finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, Money, Period, ReportId, Role
from .lines import total as line_total
from .records import CardStatus, MILEAGE, PER_DIEM, Region, Vehicle, in_force
from .registry import Registry
from .reports import ReportStatus
from .staff import Staff
from .trips import Plan, Reconciliation, Trip, TripId, TripStatus


def _price(region: Region, days: int, vehicle: Vehicle, km: int) -> Money:
    return PER_DIEM[region] * days + MILEAGE[vehicle] * km


def _valid_plan(days: int, km: int) -> bool:
    return 0 <= days <= MAX_DAYS and 0 <= km <= MAX_KM and (days > 0 or km > 0)


def file_trip(store: Store, badge: Badge, period: Period, region: Region, days: int, vehicle: Vehicle, km: int) -> TripId:
    who = active_staff(store, badge)
    if store.period_closed(period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if not _valid_plan(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan claims 0 to 30 per diem days and 0 to 2,000 km, and at least one of them")
    if any(t.badge == badge and t.status in (TripStatus.REQUESTED, TripStatus.APPROVED, TripStatus.RECONCILED)
           for t in store.trips_in(period)):
        raise Failure(FailureCode.CONFLICT, "the staff member already has an open trip for this period")
    committed = _price(region, days, vehicle, km)
    id = store.next_id()
    store.save_trip(Trip(id, badge, who.department, period, Plan(region, days, vehicle, km), committed, TripStatus.REQUESTED))
    return id


def amend_trip(store: Store, trip_id: TripId, badge: Badge, region: Region, days: int, vehicle: Vehicle, km: int) -> TripStatus:
    t = store.trip(trip_id)
    if t.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the staff member who filed the trip may amend it")
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be amended")
    if not _valid_plan(days, km):
        raise Failure(FailureCode.INVALID_INPUT, "a trip plan claims 0 to 30 per diem days and 0 to 2,000 km, and at least one of them")
    committed = _price(region, days, vehicle, km)
    before = t.status
    store.save_trip(trips.amend(t, Plan(region, days, vehicle, km), committed))
    if before is TripStatus.APPROVED:
        store.append_audit(Entry(badge, Subject.TRIP, t.id, TripStatus.APPROVED, TripStatus.REQUESTED, "amended"))
    return TripStatus.REQUESTED


def _delegated_reason(base: str, delegated_from: Badge | None, today: Period) -> str:
    if delegated_from is None:
        return base
    return f"{base}; on behalf of {delegated_from} for period {today}"


def _trip_approver_ok(store: Store, reg: Registry, t: Trip, who: Staff, today: Period) -> tuple[bool, Badge | None]:
    nominal = review.nominal_approver(store, t)
    if nominal is None:
        return who.role is Role.FINANCE, None
    if any(d.delegate == who.badge and in_force(d, today) for d in reg.delegations_from(nominal)):
        return True, nominal
    return who.badge == review.stand_in(store, nominal), None


def _gate_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> tuple[Trip, Staff, Badge | None]:
    who = store.staff(approver)
    if not who.active:
        raise Failure(FailureCode.UNAUTHORIZED, "staff member is not active")
    t = store.trip(trip_id)
    if t.status is not TripStatus.REQUESTED:
        raise Failure(FailureCode.CONFLICT, "the trip is not awaiting approval")
    if store.period_closed(t.period):
        raise Failure(FailureCode.CONFLICT, "the period is closed")
    if who.badge == t.badge:
        raise Failure(FailureCode.UNAUTHORIZED, "a trip cannot be approved by the staff member who filed it")
    ok, delegated_from = _trip_approver_ok(store, reg, t, who, today)
    if not ok:
        raise Failure(FailureCode.UNAUTHORIZED, "not this trip's next approver")
    return t, who, delegated_from


def approve_trip(store: Store, reg: Registry, trip_id: TripId, approver: Badge, today: Period) -> TripStatus:
    t, who, delegated_from = _gate_trip(store, reg, trip_id, approver, today)
    if len(t.approvals) + 1 >= routing.steps_for(t.committed):
        return _final_trip_approval(store, t, who, delegated_from, today)
    store.save_trip(trips.add_approval(t, who.badge))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.REQUESTED,
                              _delegated_reason("approved; awaiting the next approver", delegated_from, today)))
    return TripStatus.REQUESTED


def _final_trip_approval(store: Store, t: Trip, who: Staff, delegated_from: Badge | None, today: Period) -> TripStatus:
    amount = budget.trip_remaining_if_approved(store, t)
    within = review.within_budget(store, t.department, t.period, amount)
    if not within and who.role is not Role.FINANCE:
        raise Failure(FailureCode.CONFLICT, "the department budget for this period would be exceeded")
    store.save_trip(trips.approve(t))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, TripStatus.REQUESTED, TripStatus.APPROVED,
                              _delegated_reason("approved" if within else "approved; budget override", delegated_from, today)))
    return TripStatus.APPROVED


def reconcile_trip(store: Store, reg: Registry, trip_id: TripId, report_id: ReportId, finance_badge: Badge) -> Money:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.APPROVED, TripStatus.RECONCILED):
        raise Failure(FailureCode.CONFLICT, "the trip is not approved")
    r = store.report(report_id)
    if r.badge != t.badge or r.period != t.period:
        raise Failure(FailureCode.CONFLICT, "the report is not the staff member's for this period")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PAID):
        raise Failure(FailureCode.CONFLICT, "the report is not approved or paid")
    unmatched = [tx for tx in reg.txns_for(t.period) if tx.badge == t.badge and tx.status is not CardStatus.MATCHED]
    actual = line_total(r.lines) + sum(tx.amount for tx in unmatched)
    recon = Reconciliation(t.committed, actual, r.id, tuple(tx.id for tx in unmatched))
    changed = t.reconciliation != recon
    before = t.status
    store.save_trip(trips.reconcile(t, recon))
    if changed:
        reason = "reconciled"
        if actual > t.committed:
            reason += "; the actual amount exceeds the committed amount"
        store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.RECONCILED, reason))
    return actual


def close_trip(store: Store, trip_id: TripId, finance_badge: Badge, reason: str) -> None:
    who = finance_staff(store, finance_badge)
    t = store.trip(trip_id)
    if t.status not in (TripStatus.REQUESTED, TripStatus.APPROVED):
        raise Failure(FailureCode.CONFLICT, "the trip cannot be closed")
    before = t.status
    store.save_trip(trips.close(t))
    store.append_audit(Entry(who.badge, Subject.TRIP, t.id, before, TripStatus.CLOSED, reason))
