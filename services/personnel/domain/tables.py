"""SQL that creates the tables owned by the personnel service: roles, employees and clock-ins, for every restaurant.

clock_ins used to be shared input read by both domains (ADR-3); since the split only personnel reads it,
so it belongs here (ADR-6). employee_id is not a foreign key because the clock-in system that writes it
is outside ManageEAT, as it was in the monolith.
"""

PERSONNEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id                INTEGER PRIMARY KEY,
    restaurant_id     INTEGER NOT NULL,
    name              TEXT    NOT NULL,
    hourly_rate       REAL    NOT NULL CHECK (hourly_rate > 0),
    covers_per_hour   INTEGER NOT NULL CHECK (covers_per_hour > 0),
    min_staff         INTEGER NOT NULL CHECK (min_staff >= 0),
    UNIQUE (restaurant_id, name)
);

CREATE TABLE IF NOT EXISTS employees (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL,
    name           TEXT    NOT NULL,
    role_id        INTEGER NOT NULL REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS clock_ins (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL,
    employee_id    INTEGER NOT NULL,
    clock_in       TEXT    NOT NULL,
    clock_out      TEXT    NOT NULL
);

-- Payroll and labor cost filter by restaurant and date
CREATE INDEX IF NOT EXISTS clock_ins_by_restaurant ON clock_ins (restaurant_id, clock_in);
"""