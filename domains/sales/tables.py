"""SQL that creates the tables owned by the sales domain (menu items, ingredients, recipes, suppliers, purchases, fixed expenses).

Every table that is read on its own has a restaurant_id. Purchases belong to the restaurant of their
supplier, so they are always read through it.
"""

from domains.sales.schemas import CATEGORIES

_CATEGORY_LIST = ", ".join(f"'{c}'" for c in CATEGORIES)   # 'main', 'starter', 'dessert', 'drink'

SALES_SCHEMA = f"""
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