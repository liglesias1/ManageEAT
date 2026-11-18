"""SQL queries of the sales domain (T-SQL, SQL Server). Only reads and writes data, no calculations.

Every function takes the restaurant_id and only reads or changes that restaurant's rows,
so one restaurant can never see or edit another's data.

Ported from SQLite: date(x) -> CAST(x AS DATE), strftime('%Y-%m', x) -> CONVERT(CHAR(7), x, 126),
GROUP_CONCAT -> STRING_AGG, ON CONFLICT -> MERGE, and every column that is not aggregated is listed in
GROUP BY, which SQL Server requires.
"""


def get_dish_sales(conn, restaurant_id):
    """Units sold, revenue and ingredient cost per portion for every dish on the menu."""
    rows = conn.execute(
        """
        SELECT m.code,
               m.name,
               m.category,
               COALESCE(SUM(sold.quantity), 0)                   AS units_sold,
               COALESCE(SUM(sold.quantity * sold.unit_price), 0) AS revenue,
               (SELECT COALESCE(SUM(r.quantity * i.unit_cost), 0)
                  FROM recipes r
                  JOIN ingredients i ON i.id = r.ingredient_id
                 WHERE r.restaurant_id = m.restaurant_id
                   AND r.item_code = m.code)                     AS unit_cost
          FROM menu_items m
          LEFT JOIN (SELECT oi.item_code, oi.quantity, oi.unit_price
                       FROM order_items oi
                       JOIN orders o ON o.id = oi.order_id
                      WHERE o.restaurant_id = %s) sold ON sold.item_code = m.code
         WHERE m.restaurant_id = %s
         GROUP BY m.restaurant_id, m.code, m.name, m.category
         ORDER BY m.category, m.code
        """,
        (restaurant_id, restaurant_id),
    ).fetchall()
    return [dict(row) for row in rows]


