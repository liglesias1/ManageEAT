"""Demo reference data for the personnel domain: roles and employees."""

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


def seed_personnel_if_empty(conn):
    """Loads the demo roles and employees, only on a brand-new database."""
    if conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] > 0:
        return
    conn.executemany("INSERT INTO roles VALUES (?, ?, ?, ?, ?)", ROLES)
    conn.executemany("INSERT INTO employees VALUES (?, ?, ?)", EMPLOYEES)
    conn.commit()