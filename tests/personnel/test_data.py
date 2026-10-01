import sqlite3

import pytest

from domains.personnel.seed import seed_personnel_if_empty


def test_demo_staff_loads_once(conn):
    seed_personnel_if_empty(conn)
    seed_personnel_if_empty(conn)
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 10


def test_every_clocked_employee_exists(conn):
    from ingestion.seed import generate_demo_data

    generate_demo_data(conn)
    seed_personnel_if_empty(conn)
    unknown = conn.execute(
        "SELECT COUNT(*) FROM clock_ins WHERE employee_id NOT IN (SELECT id FROM employees)"
    ).fetchone()[0]
    assert unknown == 0


def test_hourly_rate_must_be_positive(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO roles (name, hourly_rate, covers_per_hour, min_staff) VALUES ('Host', 0, 10, 1)")


def test_employee_needs_an_existing_role(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (name, role_id) VALUES ('Nobody', 99)")