"""SQL that creates the tables owned by the personnel domain (roles, employees), for every restaurant."""

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
"""