"""The flow that crosses the seam: profit and loss with wages from personnel, and what happens when it fails.

personnel is the stub from conftest.py: it answers DAILY_WAGES per day, or fails the way the test chooses.
"""
import httpx
import pytest

from domain import repository
from domain.wages import Wages
from tests.conftest import DAILY_WAGES, PersonnelStub

WEEK = ("2026-09-01", "2026-09-07")


def wages_with(stub, conn, restaurant_id=1):
    return Wages(stub.client(), "abc", conn, restaurant_id)


# ---------- Wages, on its own ----------

def test_wages_asks_personnel_with_the_managers_token_and_keeps_a_snapshot(conn):
    stub = PersonnelStub()
    wages = wages_with(stub, conn)
    assert wages.labor_cost_for(*WEEK) == 7 * DAILY_WAGES
    assert stub.requests[0].headers["Authorization"] == "Bearer abc"
    assert wages.report() == {"source": "live"}
    cost, fetched_at = repository.get_labor_cost_snapshot(conn, 1, *WEEK)
    assert cost == 7 * DAILY_WAGES and fetched_at


def test_the_same_period_is_asked_only_once(conn):
    stub = PersonnelStub()
    wages = wages_with(stub, conn)
    wages.labor_cost_for(*WEEK)
    wages.labor_cost_for(*WEEK)
    assert len(stub.requests) == 1


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_when_personnel_fails_the_last_wages_received_are_used_with_their_date(conn, mode):
    repository.save_labor_cost(conn, 1, *WEEK, 555.0, "2026-11-15T20:00:00+00:00")
    stub = PersonnelStub()
    stub.mode = mode
    wages = wages_with(stub, conn)
    assert wages.labor_cost_for(*WEEK) == 555.0
    assert wages.report() == {"source": "snapshot", "as_of": "2026-11-15T20:00:00+00:00"}


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_without_a_snapshot_the_wages_are_unavailable(conn, mode):
    stub = PersonnelStub()
    stub.mode = mode
    wages = wages_with(stub, conn)
    assert wages.labor_cost_for(*WEEK) == 0
    assert wages.report() == {"source": "unavailable"}


def test_after_one_failure_personnel_is_not_asked_again_in_the_same_request(conn):
    stub = PersonnelStub()
    stub.mode = "slow"
    wages = wages_with(stub, conn)
    wages.labor_cost_for("2026-09-01", "2026-09-07")
    wages.labor_cost_for("2026-09-08", "2026-09-14")
    assert len(stub.requests) == 1                     # so a page never waits the timeout more than once


def test_a_live_answer_replaces_the_old_snapshot(conn):
    repository.save_labor_cost(conn, 1, *WEEK, 555.0, "2026-11-15T20:00:00+00:00")
    wages_with(PersonnelStub(), conn).labor_cost_for(*WEEK)
    cost, fetched_at = repository.get_labor_cost_snapshot(conn, 1, *WEEK)
    assert cost == 7 * DAILY_WAGES and fetched_at > "2026-11-15T20:00:00+00:00"


def test_the_oldest_snapshot_used_is_reported(conn):
    repository.save_labor_cost(conn, 1, "2026-09-01", "2026-09-07", 1.0, "2026-11-15T20:00:00+00:00")
    repository.save_labor_cost(conn, 1, "2026-09-08", "2026-09-14", 2.0, "2026-11-10T08:00:00+00:00")
    stub = PersonnelStub()
    stub.mode = "down"
    wages = wages_with(stub, conn)
    wages.labor_cost_for("2026-09-01", "2026-09-07")
    wages.labor_cost_for("2026-09-08", "2026-09-14")
    assert wages.report() == {"source": "snapshot", "as_of": "2026-11-10T08:00:00+00:00"}


def test_each_restaurant_only_uses_its_own_snapshots(conn):
    repository.save_labor_cost(conn, 1, *WEEK, 555.0, "2026-11-15T20:00:00+00:00")
    stub = PersonnelStub()
    stub.mode = "down"
    wages = wages_with(stub, conn, restaurant_id=2)
    wages.labor_cost_for(*WEEK)
    assert wages.report() == {"source": "unavailable"}


