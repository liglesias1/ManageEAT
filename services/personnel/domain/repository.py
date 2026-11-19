"""SQL queries of the personnel domain (T-SQL, SQL Server). Only reads and writes data, no calculations.

Demand (covers per hour and open days) is not here: orders belong to the sales service, and personnel
asks sales for them over HTTP (ADR-6).

Every function takes the restaurant_id and only reads or changes that restaurant's rows. Every write runs
in its own transaction (`with conn:`).
"""


def get_roles(conn, restaurant_id):
    rows = conn.execute(
        """
        SELECT id, name, hourly_rate, covers_per_hour, min_staff FROM roles
         WHERE restaurant_id = %s
         ORDER BY id
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_shifts(conn, restaurant_id):
    """Every clock-in with the role of the employee who worked it."""
    rows = conn.execute(
        """
        SELECT c.clock_in, c.clock_out, e.role_id
          FROM clock_ins c
          JOIN employees e ON e.id = c.employee_id AND e.restaurant_id = c.restaurant_id
         WHERE c.restaurant_id = %s
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_worked_shifts(conn, restaurant_id, start, end):
    """Every clock-in between two dates (inclusive), with the employee, their role and its hourly rate."""
    rows = conn.execute(
        """
        SELECT e.id   AS employee_id,
               e.name AS employee,
               r.name AS [role],
               r.hourly_rate,
               c.clock_in,
               c.clock_out
          FROM clock_ins c
          JOIN employees e ON e.id = c.employee_id AND e.restaurant_id = c.restaurant_id
          JOIN roles r     ON r.id = e.role_id
         WHERE c.restaurant_id = %s
           AND CAST(c.clock_in AS DATE) BETWEEN %s AND %s
         ORDER BY r.id, e.name
        """,
        (restaurant_id, start, end),
    ).fetchall()
    return [dict(row) for row in rows]


def get_clock_in_period(conn, restaurant_id):
    """First and last day with clock-ins, as ('YYYY-MM-DD', 'YYYY-MM-DD'), or (None, None)."""
    row = conn.execute(
        """
        SELECT MIN(CAST(clock_in AS DATE)) AS first_day, MAX(CAST(clock_in AS DATE)) AS last_day
          FROM clock_ins
         WHERE restaurant_id = %s
        """,
        (restaurant_id,),
    ).fetchone()
    return row["first_day"], row["last_day"]


# ---------- Roles ----------

def get_roles_with_staff(conn, restaurant_id):
    """Every role with how many employees have it (a role with employees cannot be deleted)."""
    rows = conn.execute(
        """
        SELECT r.id, r.name, r.hourly_rate, r.covers_per_hour, r.min_staff,
               (SELECT COUNT(*) FROM employees e WHERE e.role_id = r.id) AS employees
          FROM roles r
         WHERE r.restaurant_id = %s
         ORDER BY r.id
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_role(conn, restaurant_id, role_id):
    row = conn.execute(
        "SELECT id, name, hourly_rate, covers_per_hour, min_staff FROM roles WHERE id = %s AND restaurant_id = %s",
        (role_id, restaurant_id),
    ).fetchone()
    return dict(row) if row else None


def add_role(conn, restaurant_id, name, hourly_rate, covers_per_hour, min_staff):
    with conn:
        return conn.execute(
            """
            INSERT INTO roles (restaurant_id, name, hourly_rate, covers_per_hour, min_staff)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (restaurant_id, name, hourly_rate, covers_per_hour, min_staff),
        ).lastrowid


def update_role(conn, restaurant_id, role_id, name, hourly_rate, covers_per_hour, min_staff):
    with conn:
        conn.execute(
            """
            UPDATE roles SET name = %s, hourly_rate = %s, covers_per_hour = %s, min_staff = %s
             WHERE id = %s AND restaurant_id = %s
            """,
            (name, hourly_rate, covers_per_hour, min_staff, role_id, restaurant_id),
        )


def delete_role_without_staff(conn, restaurant_id, role_id):
    """Deletes the role only if no employee has it. Returns True if it was deleted.

    The check and the delete are one statement, so an employee added at the same moment cannot be left
    pointing at a deleted role.
    """
    with conn:
        deleted = conn.execute(
            """
            DELETE FROM roles
             WHERE id = %s AND restaurant_id = %s
               AND NOT EXISTS (SELECT 1 FROM employees e WHERE e.role_id = roles.id)
            """,
            (role_id, restaurant_id),
        ).rowcount
    return deleted == 1


# ---------- Employees ----------

def get_employees(conn, restaurant_id):
    """Every employee with their role and how many clock-ins they have (with clock-ins, they cannot be deleted)."""
    rows = conn.execute(
        """
        SELECT e.id, e.name, e.role_id, r.name AS [role],
               (SELECT COUNT(*) FROM clock_ins c
                 WHERE c.employee_id = e.id AND c.restaurant_id = e.restaurant_id) AS clock_ins
          FROM employees e
          JOIN roles r ON r.id = e.role_id
         WHERE e.restaurant_id = %s
         ORDER BY e.name
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_employee(conn, restaurant_id, employee_id):
    row = conn.execute(
        "SELECT id, name, role_id FROM employees WHERE id = %s AND restaurant_id = %s",
        (employee_id, restaurant_id),
    ).fetchone()
    return dict(row) if row else None


def add_employee(conn, restaurant_id, name, role_id):
    with conn:
        return conn.execute(
            "INSERT INTO employees (restaurant_id, name, role_id) VALUES (%s, %s, %s)",
            (restaurant_id, name, role_id),
        ).lastrowid


def update_employee(conn, restaurant_id, employee_id, name, role_id):
    with conn:
        conn.execute(
            "UPDATE employees SET name = %s, role_id = %s WHERE id = %s AND restaurant_id = %s",
            (name, role_id, employee_id, restaurant_id),
        )


def delete_employee_without_clock_ins(conn, restaurant_id, employee_id):
    """Deletes the employee only if they have no clock-ins. Returns True if they were deleted.

    Payroll and the schedule are calculated from the clock-ins, so an employee with clock-ins is part of
    the restaurant's history and stays. The check and the delete are one statement, as for roles.
    """
    with conn:
        deleted = conn.execute(
            """
            DELETE FROM employees
             WHERE id = %s AND restaurant_id = %s
               AND NOT EXISTS (SELECT 1 FROM clock_ins c
                                WHERE c.employee_id = employees.id AND c.restaurant_id = employees.restaurant_id)
            """,
            (employee_id, restaurant_id),
        ).rowcount
    return deleted == 1


# ---------- Clock-ins entered by hand ----------

def has_overlapping_clock_in(conn, restaurant_id, employee_id, clock_in, clock_out):
    """True if the employee already has a clock-in that shares any time with [clock_in, clock_out)."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM clock_ins
         WHERE restaurant_id = %s AND employee_id = %s
           AND clock_in < %s AND clock_out > %s
        """,
        (restaurant_id, employee_id, clock_out, clock_in),
    ).fetchone()
    return row["n"] > 0


def add_clock_in(conn, restaurant_id, employee_id, clock_in, clock_out):
    with conn:
        return conn.execute(
            "INSERT INTO clock_ins (restaurant_id, employee_id, clock_in, clock_out) VALUES (%s, %s, %s, %s)",
            (restaurant_id, employee_id, clock_in, clock_out),
        ).lastrowid


# ---------- Last covers received from sales ----------

def save_demand(conn, restaurant_id, payload, fetched_at):
    """Keeps sales' last answer about covers (as JSON text), replacing the previous one of that restaurant.

    MERGE updates the row if the restaurant already has one and inserts it otherwise (SQLite's ON CONFLICT);
    HOLDLOCK stops two requests at the same moment from both inserting it.
    """
    conn.execute(
        """
        MERGE demand_snapshots WITH (HOLDLOCK) AS saved
        USING (SELECT %s AS restaurant_id, %s AS payload, %s AS fetched_at) AS answer
           ON saved.restaurant_id = answer.restaurant_id
         WHEN MATCHED THEN
              UPDATE SET payload = answer.payload, fetched_at = answer.fetched_at
         WHEN NOT MATCHED THEN
              INSERT (restaurant_id, payload, fetched_at) VALUES (answer.restaurant_id, answer.payload, answer.fetched_at);
        """,
        (restaurant_id, payload, fetched_at),
    )
    conn.commit()


def get_demand_snapshot(conn, restaurant_id):
    """The last answer about covers received from sales and when, as (payload, fetched_at), or None."""
    row = conn.execute(
        "SELECT payload, fetched_at FROM demand_snapshots WHERE restaurant_id = %s", (restaurant_id,)
    ).fetchone()
    return (row["payload"], row["fetched_at"]) if row else None