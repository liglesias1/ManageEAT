"""Where sales gets its wage costs from: the only file of the sales domain that talks to personnel (ADR-2).

profit_and_loss() receives a function labor_cost_for(start, end) and never asks where the number comes
from. This file builds that function in two ways that must always give the same result:
- in_process(restaurant_id): calls personnel's code directly. Used today, with one app and one database.
- over_http(http_client): asks personnel's JSON endpoint, /personnel/api/labor-cost. Used in Assignment 2,
  when personnel is a separate service: over_http(httpx.Client(base_url=<personnel service URL>)).
tests/test_seam.py checks that both give the same numbers, so the switch does not change any figure.
"""
from database import get_connection
from domains.personnel.services import labor_cost

LABOR_COST_URL = "/personnel/api/labor-cost"


def in_process(restaurant_id):
    """Wage costs read straight from personnel's tables, with a connection of its own."""
    def labor_cost_for(start, end):
        conn = get_connection()
        try:
            return labor_cost(conn, restaurant_id, start, end)
        finally:
            conn.close()
    return labor_cost_for


def over_http(http_client):
    """Wage costs asked to personnel's endpoint; the restaurant is the one http_client is logged in as."""
    def labor_cost_for(start, end):
        response = http_client.get(LABOR_COST_URL, params={"start": start, "end": end})
        response.raise_for_status()
        return response.json()["labor_cost"]
    return labor_cost_for