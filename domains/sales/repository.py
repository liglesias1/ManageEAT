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
                   AND date(o.created_at) >= i.counted_at) AS used_since_count
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
    """Ingredients and their current supplier, for the 'what does it supply' checkboxes."""
    rows = conn.execute(
        """
        SELECT i.id, i.name, s.name AS supplier
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