import sys
sys.path.insert(0, "/private/tmp/rerun-sonnet5-20261019-d/D/P3/project/src")
sys.path.insert(0, "/private/tmp/rerun-sonnet5-20261019-d/D/P3/project/scratch")

from fake_host import FakeStore

from desk.errors import Failure, FailureCode
from desk.ids import Category, Role
from desk.lines import Line
from desk.staff import Department, Staff
from desk.reports import ReportStatus
from desk.advances import AdvanceStatus
from desk import review, payment, advance_desk, queries

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


store = FakeStore()
store.add_department(Department("D1", "director1", 1_000_000))
store.add_staff(Staff("staff1", "S1", "D1", "sup1", Role.STAFF, True))
store.add_staff(Staff("sup1", "Sup1", "D1", "director1", Role.SUPERVISOR, True))
store.add_staff(Staff("director1", "Dir1", "D1", None, Role.DIRECTOR, True))
store.add_staff(Staff("finance1", "Fin1", "D1", None, Role.FINANCE, True))

rid = review.open_draft(store, "staff1", 1, Line(Category.TRAVEL, 10_000, "cab", True))
review.submit(store, rid, "staff1")
status = review.approve(store, rid, "sup1")
check("regression: single-step report approval still works", status is ReportStatus.APPROVED)
check("regression: spend without trips unaffected", queries.spend(store, "D1", 1) == 10_000)

aid = advance_desk.request_advance(store, "staff1", 1, 5_000)
astatus = advance_desk.approve_advance(store, aid, "sup1")
check("regression: advance approval still works", astatus is AdvanceStatus.APPROVED)
check("regression: spend includes advance", queries.spend(store, "D1", 1) == 15_000)

stmt = queries.statement(store, "D1", 1)
check("regression: statement rows: report + advance, no trip rows", len(stmt.rows) == 2)

payment.close_period(store, 1, "finance1")
check("regression: close_period still marks period closed", store.period_closed(1))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
