-- 002: a one-row table that GET /health writes and reads back, to prove the service can still write to its
-- own database with its own login (A2 §3, ADR-9). It holds no business data, and nothing else uses it.
-- The row is created by the first health check (observability.py), so emptying the table does no harm.

CREATE TABLE health_checks (
    id          INT          NOT NULL PRIMARY KEY CHECK (id = 1),
    checked_at  DATETIME2(0) NOT NULL
);