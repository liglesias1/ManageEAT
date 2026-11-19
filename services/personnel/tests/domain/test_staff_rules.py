"""The staff rules without a database: field checks in schemas.py and business rules in services.py."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from domain import services
from domain.schemas import ClockInIn, EmployeeIn, RoleIn

TODAY = date(2026, 11, 19)


def entry(clock_in="2026-09-10T12:00:00", clock_out="2026-09-10T16:00:00", employee_id=1):
    return ClockInIn(employee_id=employee_id, clock_in=clock_in, clock_out=clock_out)


# ---------- Field checks ----------

def test_a_role_name_is_trimmed():
    assert RoleIn(name="  Sommelier ", hourly_rate=15, covers_per_hour=40, min_staff=0).name == "Sommelier"


@pytest.mark.parametrize("change", [
    {"name": "X"}, {"hourly_rate": 0}, {"hourly_rate": 500}, {"covers_per_hour": 0}, {"min_staff": -1},
])
def test_a_role_with_a_wrong_field_is_rejected(change):
    with pytest.raises(ValidationError):
        RoleIn(**{"name": "Sommelier", "hourly_rate": 15, "covers_per_hour": 40, "min_staff": 0, **change})


def test_an_employee_needs_a_real_name():
    with pytest.raises(ValidationError):
        EmployeeIn(name=" A ", role_id=1)


def test_a_shift_must_end_after_it_starts():
    with pytest.raises(ValidationError, match="after the clock-in"):
        entry(clock_out="2026-09-10T12:00:00")


def test_a_shift_cannot_last_more_than_16_hours():
    with pytest.raises(ValidationError, match="16 hours"):
        entry(clock_out="2026-09-11T05:00:00")


def test_a_shift_across_midnight_is_fine():
    late = entry(clock_in="2026-09-10T19:00:00", clock_out="2026-09-11T00:30:00")
    assert late.clock_out == datetime(2026, 9, 11, 0, 30)


def test_a_time_with_a_time_zone_is_rejected():
    with pytest.raises(ValidationError, match="local time"):
        entry(clock_in="2026-09-10T12:00:00Z")


# ---------- Business rules ----------

def test_a_role_name_cannot_repeat_whatever_the_case():
    role = RoleIn(name="waiter", hourly_rate=15, covers_per_hour=40, min_staff=0)
    assert services.role_problem(role, ["Waiter", "Cook"]) == "Name: there is already a role with that name"
    assert services.role_problem(role, ["Cook"]) is None


def test_an_employee_needs_a_role_of_their_restaurant():
    assert services.employee_problem(EmployeeIn(name="Ana", role_id=9), {1, 2}) == "Role: choose one of the roles"
    assert services.employee_problem(EmployeeIn(name="Ana", role_id=2), {1, 2}) is None


def test_a_clock_in_needs_an_employee_of_the_restaurant():
    assert services.clock_in_problem(entry(employee_id=99), {1, 2}, False, TODAY) == \
        "Employee: choose one of the employees"


def test_a_clock_in_cannot_be_on_a_future_day():
    future = entry(clock_in="2026-11-20T12:00:00", clock_out="2026-11-20T16:00:00")
    assert services.clock_in_problem(future, {1}, False, TODAY) == "A clock-in cannot be on a future day"
    earlier_today = entry(clock_in="2026-11-19T08:00:00", clock_out="2026-11-19T12:00:00")
    assert services.clock_in_problem(earlier_today, {1}, False, TODAY) is None


def test_a_clock_in_cannot_overlap_another():
    assert services.clock_in_problem(entry(), {1}, True, TODAY) == \
        "This employee already has a clock-in that overlaps these hours"
    assert services.clock_in_problem(entry(), {1}, False, TODAY) is None