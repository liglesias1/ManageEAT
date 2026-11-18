-- 001: the schema of the personnel service at the split (ADR-6, ADR-7).
-- Restaurants and their managers (accounts), roles, employees, clock-ins, and the last covers received
-- from sales. Ported from SQLite: INTEGER PRIMARY KEY -> INT IDENTITY, TEXT -> NVARCHAR, dates as DATE or
-- DATETIME2, money as DECIMAL.
-- Text comparisons ignore upper and lower case, because the database's default collation does
-- (SQL_Latin1_General_CP1_CI_AS, the default both in the local container and in Azure SQL), which replaces
-- SQLite's COLLATE NOCASE.

-- ---------- Accounts ----------

CREATE TABLE restaurants (
    id    INT IDENTITY(1, 1) PRIMARY KEY,
    name  NVARCHAR(80) NOT NULL
);

CREATE TABLE users (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT           NOT NULL REFERENCES restaurants (id),
    name           NVARCHAR(80)  NOT NULL,
    email          NVARCHAR(120) NOT NULL,
    password_hash  NVARCHAR(200) NOT NULL
);

-- An email logs in to exactly one account, whatever the case ("Demo@..." and "demo@..." are the same)
CREATE UNIQUE INDEX users_email_unique ON users (email);

-- ---------- Staff ----------
-- restaurant_id has no foreign key to restaurants on purpose: it keeps the link logical, as ADR-3 did
-- between the data zones, and the sales service stores the same ids without having this table.

CREATE TABLE roles (
    id               INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id    INT          NOT NULL,
    name             NVARCHAR(60) NOT NULL,
    hourly_rate      DECIMAL(8, 2) NOT NULL CHECK (hourly_rate > 0),
    covers_per_hour  INT          NOT NULL CHECK (covers_per_hour > 0),
    min_staff        INT          NOT NULL CHECK (min_staff >= 0),
    CONSTRAINT roles_name_per_restaurant UNIQUE (restaurant_id, name)
);

CREATE TABLE employees (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT          NOT NULL,
    name           NVARCHAR(80) NOT NULL,
    role_id        INT          NOT NULL REFERENCES roles (id)
);

-- employee_id is not a foreign key: the clock-in system that writes this table is outside ManageEAT
CREATE TABLE clock_ins (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    restaurant_id  INT          NOT NULL,
    employee_id    INT          NOT NULL,
    clock_in       DATETIME2(0) NOT NULL,
    clock_out      DATETIME2(0) NOT NULL
);

-- Payroll and labor cost filter by restaurant and date
CREATE INDEX clock_ins_by_restaurant ON clock_ins (restaurant_id, clock_in);

-- ---------- Copy of what sales answered ----------
-- One row per restaurant with sales' whole answer about covers as JSON, and when it answered (ISO text).

CREATE TABLE demand_snapshots (
    restaurant_id  INT           PRIMARY KEY,
    payload        NVARCHAR(MAX) NOT NULL,
    fetched_at     NVARCHAR(40)  NOT NULL
);