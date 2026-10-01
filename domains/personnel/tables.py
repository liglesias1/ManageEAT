"""SQL that creates the tables owned by the personnel domain (roles, employees)."""

PERSONNEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id                INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL UNIQUE,
    hourly_rate       REAL    NOT NULL CHECK (hourly_rate > 0),
    covers_per_hour   INTEGER NOT NULL CHECK (covers_per_hour > 0),
    min_staff         INTEGER NOT NULL CHECK (min_staff >= 0)
);

CREATE TABLE IF NOT EXISTS employees (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL,
    role_id  INTEGER NOT NULL REFERENCES roles(id)
);
"""