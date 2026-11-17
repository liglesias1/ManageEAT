"""SQL that creates the tables owned by the sales service: the orders recorded by the POS, and the menu, recipes,
ingredients, suppliers, purchases and fixed expenses.

orders and order_items used to be shared input read by both domains (ADR-3). Since the split they belong
to sales, which reads them on almost every page; personnel asks sales for the covers per hour (ADR-6).

Every table that is read on its own has a restaurant_id. Purchases belong to the restaurant of their
supplier, so they are always read through it.
"""

from domain.schemas import CATEGORIES

_CATEGORY_LIST = ", ".join(f"'{c}'" for c in CATEGORIES)   # 'main', 'starter', 'dessert', 'drink'

SALES_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL,
    table_no       INTEGER NOT NULL,
    covers         INTEGER NOT NULL,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    item_code   TEXT    NOT NULL,
    quantity    INTEGER NOT NULL,
    unit_price  REAL    NOT NULL
);

-- Every page filters the orders by restaurant and date
CREATE INDEX IF NOT EXISTS orders_by_restaurant ON orders (restaurant_id, created_at);

CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY,
    restaurant_id   INTEGER NOT NULL,
    name            TEXT    NOT NULL,
    phone           TEXT,
    email           TEXT,
    lead_time_days  INTEGER NOT NULL,
    CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS ingredients (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL,
    name           TEXT    NOT NULL,
    unit           TEXT    NOT NULL,
    unit_cost      REAL    NOT NULL,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(id),
    counted_stock  REAL    NOT NULL,
    counted_at     TEXT    NOT NULL,
    reorder_level  REAL    NOT NULL
);

-- Two restaurants can both have a dish called PAE01, so the code is unique per restaurant
CREATE TABLE IF NOT EXISTS menu_items (
    restaurant_id  INTEGER NOT NULL,
    code           TEXT    NOT NULL,
    name           TEXT    NOT NULL,
    category       TEXT    NOT NULL CHECK (category IN ({_CATEGORY_LIST})),
    price          REAL    NOT NULL CHECK (price > 0),
    PRIMARY KEY (restaurant_id, code)
);

CREATE TABLE IF NOT EXISTS recipes (
    restaurant_id  INTEGER NOT NULL,
    item_code      TEXT    NOT NULL,
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id),
    quantity       REAL    NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (restaurant_id, item_code, ingredient_id),
    FOREIGN KEY (restaurant_id, item_code) REFERENCES menu_items (restaurant_id, code)
);

CREATE TABLE IF NOT EXISTS purchases (
    id             INTEGER PRIMARY KEY,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(id),
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id),
    quantity       REAL    NOT NULL CHECK (quantity > 0),
    unit_price     REAL    NOT NULL CHECK (unit_price >= 0),
    received_on    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS fixed_expenses (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL,
    description    TEXT    NOT NULL,
    amount         REAL    NOT NULL CHECK (amount > 0),
    month          TEXT    NOT NULL
);

-- Supplier and ingredient names are unique within a restaurant, regardless of case
-- ("Chicken" and "chicken" are the same). Two restaurants can each have their own "Chicken".
CREATE UNIQUE INDEX IF NOT EXISTS suppliers_name_per_restaurant ON suppliers (restaurant_id, name COLLATE NOCASE);
CREATE UNIQUE INDEX IF NOT EXISTS ingredients_name_per_restaurant ON ingredients (restaurant_id, name COLLATE NOCASE);
"""

# Wage costs received from the personnel service, kept to show when it does not answer (ADR-6, ADR-7).
# It is a copy of what personnel answered, with the time it answered; sales never reads personnel's tables.
WAGES_SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS labor_cost_snapshots (
    restaurant_id  INTEGER NOT NULL,
    period_start   TEXT    NOT NULL,
    period_end     TEXT    NOT NULL,
    labor_cost     REAL    NOT NULL,
    fetched_at     TEXT    NOT NULL,
    PRIMARY KEY (restaurant_id, period_start, period_end)
);
"""