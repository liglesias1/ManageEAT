"""Shared test fixtures: a SQL Server test database, a known token secret, and a stub in place of the sales service.

The tests run against SQL Server, the same engine as the service (§5: tests use a SQL Server container, never
Azure SQL). At the start of the session they create the database personnel_test on that server, apply the
real migrations to it, and drop it at the end. Before every test all its tables are emptied, so every test
starts from the same empty database; the ones that need the demo data get it from the app's own seed.

The server comes from TEST_SQLSERVER_URL, an administrator login that can create databases, e.g.
mssql://sa:<password>@localhost:1433/master. If it is not set (on your machine), it is built from
MSSQL_SA_PASSWORD in the repository's .env, for the SQL Server of `docker compose up -d sqlserver`.

The tests never need sales running: `sales` replaces it with an httpx MockTransport, a fake that answers
like the real endpoint (or fails like a stopped service), so each test chooses what sales does.
"""
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
import pymssql
import pytest
from fastapi.testclient import TestClient

import config
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from database import get_connection, parse_url
from domain.demand import COVERS_PATH, sales_client
from migrations import apply_migrations

REPO_ROOT = Path(__file__).resolve().parents[3]      # services/personnel/tests/conftest.py -> the repository
TEST_DATABASE = "personnel_test"
# Every table of the service, children before parents, so emptying them never breaks a foreign key
TABLES = ["clock_ins", "employees", "roles", "demand_snapshots", "users", "restaurants"]

TEST_SECRET = "test-secret-only-used-by-the-tests-0123456789"

# What the stub answers: the 28 demo days, each with 20 diners at 13h, 40 at 14h and 30 at 21h
DEMO_DAYS = [(date(2026, 9, 1) + timedelta(days=offset)).isoformat() for offset in range(28)]
COVERS_PER_HOUR = {13: 20, 14: 40, 21: 30}
DEMAND = {
    "covers": [{"day": day, "hour": hour, "covers": covers} for day in DEMO_DAYS for hour, covers in COVERS_PER_HOUR.items()],
    "open_days": DEMO_DAYS,
}


class SalesStub:
    """What the fake sales service does: answer, be stopped, time out or answer an error."""

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
        assert request.url.path == COVERS_PATH
        return httpx.Response(200, json=DEMAND)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle), base_url="http://sales")


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
    """Creates personnel_test with the real migrations, points the service at it, and drops it at the end."""
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
    """Every test signs and checks tokens with the same known secret."""
    monkeypatch.setattr(config, "TOKEN_SECRET", TEST_SECRET)


@pytest.fixture
def conn(test_database):
    """A connection to the empty test database. What a test does not commit is undone when it closes."""
    db = get_connection(test_database)
    yield db
    db.close()


@pytest.fixture
def sales():
    return SalesStub()


@pytest.fixture
def visitor(sales):
    """The whole service on the test database, which its startup fills with the demo data, with the stub as sales."""
    import app

    app.app.dependency_overrides[sales_client] = sales.client
    with TestClient(app.app) as test_client:
        yield test_client
    app.app.dependency_overrides.clear()


def log_in(visitor, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    """Logs in through the real endpoint and returns the headers that prove it."""
    response = visitor.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def client(visitor):
    """The service as used by the demo manager: every request carries their token."""
    visitor.headers.update(log_in(visitor))
    return visitor