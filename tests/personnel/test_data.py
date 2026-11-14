import sqlite3

import pytest

from domains.personnel.seed import seed_personnel_if_empty

R = 1   # the restaurant every test works with


def test_demo_staff_loads_once(conn):
    seed_personnel_if_empty(conn, R)
    seed_personnel_if_empty(conn, R)
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 16


def test_every_clocked_employee_exists(conn):
    from ingestion.seed import generate_demo_data

    generate_demo_data(conn, R)
    seed_personnel_if_empty(conn, R)
    unknown = conn.execute(
        "SELECT COUNT(*) FROM clock_ins WHERE employee_id NOT IN (SELECT id FROM employees)"
    ).fetchone()[0]
    assert unknown == 0


def test_hourly_rate_must_be_positive(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO roles (restaurant_id, name, hourly_rate, covers_per_hour, min_staff) "
                     "VALUES (1, 'Host', 0, 10, 1)")


def test_employee_needs_an_existing_role(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (restaurant_id, name, role_id) VALUES (1, 'Nobody', 99)")


def test_repository_reads_demand_and_shifts(conn):
    from domains.personnel import repository
    from ingestion.seed import generate_demo_data

    generate_demo_data(conn, R)
    seed_personnel_if_empty(conn, R)
    assert len(repository.get_open_days(conn, R)) == 28
    assert len(repository.get_roles(conn, R)) == 6
    assert len(repository.get_shifts(conn, R)) == 320
    total_covers = sum(row["covers"] for row in repository.get_covers_by_hour(conn, R))
    assert total_covers == conn.execute("SELECT SUM(covers) FROM orders").fetchone()[0]