"""Shared test fixtures: a throw-away database, valid tokens, and a stub in place of the personnel service.

The tests never need personnel running: `personnel` replaces it with an httpx MockTransport, a fake that
answers like the real endpoint (or fails like a stopped service), so each test chooses what personnel does.
"""
from datetime import date, datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

import config
from database import get_connection, init_db
from domain.tables import SALES_SCHEMA, WAGES_SNAPSHOT_SCHEMA
from domain.wages import LABOR_COST_PATH, personnel_client

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


@pytest.fixture(autouse=True)
def token_secret(monkeypatch):
    monkeypatch.setattr(config, "TOKEN_SECRET", TEST_SECRET)


@pytest.fixture
def conn():
    """An empty in-memory database with all the tables of the sales service."""
    connection = get_connection(":memory:")
    init_db(connection, [SALES_SCHEMA, WAGES_SNAPSHOT_SCHEMA])
    yield connection
    connection.close()


@pytest.fixture
def personnel():
    return PersonnelStub()


@pytest.fixture
def visitor(tmp_path, monkeypatch, personnel):
    """The whole service on a temporary data folder with the demo data, with the stub as personnel."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
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