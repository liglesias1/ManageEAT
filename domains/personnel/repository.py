"""SQL queries of the personnel domain. Only reads and writes data, no calculations."""


def get_covers_by_hour(conn):
    """Total diners per day and hour, from the orders recorded by the POS."""
    rows = conn.execute(
        """
        SELECT date(created_at)                          AS day,
               CAST(strftime('%H', created_at) AS INTEGER) AS hour,
               SUM(covers)                               AS covers
          FROM orders
         GROUP BY day, hour
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_open_days(conn):
    """Every day the restaurant registered at least one order, as 'YYYY-MM-DD'."""
    rows = conn.execute("SELECT DISTINCT date(created_at) AS day FROM orders ORDER BY day").fetchall()
    return [row["day"] for row in rows]


def get_roles(conn):
    rows = conn.execute(
        "SELECT id, name, hourly_rate, covers_per_hour, min_staff FROM roles ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def get_shifts(conn):
    """Every clock-in with the role of the employee who worked it."""
    rows = conn.execute(
        """
        SELECT c.clock_in, c.clock_out, e.role_id
          FROM clock_ins c
          JOIN employees e ON e.id = c.employee_id
        """
    ).fetchall()
    return [dict(row) for row in rows]