import sys
sys.path.insert(0, "src")

from desk.ids import Role, Category
from desk.staff import Staff, Department
from desk.lines import Line
from desk.errors import Failure, FailureCode
from desk import review, advance_desk, queries
from test_trips import FakeStore


def mkstore():
    s = FakeStore()
    s.departments["D1"] = Department("D1", "director1", 1_000_000)
    s.staff_["staffer"] = Staff("staffer", "Staffer", "D1", "super1", Role.STAFF, True)
    s.staff_["super1"] = Staff("super1", "Super", "D1", "director1", Role.SUPERVISOR, True)
    s.staff_["director1"] = Staff("director1", "Director", "D1", None, Role.DIRECTOR, True)
    s.staff_["finance1"] = Staff("finance1", "Finance", "D1", None, Role.FINANCE, True)
    return s


def test_report_lifecycle_no_trip():
    s = mkstore()
    rid = review.open_draft(s, "staffer", 1, Line(Category.OTHER, 1_000, "x", False))
    review.submit(s, rid, "staffer")
    st = review.approve(s, rid, "super1")
    assert st.value == "Approved"
    assert queries.spend(s, "D1", 1) == 1_000
    stmt = queries.statement(s, "D1", 1)
    assert stmt.spend == 1_000
    assert stmt.remaining == 999_000
    print("test_report_lifecycle_no_trip OK")


def test_advance_lifecycle_no_trip():
    s = mkstore()
    aid = advance_desk.request_advance(s, "staffer", 1, 2_000)
    st = advance_desk.approve_advance(s, aid, "super1")
    assert st.value == "Approved"
    assert queries.spend(s, "D1", 1) == 2_000
    print("test_advance_lifecycle_no_trip OK")


if __name__ == "__main__":
    test_report_lifecycle_no_trip()
    test_advance_lifecycle_no_trip()
    print("ALL OK")
