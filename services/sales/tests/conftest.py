"""Shared test fixtures: a SQL Server test database, valid tokens, and a stub in place of the personnel service.

The tests run against SQL Server, the same engine as the service (§5: tests use a SQL Server container, never
Azure SQL). At the start of the session they create the database sales_test on that server, apply the real
migrations to it, and drop it at the end. Before every test all its tables are emptied, so every test starts
from the same empty database; the ones that need the demo data get it from the app's own seed.

The server comes from TEST_SQLSERVER_URL, an administrator login that can create databases, e.g.
mssql://sa:<password>@localhost:1433/master. If it is not set (on your machine), it is built from
MSSQL_SA_PASSWORD in the repository's .env, for the SQL Server of `docker compose up -d sqlserver`.

The tests never need personnel running: `personnel` replaces it with an httpx MockTransport, a fake that
answers like the real endpoint (or fails like a stopped service), so each test chooses what personnel does.
"""
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
import jwt
import pymssql
import pytest
from fastapi.testclient import TestClient

import config
from database import get_connection, parse_url
from domain.wages import LABOR_COST_PATH, personnel_client
from migrations import apply_migrations

REPO_ROOT = Path(__file__).resolve().parents[3]      # services/sales/tests/conftest.py -> the repository
TEST_DATABASE = "sales_test"
# Every table of the service, children before parents, so emptying them never breaks a foreign key
TABLES = ["order_items", "orders", "recipes", "menu_items", "purchases", "ingredients", "suppliers",
          "fixed_expenses", "labor_cost_snapshots"]

TEST_SECRET = "test-secret-only-used-by-the-tests-0123456789"
DAILY_WAGES = 100.0      # the stub's wage cost per day, so expected figures are easy to work out


def make_token(restaurant_id=1, minutes=15, secret=TEST_SECRET, **extra):
    """A token like the ones personnel signs at login."""
    now = datetime.now(timezone.utc)
    claims = {"sub": "1", "restaurant_id": restaurant_id, "iat": now, "exp": now + timedelta(minutes=minutes), **extra}
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(restaurant_id=1):
    return {"Authorization": f"Bearer {make_token(restaurant_id)}"}


class PersonnelStub:
    """What the fake personnel service does: answer, be stopped, time out or answer an error."""

    def __init__(self):
        self.mode = "up"
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if self.mode == "slow":
            raise httpx.ReadTimeout("timed out", request=request)
        if self.mode == "error":
            return httpx.Response(500, json={"detail": "Internal Server Error"})
        assert request.url.path == LABOR_COST_PATH
        start = date.fromisoformat(request.url.params["start"])
        end = date.fromisoformat(request.url.params["end"])
        days = (end - start).days + 1
        return httpx.Response(200, json={"start": str(start), "end": str(end), "labor_cost": days * DAILY_WAGES})

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle), base_url="http://personnel")


# ---------- The test database ----------

def _from_env_file(name):
    """A value from the repository's .env (KEY=value lines), or None."""
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name and value.strip():
                return value.strip()
    return None


def _server_url():
    url = os.getenv("TEST_SQLSERVER_URL")
    if url:
        return url
    password = os.getenv("MSSQL_SA_PASSWORD") or _from_env_file("MSSQL_SA_PASSWORD")
    if not password:
        pytest.exit("The tests need SQL Server: start it with `docker compose up -d sqlserver` and set "
                    "MSSQL_SA_PASSWORD in .env, or set TEST_SQLSERVER_URL", returncode=1)
    return f"mssql://sa:{quote(password, safe='')}@localhost:1433/master"


def _drop(cursor):
    cursor.execute(f"""
        IF DB_ID('{TEST_DATABASE}') IS NOT NULL
        BEGIN
            ALTER DATABASE {TEST_DATABASE} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
            DROP DATABASE {TEST_DATABASE};
        END
    """)


@pytest.fixture(scope="session")
def test_database():
    """Creates sales_test with the real migrations, points the service at it, and drops it at the end."""
    server = parse_url(_server_url())
    admin = pymssql.connect(**server, autocommit=True)      # CREATE DATABASE cannot run inside a transaction
    cursor = admin.cursor()
    _drop(cursor)                                            # a run that was interrupted may have left it
    cursor.execute(f"CREATE DATABASE {TEST_DATABASE}")
    url = (f"mssql://{quote(server['user'], safe='')}:{quote(server['password'], safe='')}"
           f"@{server['server']}:{server['port']}/{TEST_DATABASE}")
    config.DATABASE_URL = url
    db = get_connection(url)
    apply_migrations(db)
    db.close()
    yield url
    _drop(cursor)
    admin.close()


@pytest.fixture(autouse=True)
def empty_tables(test_database):
    """Every test starts from the migrated schema with no rows."""
    db = get_connection(test_database)
    with db:
        for table in TABLES:
            db.execute(f"DELETE FROM {table}")
    db.close()


@pytest.fixture(autouse=True)
def token_secret(monkeypatch):
    monkeypatch.setattr(config, "TOKEN_SECRET", TEST_SECRET)


@pytest.fixture
def conn(test_database):
    """A connection to the empty test database. What a test does not commit is undone when it closes."""
    db = get_connection(test_database)
    yield db
    db.close()


@pytest.fixture
def personnel():
    return PersonnelStub()


@pytest.fixture
def visitor(personnel):
    """The whole service on the test database, which its startup fills with the demo data, with the stub as personnel."""
    import app

    app.app.dependency_overrides[personnel_client] = personnel.client
    with TestClient(app.app) as test_client:
        yield test_client
    app.app.dependency_overrides.clear()


@pytest.fixture
def client(visitor):
    """The service as used by a manager of the demo restaurant (restaurant 1)."""
    visitor.headers.update(bearer(1))
    return visitor


@pytest.fixture
def db(client):
    """A connection to the database the running service uses, to check what the API saved."""
    connection = get_connection()
    yield connection
    connection.close()