def test_an_answer_without_the_agreed_shape_counts_as_a_failure(conn):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"cost": 1})),
                          base_url="http://personnel")
    wages = Wages(client, "abc", conn, 1)
    wages.labor_cost_for(*WEEK)
    assert wages.report() == {"source": "unavailable"}
    assert repository.get_labor_cost_snapshot(conn, 1, *WEEK) is None     # nothing wrong is ever saved


# ---------- Profit and loss through the API ----------

def test_profit_and_loss_opens_on_the_last_month_with_sales_with_wages_from_personnel(client, personnel):
    body = client.get("/sales/profit-loss").json()
    assert body["month"] == "2026-09"
    assert body["wages"] == {"source": "live"}
    pl = body["pl"]
    assert pl["labor"] == 28 * DAILY_WAGES                              # 2026-09-01 to 2026-09-28
    assert pl["net_profit"] == pytest.approx(pl["revenue"] - pl["ingredients"] - pl["labor"] - pl["fixed"])
    assert "Electricity and water" in [e["description"] for e in body["expenses"]]
    assert personnel.requests[0].headers["Authorization"] == client.headers["Authorization"]


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_when_personnel_stops_the_statement_shows_the_last_wages_received(client, personnel, mode):
    live = client.get("/sales/profit-loss").json()
    personnel.mode = mode
    response = client.get("/sales/profit-loss")
    assert response.status_code == 200                                  # designed failure, not a 500
    body = response.json()
    assert body["wages"]["source"] == "snapshot" and body["wages"]["as_of"]
    assert body["pl"] == live["pl"] and body["history"] == live["history"]


@pytest.mark.parametrize("mode", ["down", "slow", "error"])
def test_without_personnel_or_snapshots_the_statement_keeps_what_sales_knows(client, personnel, mode):
    personnel.mode = mode                                               # personnel never answered
    response = client.get("/sales/profit-loss")
    assert response.status_code == 200
    body = response.json()
    assert body["wages"] == {"source": "unavailable"}
    pl = body["pl"]
    assert pl["revenue"] > 0 and pl["ingredients"] > 0 and pl["fixed"] > 0
    assert pl["labor"] is None and pl["net_profit"] is None and pl["net_margin_pct"] is None
    assert all(week["labor"] is None and week["profit"] is None for week in pl["weeks"])
    assert all(row["net_profit"] is None for row in body["history"])


def test_a_month_without_data_can_still_be_navigated(client):
    body = client.get("/sales/profit-loss", params={"month": "2026-07"}).json()
    assert body["has_data"] is False
    assert (body["prev_month"], body["next_month"]) == ("2026-06", "2026-08")


def test_a_malformed_month_falls_back_to_the_default(client):
    assert client.get("/sales/profit-loss", params={"month": "banana"}).json()["month"] == "2026-09"


def test_history_lists_every_month_with_data(client):
    client.post("/sales/expenses", json={"description": "Summer rent", "amount": 3200, "month": "2026-08"})
    history = client.get("/sales/profit-loss", params={"month": "2026-09"}).json()["history"]
    assert [row["month"] for row in history] == ["2026-09", "2026-08"]


# ---------- The overview ----------

def test_the_summary_matches_the_profit_and_loss(client):
    summary = client.get("/sales/summary").json()
    statement = client.get("/sales/profit-loss").json()
    assert summary["month"] == statement["month"]
    assert summary["pl"] == statement["pl"]
    assert summary["menu"] and summary["inventory"]


def test_the_summary_without_personnel_or_snapshots_still_answers(client, personnel):
    personnel.mode = "down"
    summary = client.get("/sales/summary").json()
    assert summary["wages"] == {"source": "unavailable"}
    assert summary["pl"]["net_profit"] is None and summary["pl"]["revenue"] > 0