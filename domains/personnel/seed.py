"""Demo reference data for the personnel domain: roles and employees."""

# id, name, hourly_rate (EUR), covers_per_hour (diners one person can handle in an hour), min_staff
ROLES = [
    (1, "Waiter", 11.50, 12, 1),
    (2, "Kitchen", 13.50, 15, 1),
    (3, "Bar", 12.00, 25, 1),
]

# id, name, role_id (ids match the employee ids used by the clock-in system)
EMPLOYEES = [
    (1, "Lucía Martín", 1),
    (2, "Javier Ruiz", 2),
    (3, "Carmen López", 1),
    (4, "Pablo Sánchez", 2),
    (5, "Elena Gómez", 3),
    (6, "Daniel Torres", 1),
    (7, "Marta Navarro", 2),
    (8, "Sergio Díaz", 3),
    (9, "Laura Romero", 1),
    (10, "Andrés Molina", 1),
]


def seed_personnel_if_empty(conn):
    """Loads the demo roles and employees, only on a brand-new database."""
    if conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] > 0:
        return
    conn.executemany("INSERT INTO roles VALUES (?, ?, ?, ?, ?)", ROLES)
    conn.executemany("INSERT INTO employees VALUES (?, ?, ?)", EMPLOYEES)
    conn.commit()