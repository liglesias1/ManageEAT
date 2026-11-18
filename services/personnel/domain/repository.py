"""SQL queries of the personnel domain (T-SQL, SQL Server). Only reads and writes data, no calculations.

Demand (covers per hour and open days) is not here: orders belong to the sales service, and personnel
asks sales for them over HTTP (ADR-6).

Every function takes the restaurant_id and only reads that restaurant's rows.
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