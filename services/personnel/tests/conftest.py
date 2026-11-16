"""Shared test fixtures: every test gets its own throw-away database and a known token secret."""
import pytest
from fastapi.testclient import TestClient

import config
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from accounts.tables import ACCOUNTS_SCHEMA
from database import get_connection, init_db
from domain.tables import PERSONNEL_SCHEMA

TEST_SECRET = "test-secret-only-used-by-the-tests-0123456789"


@pytest.fixture(autouse=True)
def token_secret(monkeypatch):
    """Every test signs and checks tokens with the same known secret."""
    monkeypatch.setattr(config, "TOKEN_SECRET", TEST_SECRET)


@pytest.fixture
def conn():
    """An empty in-memory database with all the tables of the personnel service."""
    connection = get_connection(":memory:")
    init_db(connection, [ACCOUNTS_SCHEMA, PERSONNEL_SCHEMA])
    yield connection
    connection.close()


@pytest.fixture
def visitor(tmp_path, monkeypatch):
    """The whole service on a temporary data folder with the demo data, used by someone not logged in."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app

    with TestClient(app.app) as test_client:
        yield test_client


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