"""Shared test fixtures: every test gets its own throw-away database."""
import pytest
from fastapi.testclient import TestClient

import config
from database import get_connection, init_db
from domains.sales.tables import SALES_SCHEMA
from domains.personnel.tables import PERSONNEL_SCHEMA
from ingestion.schema import INPUT_SCHEMA


@pytest.fixture
def conn():
    """An empty in-memory database with all the tables created."""
    connection = get_connection(":memory:")
    init_db(connection, [INPUT_SCHEMA, SALES_SCHEMA, PERSONNEL_SCHEMA])
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The whole app, started on a temporary data folder with the demo data."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app

    with TestClient(app.app) as test_client:
        yield test_client