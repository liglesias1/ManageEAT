"""SQL that creates the account tables: restaurants, and the users (managers) who log in to them.

A restaurant can have several managers, each with their own email and password, and all of them
see the same restaurant's data. Every table in the other zones has a restaurant_id, but no foreign
key points here: like the links between the data zones (ADR-3), the link is logical, so each domain
can later move to its own database without depending on these tables.
"""

ACCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS restaurants (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY,
    restaurant_id  INTEGER NOT NULL REFERENCES restaurants(id),
    name           TEXT    NOT NULL,
    email          TEXT    NOT NULL,
    password_hash  TEXT    NOT NULL
);

-- An email logs in to exactly one account, whatever the case ("Demo@..." and "demo@..." are the same)
CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (email COLLATE NOCASE);
"""