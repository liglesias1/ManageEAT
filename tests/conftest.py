"""Shared test fixtures: every test gets its own throw-away database."""
import pytest
from fastapi.testclient import TestClient

import config
from accounts.dependencies import current_restaurant
from accounts.seed import DEMO_RESTAURANT_ID
from accounts.tables import ACCOUNTS_SCHEMA
from database import get_connection, init_db
from domains.sales.tables import SALES_SCHEMA
from domains.personnel.tables import PERSONNEL_SCHEMA
from ingestion.schema import INPUT_SCHEMA


@pytest.fixture
def conn():
    """An empty in-memory database with all the tables created."""
    connection = get_connection(":memory:")
    init_db(connection, [ACCOUNTS_SCHEMA, INPUT_SCHEMA, SALES_SCHEMA, PERSONNEL_SCHEMA])
    yield connection
    connection.close()


@pytest.fixture
def visitor(tmp_path, monkeypatch):
    """The whole app on a temporary data folder with the demo data, used by someone who is not logged in."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app

    with TestClient(app.app) as test_client:
        yield test_client


@pytest.fixture
def client(visitor):
    """The app as seen by a manager of the demo restaurant.

    The page tests check what each page shows, not the login, so the restaurant is given directly
    instead of logging in before every test (the login itself is tested in tests/accounts).
    """
    import app

    app.app.dependency_overrides[current_restaurant] = lambda: DEMO_RESTAURANT_ID
    yield visitor
    app.app.dependency_overrides.clear()