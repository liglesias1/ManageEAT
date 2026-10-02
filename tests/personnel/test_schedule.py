import pytest

from domains.personnel.services import (
    average_demand,
    average_staff_on_shift,
    build_schedule,
    staff_needed,
)

WAITER = {"id": 1, "name": "Waiter", "covers_per_hour": 12, "min_staff": 1}
BAR = {"id": 3, "name": "Bar", "covers_per_hour": 25, "min_staff": 1}

# 2026-09-04 and 2026-09-11 are Fridays (weekday 4)
FRIDAYS = ["2026-09-04", "2026-09-11"]


def test_staff_needed_rounds_up():
    assert staff_needed(40, WAITER) == 4      # 40 / 12 = 3.3 -> 4
    assert staff_needed(36, WAITER) == 3      # exactly 3


def test_staff_needed_never_below_minimum():
    assert staff_needed(0, WAITER) == 1
    assert staff_needed(3, BAR) == 1


def test_demand_is_averaged_over_the_same_weekday():
    covers = [
        {"day": "2026-09-04", "hour": 21, "covers": 40},
        {"day": "2026-09-11", "hour": 21, "covers": 60},
    ]
    assert average_demand(covers, FRIDAYS) == {(4, 21): 50}


def test_a_weekday_with_no_orders_at_that_hour_lowers_the_average():
    covers = [{"day": "2026-09-04", "hour": 13, "covers": 10}]
    assert average_demand(covers, FRIDAYS) == {(4, 13): 5}


def test_shift_counts_for_every_hour_it_touches():
    shifts = [{"clock_in": "2026-09-04T19:05:00", "clock_out": "2026-09-05T00:10:00", "role_id": 1}]
    staff = average_staff_on_shift(shifts, ["2026-09-04", "2026-09-05"])
    assert staff[(4, 19, 1)] == 1
    assert staff[(4, 23, 1)] == 1
    assert staff[(5, 0, 1)] == 1             # past midnight it counts for Saturday
    assert (4, 18, 1) not in staff


def test_staff_is_averaged_over_the_same_weekday():
    shifts = [{"clock_in": "2026-09-04T20:00:00", "clock_out": "2026-09-04T23:00:00", "role_id": 1}]
    staff = average_staff_on_shift(shifts, FRIDAYS)  # worked one of the two Fridays
    assert staff[(4, 21, 1)] == pytest.approx(0.5)


def test_schedule_shows_missing_and_extra_staff():
    demand = {(4, 21): 50}
    staff = {(4, 21, 1): 3, (4, 21, 3): 2}
    slot = build_schedule(demand, staff, [WAITER, BAR])[0]
    waiter, bar = slot["roles"]
    assert slot["day_name"] == "Friday"
    assert (waiter["needed"], waiter["actual"], waiter["gap"]) == (5, 3, 2)     # 2 missing
    assert (bar["needed"], bar["actual"], bar["gap"]) == (2, 2, 0)


def test_role_with_nobody_on_shift_counts_as_zero():
    slot = build_schedule({(0, 13): 10}, {}, [WAITER])[0]
    assert slot["roles"][0]["actual"] == 0
    assert slot["roles"][0]["gap"] == 1