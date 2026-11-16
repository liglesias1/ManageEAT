"""The personnel tables and their demo data: roles, employees and clock-ins."""
import sqlite3

import pytest

from domain import repository
from domain.seed import seed_personnel_if_empty

R = 1   # the restaurant every test works with


def test_demo_staff_loads_once(conn):
    seed_personnel_if_empty(conn, R)
    seed_personnel_if_empty(conn, R)
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 16
    assert conn.execute("SELECT COUNT(*) FROM clock_ins").fetchone()[0] == 320   # 16 people, 28 days, 2 off a week


def test_every_clocked_employee_exists(conn):
    seed_personnel_if_empty(conn, R)
    unknown = conn.execute(
        "SELECT COUNT(*) FROM clock_ins WHERE employee_id NOT IN (SELECT id FROM employees)"
    ).fetchone()[0]
    assert unknown == 0


def test_the_demo_clock_ins_are_the_same_on_every_start(conn):
    seed_personnel_if_empty(conn, R)
    first = conn.execute("SELECT clock_in, clock_out FROM clock_ins ORDER BY id").fetchall()
    conn.execute("DELETE FROM clock_ins")
    conn.execute("DELETE FROM employees")
    conn.execute("DELETE FROM roles")
    seed_personnel_if_empty(conn, R)
    assert conn.execute("SELECT clock_in, clock_out FROM clock_ins ORDER BY id").fetchall() == first


def test_hourly_rate_must_be_positive(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO roles (restaurant_id, name, hourly_rate, covers_per_hour, min_staff) "
                     "VALUES (1, 'Host', 0, 10, 1)")


def test_employee_needs_an_existing_role(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (restaurant_id, name, role_id) VALUES (1, 'Nobody', 99)")


def test_repository_reads_roles_and_shifts(conn):
    seed_personnel_if_empty(conn, R)
    assert len(repository.get_roles(conn, R)) == 6
    assert len(repository.get_shifts(conn, R)) == 320
    assert repository.get_clock_in_period(conn, R) == ("2026-09-01", "2026-09-28")


def test_each_restaurant_only_sees_its_own_staff(conn):
    seed_personnel_if_empty(conn, R)
    assert repository.get_roles(conn, 2) == []
    assert repository.get_shifts(conn, 2) == []