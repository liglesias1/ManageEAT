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