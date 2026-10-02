import pytest

from domains.personnel.services import calculate_payroll, hours_worked, labor_cost, payroll_by_role
from domains.personnel.seed import seed_personnel_if_empty


def shift(employee_id, start, end, role="Waiter", rate=10.0, name=None):
    return {"employee_id": employee_id, "employee": name or f"Employee {employee_id}", "role": role,
            "hourly_rate": rate, "clock_in": start, "clock_out": end}


def test_hours_worked_handles_minutes_and_midnight():
    assert hours_worked("2026-09-04T12:00:00", "2026-09-04T16:30:00") == 4.5
    assert hours_worked("2026-09-04T19:00:00", "2026-09-05T00:15:00") == 5.25


def test_clock_out_before_clock_in_counts_as_zero():
    assert hours_worked("2026-09-04T16:00:00", "2026-09-04T12:00:00") == 0


def test_pay_is_clocked_hours_times_role_rate():
    payroll = calculate_payroll([
        shift(1, "2026-09-04T12:00:00", "2026-09-04T16:00:00", rate=11.5),   # 4 h
        shift(1, "2026-09-05T12:00:00", "2026-09-05T17:00:00", rate=11.5),   # 5 h
    ])
    assert len(payroll) == 1
    assert payroll[0]["shifts"] == 2
    assert payroll[0]["hours"] == 9
    assert payroll[0]["pay"] == 103.5                                        # 9 h * 11.50


def test_extra_hours_are_paid_at_the_same_rate():
    # No overtime premium: 50 hours in a week are paid exactly like 50 normal hours
    shifts = [shift(1, f"2026-09-0{d}T10:00:00", f"2026-09-0{d}T20:00:00") for d in range(1, 6)]
    assert calculate_payroll(shifts)[0]["pay"] == 500


def test_payroll_groups_by_role():
    payroll = calculate_payroll([
        shift(1, "2026-09-04T12:00:00", "2026-09-04T16:00:00", role="Waiter", rate=10),
        shift(2, "2026-09-04T12:00:00", "2026-09-04T14:00:00", role="Waiter", rate=10),
        shift(3, "2026-09-04T12:00:00", "2026-09-04T16:00:00", role="Cook", rate=15),
    ])
    roles = {r["role"]: r for r in payroll_by_role(payroll)}
    assert roles["Waiter"]["people"] == 2
    assert roles["Waiter"]["pay"] == 60
    assert roles["Cook"]["pay"] == 60


def test_labor_cost_only_counts_the_period(conn):
    seed_personnel_if_empty(conn)   # employee 1 is a waiter at 11.50 per hour
    conn.execute("INSERT INTO clock_ins (employee_id, clock_in, clock_out) VALUES (1, '2026-09-01T12:00:00', '2026-09-01T16:00:00')")
    conn.execute("INSERT INTO clock_ins (employee_id, clock_in, clock_out) VALUES (1, '2026-10-01T12:00:00', '2026-10-01T16:00:00')")
    assert labor_cost(conn, "2026-09-01", "2026-09-30") == 46.0          # only September: 4 h * 11.50
    assert labor_cost(conn, "2026-11-01", "2026-11-30") == 0


def test_clock_in_period(conn):
    from domains.personnel.repository import get_clock_in_period

    conn.execute("INSERT INTO clock_ins (employee_id, clock_in, clock_out) VALUES (1, '2026-09-03T12:00:00', '2026-09-03T16:00:00')")
    conn.execute("INSERT INTO clock_ins (employee_id, clock_in, clock_out) VALUES (1, '2026-09-20T12:00:00', '2026-09-20T16:00:00')")
    assert get_clock_in_period(conn) == ("2026-09-03", "2026-09-20")