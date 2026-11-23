"""The personnel endpoints that only use personnel's data: payroll, the overview figures, and the wage cost."""
import pytest

from tests.conftest import log_in

PERIOD = {"start": "2026-09-01", "end": "2026-09-28"}   # the demo clock-ins


def test_payroll_lists_every_employee_with_totals(client):
    body = client.get("/personnel/payroll").json()
    assert (body["start"], body["end"]) == ("2026-09-01", "2026-09-28")
    assert len(body["payroll"]) == 16
    assert body["total_pay"] == round(sum(p["pay"] for p in body["payroll"]), 2)
    assert {r["role"] for r in body["by_role"]} == {"Waiter", "Runner", "Bar", "Pass", "Cook", "Dishwasher"}


def test_the_summary_matches_the_payroll_and_the_schedule(client):
    payroll = client.get("/personnel/payroll").json()
    schedule = client.get("/personnel/schedule").json()
    summary = client.get("/personnel/summary").json()
    assert (summary["employees"], summary["hours"], summary["wages"]) == \
        (16, payroll["total_hours"], payroll["total_pay"])
    assert summary["schedule"] == schedule["summary"]
    assert summary["demand"] == {"source": "live"}


# ---------- The seam ----------

def test_labor_cost_answers_with_the_agreed_shape(client):
    response = client.get("/personnel/labor-cost", params=PERIOD)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"start", "end", "labor_cost"}
    assert (body["start"], body["end"]) == (PERIOD["start"], PERIOD["end"])
    assert isinstance(body["labor_cost"], float) and body["labor_cost"] > 0


def test_labor_cost_of_the_whole_period_is_the_total_payroll(client):
    total = client.get("/personnel/payroll").json()["total_pay"]
    assert client.get("/personnel/labor-cost", params=PERIOD).json()["labor_cost"] == total


def test_a_period_without_shifts_costs_zero(client):
    params = {"start": "2000-01-01", "end": "2000-01-31"}
    assert client.get("/personnel/labor-cost", params=params).json()["labor_cost"] == 0


@pytest.mark.parametrize("params", [
    {"start": "2026-09-01"},                                  # end missing
    {"start": "September", "end": "2026-09-30"},              # not a date
    {"start": "2026-09-30", "end": "2026-09-01"},             # backwards
])
def test_labor_cost_rejects_bad_periods(client, params):
    assert client.get("/personnel/labor-cost", params=params).status_code == 422


def test_each_restaurant_only_gets_its_own_wages(visitor):
    visitor.post("/auth/register", json={"restaurant_name": "Bar Pepe", "name": "Pepe",
                                         "email": "pepe@barpepe.es", "password": "tortilla99"})
    headers = log_in(visitor, email="pepe@barpepe.es", password="tortilla99")
    assert visitor.get("/personnel/labor-cost", params=PERIOD, headers=headers).json()["labor_cost"] == 0
