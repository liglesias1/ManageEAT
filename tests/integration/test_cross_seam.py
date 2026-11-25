"""Integration tests across the seam: both real services running, talking to each other over HTTP.

The unit tests of each service replace the other one with a stub, which checks each side on its own. These
tests check that the two sides really fit, against the compose stack:

- a token signed by personnel is accepted by sales;
- each service gets from the other the same figures the other calculates itself;
- a shift recorded in personnel reaches the profit and loss of sales;
- the browser's preflight from the UI's origin is accepted by both;
- with one service stopped, the other keeps serving its own domain and the flow that needs the stopped one
  degrades (snapshot or unavailable) quickly instead of failing or hanging (A2 §3).

They need both services running and their URLs in the environment, and are skipped otherwise:

    docker compose up --build -d
    PERSONNEL_URL=http://localhost:8001 SALES_URL=http://localhost:8002 python -m pytest tests/integration -v

The partial-failure tests stop and start containers with `docker compose`, so they only run when
CAN_STOP_SERVICES=1 is also set (in CI, and on your machine from the repository root). The shift test adds an
employee called "Integration test ..." to the demo restaurant on every run; in CI the database is new each time.
"""
import os
import subprocess
import time
from datetime import datetime

import httpx
import pytest

PERSONNEL_URL = os.getenv("PERSONNEL_URL")
SALES_URL = os.getenv("SALES_URL")
CAN_STOP_SERVICES = os.getenv("CAN_STOP_SERVICES") == "1"
UI_ORIGIN = os.getenv("UI_ORIGIN", "http://localhost:8080")

pytestmark = pytest.mark.skipif(not (PERSONNEL_URL and SALES_URL),
                                reason="set PERSONNEL_URL and SALES_URL to run against running services")
needs_docker = pytest.mark.skipif(not CAN_STOP_SERVICES, reason="set CAN_STOP_SERVICES=1 to stop and start containers")

DEMO = {"email": "demo@manageeat.com", "password": "demo1234"}
TIMEOUT_S = 60          # generous: on a first request the services may be starting and the databases resuming
# With the other service stopped, a page must still answer well within this: the call across the seam has a
# 5 s timeout and is not repeated within a request
DEGRADED_ANSWER_S = 15


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


def compose(*args):
    subprocess.run(["docker", "compose", *args], check=True, capture_output=True)


def wait_until_healthy(base_url, limit_s=90):
    """Waits for a restarted service: it connects to its database and checks its migrations first."""
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise AssertionError(f"{base_url} did not become healthy within {limit_s} s")


def stopped(service, base_url):
    """Context manager: the service is stopped inside the block and healthy again after it, whatever happens."""
    class Stopped:
        def __enter__(self):
            compose("stop", service)

        def __exit__(self, *error):
            compose("start", service)
            wait_until_healthy(base_url)
            return False

    return Stopped()


# ---------- Both services up ----------

def test_both_services_are_healthy():
    for base_url in (PERSONNEL_URL, SALES_URL):
        response = httpx.get(f"{base_url}/health", timeout=TIMEOUT_S)
        assert response.status_code == 200
        assert response.json()["db"] == "ok"


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


def test_a_shift_recorded_in_personnel_reaches_the_profit_and_loss_of_sales(headers):
    month = get(SALES_URL, "/sales/profit-loss", headers)
    before = month["pl"]["labor"]

    name = f"Integration test {datetime.now():%Y%m%d%H%M%S%f}"
    employee = httpx.post(f"{PERSONNEL_URL}/personnel/employees", headers=headers, timeout=TIMEOUT_S,
                          json={"name": name, "role_id": 1})
    assert employee.status_code == 201, employee.text
    rate = next(r["hourly_rate"] for r in get(PERSONNEL_URL, "/personnel/roles", headers) if r["id"] == 1)
    day = month["start"]                                 # a day with sales, so it is inside the statement
    shift = httpx.post(f"{PERSONNEL_URL}/personnel/clock-ins", headers=headers, timeout=TIMEOUT_S, json={
        "employee_id": employee.json()["id"], "clock_in": f"{day}T12:00:00", "clock_out": f"{day}T16:00:00"})
    assert shift.status_code == 201, shift.text

    after = get(SALES_URL, "/sales/profit-loss", headers, month=month["month"])
    assert after["wages"] == {"source": "live"}
    assert after["pl"]["labor"] == pytest.approx(before + 4 * rate, abs=0.01)


@pytest.mark.parametrize("base_url, path", [("PERSONNEL", "/auth/login"), ("SALES", "/sales/dishes")])
def test_both_services_accept_the_ui_origin_and_only_that_one(base_url, path):
    url = (PERSONNEL_URL if base_url == "PERSONNEL" else SALES_URL) + path
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    allowed = httpx.options(url, headers={"Origin": UI_ORIGIN, **preflight}, timeout=TIMEOUT_S)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == UI_ORIGIN
    refused = httpx.options(url, headers={"Origin": "https://evil.example", **preflight}, timeout=TIMEOUT_S)
    assert "access-control-allow-origin" not in refused.headers


# ---------- One service stopped (A2 §3) ----------

@needs_docker
def test_with_personnel_stopped_sales_keeps_working_and_profit_and_loss_degrades(headers):
    get(SALES_URL, "/sales/profit-loss", headers)        # live first, so personnel's answer is saved as a snapshot
    with stopped("personnel", PERSONNEL_URL):
        get(SALES_URL, "/sales/menu", headers)           # its own domain, with the token signed before the stop
        started = time.monotonic()
        statement = get(SALES_URL, "/sales/profit-loss", headers)
        assert time.monotonic() - started < DEGRADED_ANSWER_S
        assert statement["wages"]["source"] in ("snapshot", "unavailable")
        if statement["wages"]["source"] == "snapshot":
            assert statement["wages"]["as_of"]
            assert statement["pl"]["labor"] is not None
        else:
            assert statement["pl"]["net_profit"] is None    # never a profit that silently leaves wages out
        assert httpx.get(f"{SALES_URL}/health", timeout=TIMEOUT_S).status_code == 200   # its health is its own


@needs_docker
def test_with_sales_stopped_personnel_keeps_working_and_the_schedule_degrades(headers):
    get(PERSONNEL_URL, "/personnel/schedule", headers)   # live first, so sales' answer is saved as a snapshot
    with stopped("sales", SALES_URL):
        payroll = get(PERSONNEL_URL, "/personnel/payroll", headers)
        assert payroll["payroll"]
        started = time.monotonic()
        schedule = get(PERSONNEL_URL, "/personnel/schedule", headers)
        assert time.monotonic() - started < DEGRADED_ANSWER_S
        assert schedule["demand"]["source"] in ("snapshot", "unavailable")
        assert httpx.get(f"{PERSONNEL_URL}/health", timeout=TIMEOUT_S).status_code == 200
