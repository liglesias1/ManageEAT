"""Contract test of the seam between sales and personnel (ADR-2).

Sales gets wage costs through domains/sales/wages.py, either by calling personnel's code (in_process) or
by asking its JSON endpoint (over_http). In Assignment 2 the app switches from the first to the second,
so these tests check that the endpoint keeps its shape and that both ways always give the same numbers.
"""
from datetime import date, timedelta

import pytest

from accounts.dependencies import current_restaurant
from accounts.seed import DEMO_RESTAURANT_ID
from database import get_connection
from domains.personnel import repository as personnel_repo
from domains.sales import repository as sales_repo
from domains.sales.services import profit_and_loss
from domains.sales.wages import LABOR_COST_URL, in_process, over_http


@pytest.fixture
def demo_periods(client):
    """Periods to compare: the whole demo payroll, its first week, one day and a day with no shifts."""
    conn = get_connection()
    try:
        first, last = personnel_repo.get_clock_in_period(conn, DEMO_RESTAURANT_ID)
    finally:
        conn.close()
    week_end = (date.fromisoformat(first) + timedelta(days=6)).isoformat()
    return [(first, last), (first, week_end), (first, first), ("2000-01-01", "2000-01-31")]


def test_the_endpoint_answers_with_the_agreed_shape(client, demo_periods):
    start, end = demo_periods[0]
    response = client.get(LABOR_COST_URL, params={"start": start, "end": end})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"start", "end", "labor_cost"}
    assert (body["start"], body["end"]) == (start, end)
    assert isinstance(body["labor_cost"], float) and body["labor_cost"] > 0


def test_both_ways_of_asking_give_the_same_wage_cost(client, demo_periods):
    direct, remote = in_process(DEMO_RESTAURANT_ID), over_http(client)
    for start, end in demo_periods:
        assert remote(start, end) == direct(start, end), (start, end)
    assert direct("2000-01-01", "2000-01-31") == 0          # no shifts: zero, not an error


def test_the_profit_and_loss_is_the_same_whichever_way_wages_arrive(client):
    conn = get_connection()
    try:
        start, end = sales_repo.get_sales_period(conn, DEMO_RESTAURANT_ID)
        daily = sales_repo.get_daily_sales(conn, DEMO_RESTAURANT_ID, start, end)
    finally:
        conn.close()
    assert profit_and_loss(daily, [], over_http(client), start, end) == \
        profit_and_loss(daily, [], in_process(DEMO_RESTAURANT_ID), start, end)


@pytest.mark.parametrize("params", [
    {"start": "2026-09-01"},                                  # end missing
    {"start": "September", "end": "2026-09-30"},              # not a date
    {"start": "2026-09-30", "end": "2026-09-01"},             # backwards
])
def test_the_endpoint_rejects_bad_periods(client, params):
    assert client.get(LABOR_COST_URL, params=params).status_code == 422


def test_each_restaurant_only_gets_its_own_wages(client, demo_periods):
    import app

    start, end = demo_periods[0]
    app.app.dependency_overrides[current_restaurant] = lambda: 999       # a restaurant with no staff
    assert client.get(LABOR_COST_URL, params={"start": start, "end": end}).json()["labor_cost"] == 0


def test_the_endpoint_needs_a_logged_in_manager(visitor):
    response = visitor.get(LABOR_COST_URL, params={"start": "2026-09-01", "end": "2026-09-30"},
                           follow_redirects=False)
    assert response.status_code == 303