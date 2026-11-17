"""Shared test fixtures: a throw-away database, a known token secret, and a stub in place of the sales service.

The tests never need sales running: `sales` replaces it with an httpx MockTransport, a fake that answers
like the real endpoint (or fails like a stopped service), so each test chooses what sales does.
"""
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

import config
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from accounts.tables import ACCOUNTS_SCHEMA
from database import get_connection, init_db
from domain.demand import COVERS_PATH, sales_client
from domain.tables import DEMAND_SNAPSHOT_SCHEMA, PERSONNEL_SCHEMA

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


@pytest.fixture(autouse=True)
def token_secret(monkeypatch):
    """Every test signs and checks tokens with the same known secret."""
    monkeypatch.setattr(config, "TOKEN_SECRET", TEST_SECRET)


@pytest.fixture
def conn():
    """An empty in-memory database with all the tables of the personnel service."""
    connection = get_connection(":memory:")
    init_db(connection, [ACCOUNTS_SCHEMA, PERSONNEL_SCHEMA, DEMAND_SNAPSHOT_SCHEMA])
    yield connection
    connection.close()


@pytest.fixture
def sales():
    return SalesStub()


@pytest.fixture
def visitor(tmp_path, monkeypatch, sales):
    """The whole service on a temporary data folder with the demo data, with the stub as sales."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
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