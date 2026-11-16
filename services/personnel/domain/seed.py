"""Demo data for the personnel service: roles, employees, and the clock-ins the clock-in system would record.

The clock-in generator used to live in ingestion/seed.py next to the orders. Seed data moves with its
table, so it is now here, with its own random generator: the sales service generates the orders with
another one, and neither depends on the other to produce the same data on every start.
"""
import random
from datetime import date, datetime, timedelta

# id, name, hourly_rate (EUR), covers_per_hour (diners one person can handle in an hour), min_staff
ROLES = [
    (1, "Waiter", 11.50, 30, 1),
    (2, "Runner", 10.50, 40, 0),
    (3, "Bar", 12.00, 50, 1),
    (4, "Pass", 13.00, 60, 1),
    (5, "Cook", 14.00, 20, 1),
    (6, "Dishwasher", 10.00, 50, 1),
]

# id, name, role_id (ids match the employee ids used by the clock-in system)
EMPLOYEES = [
    (1, "Lucía Martín", 1),
    (2, "Javier Ruiz", 5),
    (3, "Carmen López", 1),
    (4, "Pablo Sánchez", 5),
    (5, "Elena Gómez", 3),
    (6, "Daniel Torres", 1),
    (7, "Marta Navarro", 5),
    (8, "Sergio Díaz", 3),
    (9, "Laura Romero", 1),
    (10, "Andrés Molina", 2),
    (11, "Irene Castro", 2),
    (12, "Hugo Ortega", 4),
    (13, "Nuria Vidal", 4),
    (14, "Raúl Herrera", 5),
    (15, "Sofía Delgado", 6),
    (16, "Mario Iglesias", 6),
]

# Which service each demo employee usually works
EMPLOYEE_SHIFTS = {
    1: "lunch", 2: "lunch", 3: "dinner", 4: "dinner", 5: "lunch", 6: "dinner",
    7: "lunch", 8: "dinner", 9: "lunch", 10: "lunch", 11: "dinner", 12: "lunch",
    13: "dinner", 14: "dinner", 15: "lunch", 16: "dinner",
}

SHIFT_HOURS = {"lunch": (12, 16), "dinner": (19, 24)}

# Same period as the demo orders of the sales service, so wages and sales cover the same days
DEMO_START = date(2026, 9, 1)
DEMO_DAYS = 28


def _shift_for(rng, day, service):
    start_h, end_h = SHIFT_HOURS[service]
    start = datetime(day.year, day.month, day.day) + timedelta(hours=start_h)
    end = datetime(day.year, day.month, day.day) + timedelta(hours=end_h)
    # People clock in/out a few minutes off the official times
    return start + timedelta(minutes=rng.randint(-10, 10)), end + timedelta(minutes=rng.randint(-5, 20))


def generate_clock_ins(conn, restaurant_id, start=DEMO_START, days=DEMO_DAYS, seed=42):
    """Fills the clock-ins of one restaurant with `days` days of shifts (two days off per week each)."""
    rng = random.Random(seed)
    for offset in range(days):
        day = start + timedelta(days=offset)
        for employee_id, service in EMPLOYEE_SHIFTS.items():
            if (employee_id + offset) % 7 in (0, 1):
                continue
            clock_in, clock_out = _shift_for(rng, day, service)
            conn.execute(
                "INSERT INTO clock_ins (restaurant_id, employee_id, clock_in, clock_out) VALUES (?, ?, ?, ?)",
                (restaurant_id, employee_id, clock_in.isoformat(), clock_out.isoformat()),
            )


def seed_personnel_if_empty(conn, restaurant_id):
    """Loads the demo roles, employees and clock-ins into a restaurant that has no roles yet.

    Checking first makes it idempotent: restarting the service never duplicates the demo data.
    """
    if conn.execute("SELECT COUNT(*) FROM roles WHERE restaurant_id = ?", (restaurant_id,)).fetchone()[0] > 0:
        return
    conn.executemany("INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?)", [(r[0], restaurant_id, *r[1:]) for r in ROLES])
    conn.executemany("INSERT INTO employees VALUES (?, ?, ?, ?)", [(e[0], restaurant_id, *e[1:]) for e in EMPLOYEES])
    generate_clock_ins(conn, restaurant_id)
    conn.commit()