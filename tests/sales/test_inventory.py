import pytest
from pydantic import ValidationError

from domains.sales.schemas import SupplierIn
from domains.sales.services import inventory_summary, stock_status


def ingredient(name="Rice", counted=100, used=0, reorder=10, lead=2, cost=2.0, counted_at="2026-09-21"):
    return {"name": name, "unit": "kg", "unit_cost": cost, "counted_stock": counted, "counted_at": counted_at,
            "reorder_level": reorder, "lead_time_days": lead, "used_since_count": used, "supplier": "S"}


# ---------- stock_status ----------

def test_current_stock_is_stocktake_minus_usage():
    item = stock_status([ingredient(counted=100, used=30)], "2026-09-30")[0]   # 10 days since the count
    assert item["current"] == 70
    assert item["daily_use"] == 3
    assert item["days_left"] == pytest.approx(70 / 3)
    assert item["status"] == "ok"


def test_below_reorder_level_needs_reordering():
    item = stock_status([ingredient(counted=100, used=95, reorder=10, lead=1)], "2026-09-30")[0]
    assert item["status"] == "reorder"


def test_running_out_before_delivery_needs_reordering_even_above_the_level():
    # 20 kg left, using 10 kg a day -> 2 days left; the supplier takes 3 days to deliver
    item = stock_status([ingredient(counted=120, used=100, reorder=5, lead=3)], "2026-09-30")[0]
    assert item["current"] > item["reorder_level"]
    assert item["status"] == "reorder"


def test_empty_stock_is_out():
    item = stock_status([ingredient(counted=50, used=60)], "2026-09-30")[0]
    assert item["status"] == "out"
    assert item["days_left"] == 0
    assert item["stock_value"] == 0


def test_suggested_order_covers_lead_time_plus_a_week():
    # 10 kg a day, 2 days delivery + 7 days cover = 90 kg, plus 10 kg safety level, minus 5 kg left = 95 kg
    item = stock_status([ingredient(counted=105, used=100, reorder=10, lead=2)], "2026-09-30")[0]
    assert item["suggested_order"] == 95


def test_unused_ingredient_has_no_days_left_and_no_order():
    item = stock_status([ingredient(counted=10, used=0, reorder=2)], "2026-09-30")[0]
    assert item["daily_use"] == 0
    assert item["days_left"] is None
    assert item["suggested_order"] == 0


def test_most_urgent_ingredients_come_first():
    stock = stock_status([
        ingredient("Fine", counted=100, used=10),
        ingredient("Empty", counted=10, used=20),
        ingredient("Low", counted=100, used=95),
    ], "2026-09-30")
    assert [i["name"] for i in stock] == ["Empty", "Low", "Fine"]


def test_no_orders_yet():
    item = stock_status([ingredient(counted=10)], None)[0]
    assert item["daily_use"] == 0
    assert item["status"] == "ok"


def test_inventory_summary():
    stock = stock_status([
        ingredient("A", counted=100, used=10, cost=2.0),   # ok, 90 left
        ingredient("B", counted=100, used=95, cost=1.0),   # reorder
        ingredient("C", counted=10, used=20),              # out
    ], "2026-09-30")
    summary = inventory_summary(stock)
    assert summary["to_reorder"] == 1
    assert summary["out_of_stock"] == 1
    assert summary["stock_value"] == 90 * 2.0 + 5 * 1.0
    assert summary["order_value"] > 0


# ---------- SupplierIn (form validation) ----------

def test_supplier_with_only_a_phone_is_valid():
    supplier = SupplierIn(name="Carnes Martín", phone="+34 600 000 000", email="", lead_time_days="2")
    assert supplier.email is None
    assert supplier.lead_time_days == 2


def test_supplier_without_phone_or_email_is_rejected():
    with pytest.raises(ValidationError, match="phone number or an email"):
        SupplierIn(name="Nobody", phone="  ", email="", lead_time_days=2)


def test_supplier_email_must_look_like_an_email():
    with pytest.raises(ValidationError, match="valid email"):
        SupplierIn(name="Typo", email="pedidos.gmail.com", lead_time_days=2)


def test_supplier_lead_time_cannot_be_negative():
    with pytest.raises(ValidationError):
        SupplierIn(name="Slow", phone="600", email=None, lead_time_days=-1)