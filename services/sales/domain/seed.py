"""Demo data for the sales service: suppliers, ingredients, menu, recipes, and the orders the POS would record.

The order generator used to live in ingestion/seed.py next to the clock-ins. Seed data moves with its
table, so it is now here, with its own random generator with a fixed seed: every start produces the same
orders, and they do not depend on how personnel generates its clock-ins.
"""
import random
from datetime import date, datetime, timedelta

from database import insert_rows

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

# code, name, category, current menu price in EUR (codes match the ones used by the POS)
MENU_ITEMS = [
    ("SAL01", "Mixed salad", "starter", 9.50),
    ("CRO01", "Chicken croquettes", "starter", 8.00),
    ("GAZ01", "Gazpacho", "starter", 7.50),
    ("PAE01", "Valencian paella", "main", 18.00),
    ("SOL01", "Beef tenderloin", "main", 21.00),
    ("ENT01", "Ribeye steak", "main", 24.00),
    ("HAM01", "Burger", "main", 14.50),
    ("RIS01", "Parmesan risotto", "main", 16.00),
    ("TAR01", "Cheesecake", "dessert", 6.50),
    ("FLA01", "Flan", "dessert", 5.00),
    ("AGU01", "Water", "drink", 2.50),
    ("VIN01", "Glass of wine", "drink", 4.00),
    ("CER01", "Beer", "drink", 3.50),
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

# How often each dish is chosen within its category (higher = more popular)
POPULARITY = {
    "SAL01": 3, "CRO01": 5, "GAZ01": 2,
    "PAE01": 6, "SOL01": 2, "ENT01": 3, "HAM01": 5, "RIS01": 1.5,
    "TAR01": 3, "FLA01": 2,
    "AGU01": 4, "VIN01": 3, "CER01": 4,
}

# Relative weight of orders at each opening hour (lunch 13-15h, dinner 20-23h)
HOURLY_WEIGHT = {13: 3, 14: 6, 15: 3, 20: 2, 21: 6, 22: 5, 23: 1}

# Same period as the demo clock-ins of the personnel service, so sales and wages cover the same days
DEMO_START = date(2026, 9, 1)
DEMO_DAYS = 28

PRICES = {code: price for code, _, _, price in MENU_ITEMS}


def _pick(rng, category):
    """Chooses a dish of the category, favouring the most popular ones."""
    dishes = [code for code, _, cat, _ in MENU_ITEMS if cat == category]
    return rng.choices(dishes, [POPULARITY[code] for code in dishes])[0]


def _orders_for_day(rng, day):
    """Returns a list of (order_datetime, covers, items) for one day."""
    weekend = day.weekday() >= 4  # Friday to Sunday are busier
    total_orders = rng.randint(55, 75) if weekend else rng.randint(30, 45)
    hours = list(HOURLY_WEIGHT)
    weights = list(HOURLY_WEIGHT.values())

    orders = []
    for _ in range(total_orders):
        hour = rng.choices(hours, weights)[0]
        when = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59))
        covers = rng.randint(1, 6)
        items = {}
        for _ in range(covers):
            picks = [_pick(rng, "main"), _pick(rng, "drink")]
            if rng.random() < 0.5:
                picks.append(_pick(rng, "starter"))
            if rng.random() < 0.4:
                picks.append(_pick(rng, "dessert"))
            for code in picks:
                items[code] = items.get(code, 0) + 1
        orders.append((when, covers, items))
    return orders


def order_rows(restaurant_id, first_id, start=DEMO_START, days=DEMO_DAYS, seed=42):
    """The demo POS data of one restaurant as (orders, order_items) rows, with order ids from `first_id` on.

    The ids are chosen here, instead of by the database, so the items can refer to their order and both
    tables can be inserted in a few multi-row statements.
    """
    rng = random.Random(seed)
    orders, items = [], []
    order_id = first_id
    for offset in range(days):
        day = start + timedelta(days=offset)
        for when, covers, picked in _orders_for_day(rng, day):
            orders.append((order_id, restaurant_id, rng.randint(1, 20), covers, when))
            items.extend((order_id, code, qty, PRICES[code]) for code, qty in picked.items())
            order_id += 1
    return orders, items


def seed_sales_if_empty(db, restaurant_id):
    """Loads the demo data into a restaurant that has no suppliers yet, in one transaction.

    Checking first makes it idempotent: restarting the service never duplicates the demo data. Suppliers and
    ingredients keep their demo ids, because the recipes, purchases and ingredients refer to them.
    """
    if db.execute("SELECT COUNT(*) FROM suppliers WHERE restaurant_id = %s", (restaurant_id,)).fetchone()[0] > 0:
        return
    with db:
        insert_rows(db, "suppliers", ("id", "restaurant_id", "name", "phone", "email", "lead_time_days"),
                    [(s[0], restaurant_id, *s[1:]) for s in SUPPLIERS], keep_ids=True)
        insert_rows(db, "ingredients", ("id", "restaurant_id", "name", "unit", "unit_cost", "supplier_id",
                                        "counted_stock", "counted_at", "reorder_level"),
                    [(i[0], restaurant_id, *i[1:]) for i in INGREDIENTS], keep_ids=True)
        insert_rows(db, "menu_items", ("restaurant_id", "code", "name", "category", "price"),
                    [(restaurant_id, *m) for m in MENU_ITEMS])
        insert_rows(db, "recipes", ("restaurant_id", "item_code", "ingredient_id", "quantity"),
                    [(restaurant_id, *r) for r in RECIPES])
        insert_rows(db, "purchases", ("supplier_id", "ingredient_id", "quantity", "unit_price", "received_on"), [
            (supplier_id, ingredient_id, round(counted * share), unit_cost, day)
            for day, share in PURCHASE_ROUNDS
            for ingredient_id, _, _, unit_cost, supplier_id, counted, _, _ in INGREDIENTS
        ])
        insert_rows(db, "fixed_expenses", ("restaurant_id", "description", "amount", "month"),
                    [(restaurant_id, *e) for e in FIXED_EXPENSES])
        first_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM orders").fetchone()[0]
        orders, items = order_rows(restaurant_id, first_id)
        insert_rows(db, "orders", ("id", "restaurant_id", "table_no", "covers", "created_at"), orders, keep_ids=True)
        insert_rows(db, "order_items", ("order_id", "item_code", "quantity", "unit_price"), items)
