"""Integration test across the seam: both real services running, talking to each other over HTTP.

The unit tests of each service replace the other one with a stub, which checks each side on its own. This
test checks that the two sides really fit: a token signed by personnel is accepted by sales, and each
service gets from the other the same figures the other calculates itself.

It needs both services running and their URLs in the environment, and is skipped otherwise:

    PERSONNEL_URL=http://localhost:8001 SALES_URL=http://localhost:8000 python -m pytest tests/integration

Locally the services run with `docker compose up` (or by hand); in CI, against the compose stack.
"""
import os

import httpx
import pytest

PERSONNEL_URL = os.getenv("PERSONNEL_URL")
SALES_URL = os.getenv("SALES_URL")

pytestmark = pytest.mark.skipif(not (PERSONNEL_URL and SALES_URL),
                                reason="set PERSONNEL_URL and SALES_URL to run against running services")

DEMO = {"email": "demo@manageeat.com", "password": "demo1234"}
TIMEOUT_S = 60          # generous: on a first request the services may be starting and the databases resuming


@pytest.fixture(scope="module")
def headers():
    """Logs in once through the real personnel service."""
    response = httpx.post(f"{PERSONNEL_URL}/auth/login", json=DEMO, timeout=TIMEOUT_S)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def get(base_url, path, headers, **params):
    response = httpx.get(f"{base_url}{path}", headers=headers, params=params, timeout=TIMEOUT_S)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    return response.json()


def test_both_services_are_healthy():
    for base_url in (PERSONNEL_URL, SALES_URL):
        assert httpx.get(f"{base_url}/health", timeout=TIMEOUT_S).status_code == 200


def test_sales_accepts_the_token_personnel_signed(headers):
    get(SALES_URL, "/sales/menu", headers)


def test_profit_and_loss_gets_the_wage_cost_personnel_calculates(headers):
    statement = get(SALES_URL, "/sales/profit-loss", headers)
    assert statement["wages"] == {"source": "live"}
    wages = get(PERSONNEL_URL, "/personnel/labor-cost", headers, start=statement["start"], end=statement["end"])
    assert statement["pl"]["labor"] == wages["labor_cost"]


def test_the_schedule_gets_the_covers_sales_records(headers):
    schedule = get(PERSONNEL_URL, "/personnel/schedule", headers)
    assert schedule["demand"] == {"source": "live"}
    covers = get(SALES_URL, "/sales/covers", headers)
    assert schedule["hours"] == sorted({row["hour"] for row in covers["covers"]})