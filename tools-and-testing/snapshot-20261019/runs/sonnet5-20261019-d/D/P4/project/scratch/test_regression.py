import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fake_host import FakeStore, FakeRegistry, FakeLedger

from desk.staff import Staff, Department
from desk.ids import Role, Category
from desk.errors import Failure, FailureCode
from desk.reports import Report, ReportStatus
from desk.lines import Line
from desk import review, payment, queries, advance_desk

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def new_store(budget=1_000_000):
    s = FakeStore()
    s.add_department(Department("D1", "DIR1", budget))
    s.add_staff(Staff("STAFF1", "A", "D1", "SUP1", Role.STAFF, True))
    s.add_staff(Staff("SUP1", "B", "D1", "DIR1", Role.SUPERVISOR, True))
    s.add_staff(Staff("DIR1", "C", "D1", None, Role.DIRECTOR, True))
    s.add_staff(Staff("FIN1", "D", "D1", None, Role.FINANCE, True))
    return s


# plain report approval, no trips in the picture at all
s = new_store()
rid = review.open_draft(s, "STAFF1", 1, Line(Category.FEED, 1000, "food", False))
review.submit(s, rid, "STAFF1")
status = review.approve(s, rid, "SUP1")
check("report: approved without any trips", status is ReportStatus.APPROVED)
check("spend matches plain report total", queries.spend(s, "D1", 1) == 1000)

# advance approval unaffected
s2 = new_store()
aid = advance_desk.request_advance(s2, "STAFF1", 1, 2000)
status = advance_desk.approve_advance(s2, aid, "SUP1")
check("advance: approved", status.value == "Approved")

# pay + close_period with no trips at all (host trips_in must be called but return empty)
s3 = new_store()
rid = review.open_draft(s3, "STAFF1", 1, Line(Category.FEED, 500, "food", False))
review.submit(s3, rid, "STAFF1")
review.approve(s3, rid, "SUP1")
payment.close_period(s3, 1, "FIN1")
check("close_period with no trips works", s3.period_closed(1))

print(f"\n{PASS} passed, {FAIL} failed")
