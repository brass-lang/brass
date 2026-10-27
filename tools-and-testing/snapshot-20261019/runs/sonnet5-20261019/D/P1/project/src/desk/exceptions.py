"""Policy exceptions: a submitter asks for one line to be excused; the department's director decides. A decision is recorded only; line validation is unchanged."""
from . import records, reports
from .checks import active_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import Badge, ReportId
from .records import ExceptionId, ExceptionStatus, PolicyException, text_ok
from .registry import Registry


def request_exception(store: Store, reg: Registry, report_id: ReportId, badge: Badge, position: int, reason: str) -> ExceptionId:
    active_staff(store, badge)
    r = store.report(report_id)
    if r.badge != badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the submitter may ask for an exception")
    if not reports.editable(r):
        raise Failure(FailureCode.CONFLICT, "the report is not editable")
    if not 1 <= position <= len(r.lines):
        raise Failure(FailureCode.INVALID_INPUT, "no line at that position")
    if not text_ok(reason):
        raise Failure(FailureCode.INVALID_INPUT, "a reason is 1 to 200 characters")
    if any(e.status is ExceptionStatus.PENDING and e.position == position for e in reg.exceptions_for(r.id)):
        raise Failure(FailureCode.CONFLICT, "an exception for that line is already pending")
    id = store.next_id()
    reg.save_exception(PolicyException(id, r.id, position, badge, reason, ExceptionStatus.PENDING, None))
    return id


def decide_exception(store: Store, reg: Registry, exception_id: ExceptionId, director_badge: Badge, grant: bool) -> ExceptionStatus:
    active_staff(store, director_badge)
    e = reg.exception(exception_id)
    if e.status is not ExceptionStatus.PENDING:
        raise Failure(FailureCode.CONFLICT, "the exception is already decided")
    r = store.report(e.report)
    if store.department(r.department).director != director_badge:
        raise Failure(FailureCode.UNAUTHORIZED, "only the department's director may decide")
    status = ExceptionStatus.GRANTED if grant else ExceptionStatus.DENIED
    reg.save_exception(records.settle_exception(e, status, director_badge))
    return status
