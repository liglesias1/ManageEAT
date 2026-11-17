"""The flow of personnel that crosses the seam: the schedule with covers from sales, and what happens when it fails.

sales is the stub from conftest.py: it answers DEMAND (20, 40 and 30 diners at 13h, 14h and 21h every day of
the demo period), or fails the way the test chooses.
"""
import json

import httpx
import pytest

from domain import repository
from domain.demand import Demand
from tests.conftest import DEMAND, SalesStub


def demand_with(stub, conn, restaurant_id=1):
    return Demand(stub.client(), "abc", conn, restaurant_id)


# ---------- Demand, on its own ----------

def test_demand_asks_sales_with_the_managers_token_and_keeps_a_snapshot(conn):
    stub = SalesStub()
    demand = demand_with(stub, conn)
    assert demand.get() == DEMAND
    assert stub.requests[0].headers["Authorization"] == "Bearer abc"
    assert demand.report() == {"source": "live"}
    payload, fetched_at = repository.get_demand_snapshot(conn, 1)
    assert json.loads(payload) == DEMAND and fetched_at


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_when_sales_fails_the_last_covers_received_are_used_with_their_date(conn, mode):
    repository.save_demand(conn, 1, json.dumps(DEMAND), "2026-11-15T20:00:00+00:00")
    stub = SalesStub()
    stub.mode = mode
    demand = demand_with(stub, conn)
    assert demand.get() == DEMAND
    assert demand.report() == {"source": "snapshot", "as_of": "2026-11-15T20:00:00+00:00"}


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_without_a_snapshot_the_demand_is_unavailable(conn, mode):
    stub = SalesStub()
    stub.mode = mode
    demand = demand_with(stub, conn)
    assert demand.get() is None
    assert demand.report() == {"source": "unavailable"}


def test_a_live_answer_replaces_the_old_snapshot(conn):
    repository.save_demand(conn, 1, json.dumps({"covers": [], "open_days": []}), "2026-11-15T20:00:00+00:00")
    demand_with(SalesStub(), conn).get()
    payload, fetched_at = repository.get_demand_snapshot(conn, 1)
    assert json.loads(payload) == DEMAND and fetched_at > "2026-11-15T20:00:00+00:00"


def test_each_restaurant_only_uses_its_own_snapshot(conn):
    repository.save_demand(conn, 1, json.dumps(DEMAND), "2026-11-15T20:00:00+00:00")
    stub = SalesStub()
    stub.mode = "down"
    demand = demand_with(stub, conn, restaurant_id=2)
    assert demand.get() is None


@pytest.mark.parametrize("answer", [
    {"covers": "lots"},                                                    # open_days missing
    {"covers": "lots", "open_days": []},                                   # not a list
    {"covers": [{"day": "2026-09-01", "covers": 3}], "open_days": []},     # a row without hour
])
def test_an_answer_without_the_agreed_shape_counts_as_a_failure_and_is_not_saved(conn, answer):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=answer)),
                          base_url="http://sales")
    demand = Demand(client, "abc", conn, 1)
    assert demand.get() is None
    assert repository.get_demand_snapshot(conn, 1) is None


# ---------- The schedule through the API ----------

def test_the_schedule_compares_recommended_and_actual_staff_with_covers_from_sales(client, sales):
    body = client.get("/personnel/schedule").json()
    assert body["demand"] == {"source": "live"}
    assert body["hours"] == [13, 14, 21]
    assert body["max_covers"] == 40
    assert body["roles"] == ["Waiter", "Runner", "Bar", "Pass", "Cook", "Dishwasher"]
    friday_14h = next(slot for slot in body["by_day"]["Friday"] if slot["hour"] == 14)
    waiter = next(role for role in friday_14h["roles"] if role["role"] == "Waiter")
    assert waiter["needed"] == 2                              # 40 diners / 30 per waiter, rounded up
    assert body["summary"]["peak"]["covers"] == 40
    assert sales.requests[0].headers["Authorization"] == client.headers["Authorization"]


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_when_sales_stops_the_schedule_uses_the_last_covers_received(client, sales, mode):
    live = client.get("/personnel/schedule").json()
    sales.mode = mode
    response = client.get("/personnel/schedule")
    assert response.status_code == 200                        # designed failure, not a 500
    body = response.json()
    assert body["demand"]["source"] == "snapshot" and body["demand"]["as_of"]
    assert body["by_day"] == live["by_day"] and body["summary"] == live["summary"]


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_without_sales_or_a_snapshot_the_schedule_is_empty_but_answers(client, sales, mode):
    sales.mode = mode                                         # sales never answered
    response = client.get("/personnel/schedule")
    assert response.status_code == 200
    body = response.json()
    assert body["demand"] == {"source": "unavailable"}
    assert body["heatmap"] == [] and body["summary"] is None
    assert all(slots == [] for slots in body["by_day"].values())
    assert len(body["roles"]) == 6                            # personnel's own data is still there


def test_payroll_and_labor_cost_never_need_sales(client, sales):
    sales.mode = "down"
    assert client.get("/personnel/payroll").status_code == 200
    assert client.get("/personnel/labor-cost", params={"start": "2026-09-01", "end": "2026-09-28"}).json()["labor_cost"] > 0
    assert sales.requests == []


def test_the_summary_without_sales_or_a_snapshot_still_answers(client, sales):
    sales.mode = "down"
    summary = client.get("/personnel/summary").json()
    assert summary["demand"] == {"source": "unavailable"}
    assert summary["schedule"] is None and summary["employees"] == 16