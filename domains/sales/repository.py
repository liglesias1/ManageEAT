"""SQL queries of the sales domain. Only reads and writes data, no calculations."""


def get_dish_sales(conn):
    """Units sold, revenue and ingredient cost per portion for every dish on the menu."""
    rows = conn.execute(
        """
        SELECT m.code,
               m.name,
               m.category,
               COALESCE(SUM(oi.quantity), 0)                 AS units_sold,
               COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue,
               (SELECT COALESCE(SUM(r.quantity * i.unit_cost), 0)
                  FROM recipes r
                  JOIN ingredients i ON i.id = r.ingredient_id
                 WHERE r.item_code = m.code)                  AS unit_cost
          FROM menu_items m
          LEFT JOIN order_items oi ON oi.item_code = m.code
         GROUP BY m.code
         ORDER BY m.category, m.code
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_stock_levels(conn):
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
                 WHERE r.ingredient_id = i.id)        AS used_in_period,
               (SELECT COALESCE(SUM(oi.quantity * r.quantity), 0)
                  FROM recipes r
                  JOIN order_items oi ON oi.item_code = r.item_code
                  JOIN orders o       ON o.id = oi.order_id
                 WHERE r.ingredient_id = i.id
                   AND date(o.created_at) >= i.counted_at) AS used_since_count,
               (SELECT COALESCE(SUM(p.quantity), 0)
                  FROM purchases p
                 WHERE p.ingredient_id = i.id
                   AND p.received_on >= i.counted_at)      AS received_since_count
          FROM ingredients i
          JOIN suppliers s ON s.id = i.supplier_id
         ORDER BY i.name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_last_order_day(conn):
    """The most recent day with orders, as 'YYYY-MM-DD' (None if there are no orders)."""
    return conn.execute("SELECT MAX(date(created_at)) FROM orders").fetchone()[0]


def get_suppliers(conn):
    """Every supplier with the names of the ingredients it supplies, e.g. 'Chicken, Ribeye'."""
    rows = conn.execute(
        """
        SELECT s.id, s.name, s.phone, s.email, s.lead_time_days,
               COALESCE(GROUP_CONCAT(i.name, ', '), '') AS supplies
          FROM suppliers s
          LEFT JOIN ingredients i ON i.supplier_id = s.id
         GROUP BY s.id
         ORDER BY s.name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_supplier(conn, supplier_id):
    """One supplier's contact details, or None if it does not exist."""
    row = conn.execute(
        "SELECT id, name, phone, email, lead_time_days FROM suppliers WHERE id = ?", (supplier_id,)
    ).fetchone()
    return dict(row) if row else None


def get_ingredient_choices(conn):
    """Ingredients with their unit, cost and current supplier, for the choices in the forms."""
    rows = conn.execute(
        """
        SELECT i.id, i.name, i.unit, i.unit_cost, s.name AS supplier
          FROM ingredients i
          JOIN suppliers s ON s.id = i.supplier_id
         ORDER BY i.name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def add_supplier(conn, name, phone, email, lead_time_days, ingredient_ids=()):
    """Saves a new supplier and makes it the supplier of the chosen ingredients, in one transaction."""
    cursor = conn.execute(
        "INSERT INTO suppliers (name, phone, email, lead_time_days) VALUES (?, ?, ?, ?)",
        (name, phone, email, lead_time_days),
    )
    supplier_id = cursor.lastrowid
    conn.executemany(
        "UPDATE ingredients SET supplier_id = ? WHERE id = ?",
        [(supplier_id, ingredient_id) for ingredient_id in ingredient_ids],
    )
    conn.commit()
    return supplier_id


def get_purchases(conn, supplier_id):
    """Every delivery from a supplier, newest first."""
    rows = conn.execute(
        """
        SELECT p.id, p.received_on, i.name AS ingredient, i.unit, p.quantity, p.unit_price,
               p.quantity * p.unit_price AS total
          FROM purchases p
          JOIN ingredients i ON i.id = p.ingredient_id
         WHERE p.supplier_id = ?
         ORDER BY p.received_on DESC, p.id DESC
        """,
        (supplier_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_purchase(conn, supplier_id, ingredient_id, quantity, unit_price, received_on):
    conn.execute(
        "INSERT INTO purchases (supplier_id, ingredient_id, quantity, unit_price, received_on) VALUES (?, ?, ?, ?, ?)",
        (supplier_id, ingredient_id, quantity, unit_price, received_on),
    )
    conn.commit()



# ---------- Profit and loss ----------

def get_sales_period(conn):
    """First and last day with orders, as ('YYYY-MM-DD', 'YYYY-MM-DD'), or (None, None)."""
    row = conn.execute("SELECT MIN(date(created_at)), MAX(date(created_at)) FROM orders").fetchone()
    return row[0], row[1]


def get_daily_sales(conn, start, end):
    """Revenue and cost of the ingredients used, per day: units sold x what their recipes cost."""
    rows = conn.execute(
        """
        SELECT date(o.created_at)                  AS day,
               SUM(oi.quantity * oi.unit_price)    AS revenue,
               SUM(oi.quantity * COALESCE((SELECT SUM(r.quantity * i.unit_cost)
                                             FROM recipes r
                                             JOIN ingredients i ON i.id = r.ingredient_id
                                            WHERE r.item_code = oi.item_code), 0)) AS ingredient_cost
          FROM orders o
          JOIN order_items oi ON oi.order_id = o.id
         WHERE date(o.created_at) BETWEEN ? AND ?
         GROUP BY day
         ORDER BY day
        """,
        (start, end),
    ).fetchall()
    return [dict(row) for row in rows]


def get_fixed_expenses(conn, month):
    rows = conn.execute(
        "SELECT id, description, amount, month FROM fixed_expenses WHERE month = ? ORDER BY amount DESC", (month,)
    ).fetchall()
    return [dict(row) for row in rows]


def add_fixed_expense(conn, description, amount, month):
    conn.execute(
        "INSERT INTO fixed_expenses (description, amount, month) VALUES (?, ?, ?)", (description, amount, month)
    )
    conn.commit()


# ---------- Menu and recipes ----------

def get_menu(conn):
    """Every dish on the menu with its current price."""
    rows = conn.execute("SELECT code, name, category, price FROM menu_items ORDER BY category, name").fetchall()
    return [dict(row) for row in rows]


def get_recipe_lines(conn):
    """Every ingredient of every recipe, with how much one portion uses and what it costs."""
    rows = conn.execute(
        """
        SELECT r.item_code, i.name AS ingredient, i.unit, r.quantity, i.unit_cost
          FROM recipes r
          JOIN ingredients i ON i.id = r.ingredient_id
         ORDER BY r.item_code, i.name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def add_dish(conn, code, name, category, price, recipe):
    """Adds a dish and its recipe in one transaction: either both are saved or neither is.

    `recipe` is a list of (ingredient_id, quantity per portion).
    """
    with conn:
        conn.execute(
            "INSERT INTO menu_items (code, name, category, price) VALUES (?, ?, ?, ?)",
            (code, name, category, price),
        )
        conn.executemany(
            "INSERT INTO recipes (item_code, ingredient_id, quantity) VALUES (?, ?, ?)",
            [(code, ingredient_id, quantity) for ingredient_id, quantity in recipe],
        )


def add_ingredient(conn, name, unit, unit_cost, counted_stock, counted_at, reorder_level,
                   supplier_id=None, new_supplier=None):
    """Saves a new ingredient with its first stock count, and returns the id of its supplier.

    If `new_supplier` is given (name, phone, email, lead_time_days), the supplier is created first.
    Both are saved in one transaction: an ingredient never ends up without its supplier.
    """
    with conn:
        if new_supplier is not None:
            supplier_id = conn.execute(
                "INSERT INTO suppliers (name, phone, email, lead_time_days) VALUES (?, ?, ?, ?)", new_supplier
            ).lastrowid
        conn.execute(
            """
            INSERT INTO ingredients (name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level),
        )
    return supplier_id



# ---------- Editing ----------

def get_dish(conn, code):
    """One dish of the menu, or None if it does not exist."""
    row = conn.execute("SELECT code, name, category, price FROM menu_items WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def get_recipe(conn, code):
    """The recipe of one dish as a list of (ingredient_id, quantity per portion)."""
    rows = conn.execute(
        "SELECT ingredient_id, quantity FROM recipes WHERE item_code = ? ORDER BY ingredient_id", (code,)
    ).fetchall()
    return [(row["ingredient_id"], row["quantity"]) for row in rows]


def update_dish(conn, code, name, category, price, recipe):
    """Changes a dish and replaces its whole recipe, in one transaction."""
    with conn:
        conn.execute(
            "UPDATE menu_items SET name = ?, category = ?, price = ? WHERE code = ?", (name, category, price, code)
        )
        conn.execute("DELETE FROM recipes WHERE item_code = ?", (code,))
        conn.executemany(
            "INSERT INTO recipes (item_code, ingredient_id, quantity) VALUES (?, ?, ?)",
            [(code, ingredient_id, quantity) for ingredient_id, quantity in recipe],
        )


def get_ingredient(conn, ingredient_id):
    """One ingredient with its supplier and last stock count, or None if it does not exist."""
    row = conn.execute(
        """
        SELECT id, name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level
          FROM ingredients WHERE id = ?
        """,
        (ingredient_id,),
    ).fetchone()
    return dict(row) if row else None


def update_ingredient(conn, ingredient_id, name, unit, unit_cost, supplier_id, counted_stock, counted_at,
                      reorder_level):
    conn.execute(
        """
        UPDATE ingredients
           SET name = ?, unit = ?, unit_cost = ?, supplier_id = ?, counted_stock = ?, counted_at = ?, reorder_level = ?
         WHERE id = ?
        """,
        (name, unit, unit_cost, supplier_id, counted_stock, counted_at, reorder_level, ingredient_id),
    )
    conn.commit()


def update_supplier(conn, supplier_id, name, phone, email, lead_time_days):
    conn.execute(
        "UPDATE suppliers SET name = ?, phone = ?, email = ?, lead_time_days = ? WHERE id = ?",
        (name, phone, email, lead_time_days, supplier_id),
    )
    conn.commit()