def get_stock_levels(conn, restaurant_id):
    """Every ingredient with its supplier, last stocktake and how much the recipes used since then."""
    rows = conn.execute(
        """
        SELECT i.id,
               i.name,
               i.unit,
               i.unit_cost,
               i.counted_stock,
               i.counted_at,
               i.reorder_level,
               i.supplier_id,
               s.name           AS supplier,
               s.lead_time_days,
               (SELECT COALESCE(SUM(oi.quantity * r.quantity), 0)
                  FROM recipes r
                  JOIN order_items oi ON oi.item_code = r.item_code
                  JOIN orders o       ON o.id = oi.order_id AND o.restaurant_id = r.restaurant_id
                 WHERE r.ingredient_id = i.id)                       AS used_in_period,
               (SELECT COALESCE(SUM(oi.quantity * r.quantity), 0)
                  FROM recipes r
                  JOIN order_items oi ON oi.item_code = r.item_code
                  JOIN orders o       ON o.id = oi.order_id AND o.restaurant_id = r.restaurant_id
                 WHERE r.ingredient_id = i.id
                   AND CAST(o.created_at AS DATE) >= i.counted_at)  AS used_since_count,
               (SELECT COALESCE(SUM(p.quantity), 0)
                  FROM purchases p
                 WHERE p.ingredient_id = i.id
                   AND p.received_on >= i.counted_at)                AS received_since_count
          FROM ingredients i
          JOIN suppliers s ON s.id = i.supplier_id
         WHERE i.restaurant_id = %s
         ORDER BY i.name
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_last_order_day(conn, restaurant_id):
    """The most recent day with orders, as 'YYYY-MM-DD' (None if there are no orders)."""
    return conn.execute(
        "SELECT MAX(CAST(created_at AS DATE)) FROM orders WHERE restaurant_id = %s", (restaurant_id,)
    ).fetchone()[0]


def get_suppliers(conn, restaurant_id):
    """Every supplier with the names of the ingredients it supplies, alphabetically, e.g. 'Chicken, Ribeye'."""
    rows = conn.execute(
        """
        SELECT s.id, s.name, s.phone, s.email, s.lead_time_days,
               COALESCE(STRING_AGG(i.name, ', ') WITHIN GROUP (ORDER BY i.name), '') AS supplies
          FROM suppliers s
          LEFT JOIN ingredients i ON i.supplier_id = s.id
         WHERE s.restaurant_id = %s
         GROUP BY s.id, s.name, s.phone, s.email, s.lead_time_days
         ORDER BY s.name
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_supplier(conn, restaurant_id, supplier_id):
    """One supplier's contact details, or None if it does not exist in this restaurant."""
    row = conn.execute(
        "SELECT id, name, phone, email, lead_time_days FROM suppliers WHERE id = %s AND restaurant_id = %s",
        (supplier_id, restaurant_id),
    ).fetchone()
    return dict(row) if row else None


def get_ingredient_choices(conn, restaurant_id):
    """Ingredients with their unit, cost and current supplier, for the choices in the forms."""
    rows = conn.execute(
        """
        SELECT i.id, i.name, i.unit, i.unit_cost, s.name AS supplier
          FROM ingredients i
          JOIN suppliers s ON s.id = i.supplier_id
         WHERE i.restaurant_id = %s
         ORDER BY i.name
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_supplier(conn, restaurant_id, name, phone, email, lead_time_days, ingredient_ids=()):
    """Saves a new supplier and makes it the supplier of the chosen ingredients, in one transaction."""
    with conn:
        supplier_id = conn.execute(
            "INSERT INTO suppliers (restaurant_id, name, phone, email, lead_time_days) VALUES (%s, %s, %s, %s, %s)",
            (restaurant_id, name, phone, email, lead_time_days),
        ).lastrowid
        for ingredient_id in ingredient_ids:
            conn.execute(
                "UPDATE ingredients SET supplier_id = %s WHERE id = %s AND restaurant_id = %s",
                (supplier_id, ingredient_id, restaurant_id),
            )
    return supplier_id


def get_purchases(conn, restaurant_id, supplier_id):
    """Every delivery from one of this restaurant's suppliers, newest first."""
    rows = conn.execute(
        """
        SELECT p.id, p.received_on, i.name AS ingredient, i.unit, p.quantity, p.unit_price,
               p.quantity * p.unit_price AS total
          FROM purchases p
          JOIN ingredients i ON i.id = p.ingredient_id
          JOIN suppliers s   ON s.id = p.supplier_id
         WHERE p.supplier_id = %s AND s.restaurant_id = %s
         ORDER BY p.received_on DESC, p.id DESC
        """,
        (supplier_id, restaurant_id),
    ).fetchall()
    return [dict(row) for row in rows]


def add_purchase(conn, supplier_id, ingredient_id, quantity, unit_price, received_on):
    """Saves a delivery. The route checks first that the supplier and ingredient belong to the restaurant."""
    conn.execute(
        "INSERT INTO purchases (supplier_id, ingredient_id, quantity, unit_price, received_on) "
        "VALUES (%s, %s, %s, %s, %s)",
        (supplier_id, ingredient_id, quantity, unit_price, received_on),
    )
    conn.commit()


# ---------- Profit and loss ----------

def get_sales_period(conn, restaurant_id):
    """First and last day with orders, as ('YYYY-MM-DD', 'YYYY-MM-DD'), or (None, None)."""
    row = conn.execute(
        "SELECT MIN(CAST(created_at AS DATE)), MAX(CAST(created_at AS DATE)) FROM orders WHERE restaurant_id = %s",
        (restaurant_id,),
    ).fetchone()
    return row[0], row[1]


def get_daily_sales(conn, restaurant_id, start, end):
    """Revenue and cost of the ingredients used, per day: units sold x what their recipes cost.

    SQL Server does not allow a subquery inside SUM(), so the cost of one portion of each dish is worked
    out first (dish_cost) and joined to the order lines.
    """
    rows = conn.execute(
        """
        WITH dish_cost AS (
            SELECT r.item_code, SUM(r.quantity * i.unit_cost) AS unit_cost
              FROM recipes r
              JOIN ingredients i ON i.id = r.ingredient_id
             WHERE r.restaurant_id = %s
             GROUP BY r.item_code
        )
        SELECT CAST(o.created_at AS DATE)                    AS [day],
               SUM(oi.quantity * oi.unit_price)              AS revenue,
               SUM(oi.quantity * COALESCE(dc.unit_cost, 0))  AS ingredient_cost
          FROM orders o
          JOIN order_items oi    ON oi.order_id = o.id
          LEFT JOIN dish_cost dc ON dc.item_code = oi.item_code
         WHERE o.restaurant_id = %s
           AND CAST(o.created_at AS DATE) BETWEEN %s AND %s
         GROUP BY CAST(o.created_at AS DATE)
         ORDER BY [day]
        """,
        (restaurant_id, restaurant_id, start, end),
    ).fetchall()
    return [dict(row) for row in rows]


def get_fixed_expenses(conn, restaurant_id, month):
    rows = conn.execute(
        """
        SELECT id, description, amount, month FROM fixed_expenses
         WHERE restaurant_id = %s AND month = %s
         ORDER BY amount DESC
        """,
        (restaurant_id, month),
    ).fetchall()
    return [dict(row) for row in rows]


def add_fixed_expense(conn, restaurant_id, description, amount, month):
    conn.execute(
        "INSERT INTO fixed_expenses (restaurant_id, description, amount, month) VALUES (%s, %s, %s, %s)",
        (restaurant_id, description, amount, month),
    )
    conn.commit()


# ---------- Menu and recipes ----------

def get_menu(conn, restaurant_id):
    """Every dish on the menu with its current price."""
    rows = conn.execute(
        "SELECT code, name, category, price FROM menu_items WHERE restaurant_id = %s ORDER BY category, name",
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_recipe_lines(conn, restaurant_id):
    """Every ingredient of every recipe, with how much one portion uses and what it costs."""
    rows = conn.execute(
        """
        SELECT r.item_code, i.name AS ingredient, i.unit, r.quantity, i.unit_cost
          FROM recipes r
          JOIN ingredients i ON i.id = r.ingredient_id
         WHERE r.restaurant_id = %s
         ORDER BY r.item_code, i.name
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_dish(conn, restaurant_id, code, name, category, price, recipe):
    """Adds a dish and its recipe in one transaction: either both are saved or neither is.

    `recipe` is a list of (ingredient_id, quantity per portion).
    """
    with conn:
        conn.execute(
            "INSERT INTO menu_items (restaurant_id, code, name, category, price) VALUES (%s, %s, %s, %s, %s)",
            (restaurant_id, code, name, category, price),
        )
        for ingredient_id, quantity in recipe:
            conn.execute(
                "INSERT INTO recipes (restaurant_id, item_code, ingredient_id, quantity) VALUES (%s, %s, %s, %s)",
                (restaurant_id, code, ingredient_id, quantity),
            )


def add_ingredient(conn, restaurant_id, name, unit, unit_cost, counted_stock, counted_at, reorder_level,
                   supplier_id=None, new_supplier=None):
    """Saves a new ingredient with its first stock count, and returns the id of its supplier.

    If `new_supplier` is given (name, phone, email, lead_time_days), the supplier is created first.
    Both are saved in one transaction: an ingredient never ends up without its supplier.
    """
    with conn:
        if new_supplier is not None:
            supplier_id = conn.execute(
                "INSERT INTO suppliers (restaurant_id, name, phone, email, lead_time_days) "
                "VALUES (%s, %s, %s, %s, %s)",
                (restaurant_id, *new_supplier),
            ).lastrowid
        conn.execute(
            """
            INSERT INTO ingredients (restaurant_id, name, unit, unit_cost, supplier_id, counted_stock, counted_at,
                                     reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (restaurant_id, name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level),
        )
    return supplier_id


# ---------- Editing ----------

def get_dish(conn, restaurant_id, code):
    """One dish of the menu, or None if this restaurant has no dish with that code."""
    row = conn.execute(
        "SELECT code, name, category, price FROM menu_items WHERE restaurant_id = %s AND code = %s",
        (restaurant_id, code),
    ).fetchone()
    return dict(row) if row else None


def get_recipe(conn, restaurant_id, code):
    """The recipe of one dish as a list of (ingredient_id, quantity per portion)."""
    rows = conn.execute(
        """
        SELECT ingredient_id, quantity FROM recipes
         WHERE restaurant_id = %s AND item_code = %s
         ORDER BY ingredient_id
        """,
        (restaurant_id, code),
    ).fetchall()
    return [(row["ingredient_id"], row["quantity"]) for row in rows]


def update_dish(conn, restaurant_id, code, name, category, price, recipe):
    """Changes a dish and replaces its whole recipe, in one transaction."""
    with conn:
        conn.execute(
            "UPDATE menu_items SET name = %s, category = %s, price = %s WHERE restaurant_id = %s AND code = %s",
            (name, category, price, restaurant_id, code),
        )
        conn.execute("DELETE FROM recipes WHERE restaurant_id = %s AND item_code = %s", (restaurant_id, code))
        for ingredient_id, quantity in recipe:
            conn.execute(
                "INSERT INTO recipes (restaurant_id, item_code, ingredient_id, quantity) VALUES (%s, %s, %s, %s)",
                (restaurant_id, code, ingredient_id, quantity),
            )


def get_ingredient(conn, restaurant_id, ingredient_id):
    """One ingredient with its supplier and last stock count, or None if it does not exist in this restaurant."""
    row = conn.execute(
        """
        SELECT id, name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level
          FROM ingredients WHERE id = %s AND restaurant_id = %s
        """,
        (ingredient_id, restaurant_id),
    ).fetchone()
    return dict(row) if row else None


def update_ingredient(conn, restaurant_id, ingredient_id, name, unit, unit_cost, supplier_id, counted_stock,
                      counted_at, reorder_level):
    conn.execute(
        """
        UPDATE ingredients
           SET name = %s, unit = %s, unit_cost = %s, supplier_id = %s, counted_stock = %s, counted_at = %s,
               reorder_level = %s
         WHERE id = %s AND restaurant_id = %s
        """,
        (name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level, ingredient_id, restaurant_id),
    )
    conn.commit()


def update_supplier(conn, restaurant_id, supplier_id, name, phone, email, lead_time_days):
    conn.execute(
        "UPDATE suppliers SET name = %s, phone = %s, email = %s, lead_time_days = %s "
        "WHERE id = %s AND restaurant_id = %s",
        (name, phone, email, lead_time_days, supplier_id, restaurant_id),
    )
    conn.commit()


# ---------- Months ----------

def get_months(conn, restaurant_id):
    """Every month with orders or fixed expenses, as 'YYYY-MM', oldest first.

    CONVERT(CHAR(7), x, 126) keeps the first 7 characters of the ISO date, 'YYYY-MM'.
    """
    rows = conn.execute(
        """
        SELECT CONVERT(CHAR(7), created_at, 126) AS month FROM orders WHERE restaurant_id = %s
        UNION
        SELECT month FROM fixed_expenses WHERE restaurant_id = %s
        ORDER BY month
        """,
        (restaurant_id, restaurant_id),
    ).fetchall()
    return [row["month"] for row in rows]


def get_sales_period_in_month(conn, restaurant_id, month):
    """First and last day with orders within one month ('YYYY-MM'), or (None, None) if it has none."""
    row = conn.execute(
        """
        SELECT MIN(CAST(created_at AS DATE)), MAX(CAST(created_at AS DATE)) FROM orders
         WHERE restaurant_id = %s AND CONVERT(CHAR(7), created_at, 126) = %s
        """,
        (restaurant_id, month),
    ).fetchone()
    return row[0], row[1]


def get_all_fixed_expenses(conn, restaurant_id):
    """Every fixed expense of every month, for the month-by-month history."""
    rows = conn.execute(
        "SELECT id, description, amount, month FROM fixed_expenses WHERE restaurant_id = %s ORDER BY month",
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------- Demand: what the personnel service asks for ----------

def get_covers_by_hour(conn, restaurant_id):
    """Total diners per day and hour, from the orders recorded by the POS."""
    rows = conn.execute(
        """
        SELECT CAST(created_at AS DATE)      AS [day],
               DATEPART(HOUR, created_at)    AS [hour],
               SUM(covers)                   AS covers
          FROM orders
         WHERE restaurant_id = %s
         GROUP BY CAST(created_at AS DATE), DATEPART(HOUR, created_at)
         ORDER BY [day], [hour]
        """,
        (restaurant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_open_days(conn, restaurant_id):
    """Every day the restaurant registered at least one order, as 'YYYY-MM-DD'."""
    rows = conn.execute(
        "SELECT DISTINCT CAST(created_at AS DATE) AS [day] FROM orders WHERE restaurant_id = %s ORDER BY [day]",
        (restaurant_id,),
    ).fetchall()
    return [row["day"] for row in rows]


# ---------- Last wage costs received from personnel ----------

def save_labor_cost(conn, restaurant_id, start, end, labor_cost, fetched_at):
    """Keeps the wage cost personnel just gave for a period, replacing the previous copy of that period.

    MERGE updates the row if the period already has one and inserts it otherwise (SQLite's ON CONFLICT);
    HOLDLOCK stops two requests at the same moment from both inserting it.
    """
    conn.execute(
        """
        MERGE labor_cost_snapshots WITH (HOLDLOCK) AS saved
        USING (SELECT %s AS restaurant_id, %s AS period_start, %s AS period_end,
                      %s AS labor_cost, %s AS fetched_at) AS answer
           ON saved.restaurant_id = answer.restaurant_id
          AND saved.period_start = answer.period_start
          AND saved.period_end = answer.period_end
         WHEN MATCHED THEN
              UPDATE SET labor_cost = answer.labor_cost, fetched_at = answer.fetched_at
         WHEN NOT MATCHED THEN
              INSERT (restaurant_id, period_start, period_end, labor_cost, fetched_at)
              VALUES (answer.restaurant_id, answer.period_start, answer.period_end, answer.labor_cost,
                      answer.fetched_at);
        """,
        (restaurant_id, start, end, labor_cost, fetched_at),
    )
    conn.commit()


def get_labor_cost_snapshot(conn, restaurant_id, start, end):
    """The last wage cost received for a period and when it was received, as (cost, fetched_at), or None."""
    row = conn.execute(
        """
        SELECT labor_cost, fetched_at FROM labor_cost_snapshots
         WHERE restaurant_id = %s AND period_start = %s AND period_end = %s
        """,
        (restaurant_id, start, end),
    ).fetchone()
    return (row["labor_cost"], row["fetched_at"]) if row else None