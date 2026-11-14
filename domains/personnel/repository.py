"""SQL queries of the personnel domain. Only reads and writes data, no calculations.

Every function takes the restaurant_id and only reads that restaurant's rows.
"""


def get_covers_by_hour(conn, restaurant_id):
    """Total diners per day and hour, from the orders recorded by the POS."""
    rows = conn.execute(
        """
        SELECT date(created_at)                          AS day,
               CAST(strftime('%H', created_at) AS INTEGER) AS hour,
               SUM(covers)                               AS covers
          FROM orders
         WHERE restaurant_id = ?
         GROUP BY day, hour
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_open_days(conn, restaurant_id):
    """Every day the restaurant registered at least one order, as 'YYYY-MM-DD'."""
    rows = conn.execute(
        "SELECT DISTINCT date(created_at) AS day FROM orders WHERE restaurant_id = ? ORDER BY day", (restaurant_id,)
    ).fetchall()
    return [row["day"] for row in rows]


def get_roles(conn, restaurant_id):
    rows = conn.execute(
        """
        SELECT id, name, hourly_rate, covers_per_hour, min_staff FROM roles
         WHERE restaurant_id = ?
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
         WHERE c.restaurant_id = ?
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
               r.name AS role,
               r.hourly_rate,
               c.clock_in,
               c.clock_out
          FROM clock_ins c
          JOIN employees e ON e.id = c.employee_id AND e.restaurant_id = c.restaurant_id
          JOIN roles r     ON r.id = e.role_id
         WHERE c.restaurant_id = ?
           AND date(c.clock_in) BETWEEN ? AND ?
         ORDER BY r.id, e.name
        """,
        (restaurant_id, start, end),
    ).fetchall()
    return [dict(row) for row in rows]


def get_clock_in_period(conn, restaurant_id):
    """First and last day with clock-ins, as ('YYYY-MM-DD', 'YYYY-MM-DD')."""
    row = conn.execute(
        "SELECT MIN(date(clock_in)) AS first, MAX(date(clock_in)) AS last FROM clock_ins WHERE restaurant_id = ?",
        (restaurant_id,),
    ).fetchone()
    return row["first"], row["last"]