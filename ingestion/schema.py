#ponemos todo el SQL en una variable de texto de Python (input_schema) para que app.py la importe  y se la pase a init_db, que la sabe ejecutar
# orders: cada comanda
#orders_items:contenidos de la comanda
# clock_ins: fichajes, quien ficho y a que hora entro/salio


"""Input data produced by the restaurant's existing systems (POS and clock-in app).

ManageEAT only READS these tables. They belong to neither domain: both the sales
and the personnel domain read them, and neither writes to them.
"""

INPUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    table_no    INTEGER NOT NULL,
    covers      INTEGER NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items ( 
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    item_code   TEXT    NOT NULL,
    quantity    INTEGER NOT NULL,
    unit_price  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS clock_ins ( 
    id           INTEGER PRIMARY KEY,
    employee_id  INTEGER NOT NULL,
    clock_in     TEXT    NOT NULL,
    clock_out    TEXT    NOT NULL
);
"""