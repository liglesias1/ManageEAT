import pytest
from pydantic import ValidationError

from domains.sales.schemas import FixedExpenseIn
from domains.sales.services import profit_and_loss

DAILY = [
    {"day": "2026-09-01", "revenue": 1000.0, "ingredient_cost": 250.0},
    {"day": "2026-09-08", "revenue": 2000.0, "ingredient_cost": 500.0},
]
RENT = [{"description": "Rent", "amount": 3000.0}]


def fake_labor_cost(start, end):
    """Stands in for personnel's labor_cost: 100 EUR per day, whatever the payroll tables say."""
    from datetime import date
    return 100.0 * ((date.fromisoformat(end) - date.fromisoformat(start)).days + 1)


def test_net_profit_is_revenue_minus_ingredients_wages_and_fixed_costs():
    pl = profit_and_loss(DAILY, RENT, fake_labor_cost, "2026-09-01", "2026-09-10")
    assert pl["revenue"] == 3000
    assert pl["ingredients"] == 750
    assert pl["gross_profit"] == 2250
    assert pl["labor"] == 1000           # 10 days x 100
    assert pl["fixed"] == 3000
    assert pl["net_profit"] == 2250 - 1000 - 3000


def test_wages_come_only_from_the_function_it_is_given():
    # The seam between the two domains: sales never reads personnel's tables,
    # it only asks for the wage cost of a period.
    calls = []

    def recording_labor_cost(start, end):
        calls.append((start, end))
        return 0.0

    profit_and_loss(DAILY, [], recording_labor_cost, "2026-09-01", "2026-09-10")
    assert ("2026-09-01", "2026-09-10") in calls                          # whole month
    assert ("2026-09-01", "2026-09-07") in calls                          # first week
    assert ("2026-09-08", "2026-09-10") in calls                          # last, shorter week


def test_costs_as_a_share_of_revenue():
    pl = profit_and_loss(DAILY, RENT, fake_labor_cost, "2026-09-01", "2026-09-10")
    assert pl["ingredients_pct"] == 25
    assert pl["fixed_pct"] == 100
    assert pl["net_margin_pct"] == pytest.approx(-1750 / 3000 * 100)


def test_weekly_breakdown_splits_sales_and_shares_out_fixed_costs_by_day():
    pl = profit_and_loss(DAILY, RENT, fake_labor_cost, "2026-09-01", "2026-09-10")
    first, second = pl["weeks"]
    assert (first["start"], first["end"]) == ("2026-09-01", "2026-09-07")
    assert first["revenue"] == 1000 and second["revenue"] == 2000
    assert first["fixed"] == pytest.approx(3000 / 30 * 7)              # September has 30 days
    assert second["fixed"] == pytest.approx(3000 / 30 * 3)
    assert first["profit"] == pytest.approx(1000 - 250 - 700 - 700)


def test_no_sales_yet():
    pl = profit_and_loss([], RENT, fake_labor_cost, None, None)
    assert pl["revenue"] == 0
    assert pl["labor"] == 0
    assert pl["net_margin_pct"] == 0
    assert pl["weeks"] == []


def test_fixed_expense_validation():
    expense = FixedExpenseIn(description="  Rent ", amount="3200", month="2026-09")
    assert expense.description == "Rent"
    with pytest.raises(ValidationError):
        FixedExpenseIn(description="Rent", amount=0, month="2026-09")
    with pytest.raises(ValidationError):
        FixedExpenseIn(description="Rent", amount=100, month="September")
    with pytest.raises(ValidationError):
        FixedExpenseIn(description="Rent", amount=100, month="2026-13")