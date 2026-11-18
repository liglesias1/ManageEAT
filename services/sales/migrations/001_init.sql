-- 001: the schema of the sales service at the split (ADR-6, ADR-7).
-- The orders recorded by the POS, the menu and its recipes, ingredients, suppliers, purchases, fixed
-- expenses, and the last wage costs received from personnel. Ported from SQLite: INTEGER PRIMARY KEY ->
-- INT IDENTITY, TEXT -> NVARCHAR, dates as DATE or DATETIME2, money as DECIMAL, quantities as FLOAT.
-- Text comparisons ignore upper and lower case, because the database's default collation does
-- (SQL_Latin1_General_CP1_CI_AS, the default both in the local container and in Azure SQL), which replaces
-- SQLite's COLLATE NOCASE.
-- restaurant_id is a plain number with no foreign key: the restaurants table belongs to personnel (ADR-7).

-- ---------- Orders, as the POS records them ----------

CREATE TABLE orders (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT          NOT NULL,
    table_no       INT          NOT NULL,
    covers         INT          NOT NULL,
    created_at     DATETIME2(0) NOT NULL
);

CREATE TABLE order_items (
    id          INT IDENTITY(1, 1) PRIMARY KEY,
    order_id    INT           NOT NULL REFERENCES orders (id),
    item_code   NVARCHAR(10)  NOT NULL,
    quantity    INT           NOT NULL,
    unit_price  DECIMAL(8, 2) NOT NULL
);

-- Every page filters the orders by restaurant and date; the items are always read through their order
CREATE INDEX orders_by_restaurant ON orders (restaurant_id, created_at);
CREATE INDEX order_items_by_order ON order_items (order_id);

-- ---------- Suppliers and ingredients ----------

CREATE TABLE suppliers (
    id              INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id   INT           NOT NULL,
    name            NVARCHAR(80)  NOT NULL,
    phone           NVARCHAR(30)  NULL,
    email           NVARCHAR(120) NULL,
    lead_time_days  INT           NOT NULL,
    CONSTRAINT suppliers_need_a_contact CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

CREATE TABLE ingredients (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT            NOT NULL,
    name           NVARCHAR(60)   NOT NULL,
    unit           NVARCHAR(10)   NOT NULL,
    unit_cost      DECIMAL(10, 2) NOT NULL,
    supplier_id    INT            NOT NULL REFERENCES suppliers (id),
    counted_stock  FLOAT          NOT NULL,
    counted_at     DATE           NOT NULL,
    reorder_level  FLOAT          NOT NULL
);

-- Supplier and ingredient names are unique within a restaurant, regardless of case (the collation ignores
-- it, so "Chicken" and "chicken" clash). Two restaurants can each have their own "Chicken".
CREATE UNIQUE INDEX suppliers_name_per_restaurant ON suppliers (restaurant_id, name);
CREATE UNIQUE INDEX ingredients_name_per_restaurant ON ingredients (restaurant_id, name);

-- ---------- Menu and recipes ----------

-- The categories must match CATEGORIES in domain/schemas.py; test_rules.py checks that they do.
-- Two restaurants can both have a dish called PAE01, so the code is unique per restaurant.
CREATE TABLE menu_items (
    restaurant_id  INT           NOT NULL,
    code           NVARCHAR(10)  NOT NULL,
    name           NVARCHAR(60)  NOT NULL,
    category       NVARCHAR(10)  NOT NULL CHECK (category IN ('main', 'starter', 'dessert', 'drink')),
    price          DECIMAL(8, 2) NOT NULL CHECK (price > 0),
    PRIMARY KEY (restaurant_id, code)
);

CREATE TABLE recipes (
    restaurant_id  INT          NOT NULL,
    item_code      NVARCHAR(10) NOT NULL,
    ingredient_id  INT          NOT NULL REFERENCES ingredients (id),
    quantity       FLOAT        NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (restaurant_id, item_code, ingredient_id),
    FOREIGN KEY (restaurant_id, item_code) REFERENCES menu_items (restaurant_id, code)
);

-- ---------- Purchases and fixed expenses ----------

CREATE TABLE purchases (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    supplier_id    INT            NOT NULL REFERENCES suppliers (id),
    ingredient_id  INT            NOT NULL REFERENCES ingredients (id),
    quantity       FLOAT          NOT NULL CHECK (quantity > 0),
    unit_price     DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
    received_on    DATE           NOT NULL
);

CREATE TABLE fixed_expenses (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT            NOT NULL,
    description    NVARCHAR(80)   NOT NULL,
    amount         DECIMAL(10, 2) NOT NULL CHECK (amount > 0),
    month          CHAR(7)        NOT NULL
);

-- ---------- Copy of what personnel answered ----------
-- The last wage cost received for each period, and when it was received (ISO text).

CREATE TABLE labor_cost_snapshots (
    restaurant_id  INT            NOT NULL,
    period_start   DATE           NOT NULL,
    period_end     DATE           NOT NULL,
    labor_cost     DECIMAL(12, 2) NOT NULL,
    fetched_at     NVARCHAR(40)   NOT NULL,
    PRIMARY KEY (restaurant_id, period_start, period_end)
);