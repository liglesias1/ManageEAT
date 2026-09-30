"""SQL that creates the tables owned by the sales domain (menu items, ingredients, recipes, suppliers, fixed expenses)."""

SALES_SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    phone           TEXT,
    email           TEXT,
    lead_time_days  INTEGER NOT NULL,
    CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS ingredients (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    unit           TEXT    NOT NULL,
    unit_cost      REAL    NOT NULL,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(id),
    counted_stock  REAL    NOT NULL,
    counted_at     TEXT    NOT NULL,
    reorder_level  REAL    NOT NULL
);


CREATE TABLE IF NOT EXISTS menu_items (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    category  TEXT NOT NULL CHECK (category IN ('starter', 'main', 'dessert', 'drink'))
);

CREATE TABLE IF NOT EXISTS recipes (
    item_code      TEXT    NOT NULL REFERENCES menu_items(code),
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id),
    quantity       REAL    NOT NULL,
    PRIMARY KEY (item_code, ingredient_id)
);

CREATE TABLE IF NOT EXISTS fixed_expenses (
    id           INTEGER PRIMARY KEY,
    description  TEXT NOT NULL,
    amount       REAL NOT NULL CHECK (amount > 0),
    month        TEXT NOT NULL
);
"""