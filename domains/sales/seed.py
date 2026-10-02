"""Demo reference data for the sales domain: suppliers, ingredients, menu and recipes."""

# id, name, phone, email, lead_time_days
SUPPLIERS = [
    (1, "Almacenes Levante", "+34 961 234 567", "pedidos@almaceneslevante.es", 3),
    (2, "Carnes Martín", "+34 915 678 901", None, 2),
    (3, "Huerta de Madrid", None, "ventas@huertademadrid.es", 1),
    (4, "Lácteos Sierra", "+34 918 345 210", "info@lacteossierra.es", 2),
    (5, "Bebidas del Sur", "+34 954 112 233", "comercial@bebidasdelsur.es", 4),
]

# Date of the last physical stock count. Current stock = counted stock - what was used since then.
STOCKTAKE_DATE = "2026-09-22"

# id, name, unit, unit_cost (EUR per unit), supplier_id, counted_stock, counted_at, reorder_level
INGREDIENTS = [
    (1, "Rice", "kg", 2.10, 1, 115, STOCKTAKE_DATE, 15),
    (2, "Chicken", "kg", 6.50, 2, 129, STOCKTAKE_DATE, 30),
    (3, "Beef tenderloin", "kg", 32.00, 2, 72, STOCKTAKE_DATE, 8),
    (4, "Ribeye", "kg", 24.00, 2, 133, STOCKTAKE_DATE, 20),
    (5, "Minced beef", "kg", 9.00, 2, 135, STOCKTAKE_DATE, 18),
    (6, "Tomato", "kg", 2.20, 3, 87, STOCKTAKE_DATE, 25),
    (7, "Lettuce", "unit", 0.90, 3, 244, STOCKTAKE_DATE, 40),
    (8, "Mixed vegetables", "kg", 3.00, 3, 208, STOCKTAKE_DATE, 30),
    (9, "Olive oil", "l", 8.50, 1, 125, STOCKTAKE_DATE, 12),
    (10, "Flour", "kg", 0.90, 1, 48, STOCKTAKE_DATE, 5),
    (11, "Milk", "l", 1.10, 4, 175, STOCKTAKE_DATE, 25),
    (12, "Eggs", "unit", 0.25, 4, 1920, STOCKTAKE_DATE, 250),
    (13, "Cream cheese", "kg", 9.50, 4, 43, STOCKTAKE_DATE, 10),
    (14, "Parmesan", "kg", 18.00, 4, 8, STOCKTAKE_DATE, 2),
    (15, "Burger buns", "unit", 0.40, 1, 460, STOCKTAKE_DATE, 80),
    (16, "Water bottle", "unit", 0.35, 5, 950, STOCKTAKE_DATE, 120),
    (17, "Wine bottle", "unit", 5.00, 5, 83, STOCKTAKE_DATE, 20),
    (18, "Beer bottle", "unit", 0.70, 5, 1020, STOCKTAKE_DATE, 120),
]

# code, name, category (codes match the ones used by the POS)
MENU_ITEMS = [
    ("SAL01", "Mixed salad", "starter"),
    ("CRO01", "Chicken croquettes", "starter"),
    ("GAZ01", "Gazpacho", "starter"),
    ("PAE01", "Valencian paella", "main"),
    ("SOL01", "Beef tenderloin", "main"),
    ("ENT01", "Ribeye steak", "main"),
    ("HAM01", "Burger", "main"),
    ("RIS01", "Parmesan risotto", "main"),
    ("TAR01", "Cheesecake", "dessert"),
    ("FLA01", "Flan", "dessert"),
    ("AGU01", "Water", "drink"),
    ("VIN01", "Glass of wine", "drink"),
    ("CER01", "Beer", "drink"),
]

# item_code, ingredient_id, quantity per portion (in the ingredient's unit)
RECIPES = [
    ("SAL01", 7, 0.5), ("SAL01", 6, 0.15), ("SAL01", 9, 0.02),
    ("CRO01", 10, 0.05), ("CRO01", 11, 0.15), ("CRO01", 2, 0.08), ("CRO01", 12, 1), ("CRO01", 9, 0.1),
    ("GAZ01", 6, 0.3), ("GAZ01", 8, 0.1), ("GAZ01", 9, 0.03),
    ("PAE01", 1, 0.1), ("PAE01", 2, 0.2), ("PAE01", 8, 0.1), ("PAE01", 9, 0.03),
    ("SOL01", 3, 0.25), ("SOL01", 8, 0.15), ("SOL01", 9, 0.02),
    ("ENT01", 4, 0.35), ("ENT01", 8, 0.1),
    ("HAM01", 5, 0.2), ("HAM01", 15, 1), ("HAM01", 7, 0.1), ("HAM01", 6, 0.05),
    ("RIS01", 1, 0.09), ("RIS01", 14, 0.04), ("RIS01", 8, 0.1), ("RIS01", 9, 0.02),
    ("TAR01", 13, 0.12), ("TAR01", 12, 1), ("TAR01", 11, 0.05), ("TAR01", 10, 0.02),
    ("FLA01", 11, 0.15), ("FLA01", 12, 2),
    ("AGU01", 16, 1),
    ("VIN01", 17, 0.2),
    ("CER01", 18, 1),
]

# Weekly deliveries before the last stocktake: (received_on, share of the counted stock delivered)
PURCHASE_ROUNDS = [("2026-09-01", 0.9), ("2026-09-08", 0.8), ("2026-09-15", 0.85)]

# description, amount (EUR), month
FIXED_EXPENSES = [
    ("Rent", 3200.00, "2026-09"),
    ("Electricity and water", 850.00, "2026-09"),
    ("Insurance", 180.00, "2026-09"),
    ("Cleaning service", 400.00, "2026-09"),
]


def seed_sales_if_empty(conn):
    """Loads the demo reference data, only on a brand-new database."""
    if conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] > 0:
        return
    conn.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?, ?)", SUPPLIERS)
    conn.executemany("INSERT INTO ingredients VALUES (?, ?, ?, ?, ?, ?, ?, ?)", INGREDIENTS)
    conn.executemany("INSERT INTO menu_items VALUES (?, ?, ?)", MENU_ITEMS)
    conn.executemany("INSERT INTO recipes VALUES (?, ?, ?)", RECIPES)
    conn.executemany(
        "INSERT INTO purchases (supplier_id, ingredient_id, quantity, unit_price, received_on) VALUES (?, ?, ?, ?, ?)",
        [
            (supplier_id, ingredient_id, round(counted * share), unit_cost, day)
            for day, share in PURCHASE_ROUNDS
            for ingredient_id, _, _, unit_cost, supplier_id, counted, _, _ in INGREDIENTS
        ],
    )
    conn.executemany(
        "INSERT INTO fixed_expenses (description, amount, month) VALUES (?, ?, ?)", FIXED_EXPENSES
    )
    conn.commit()