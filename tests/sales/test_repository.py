import sqlite3

import pytest

from domains.sales.repository import (
    add_fixed_expense,
    add_purchase,
    add_supplier,
    get_daily_sales,
    get_dish_sales,
    get_fixed_expenses,
    get_ingredient_choices,
    get_purchases,
    get_last_order_day,
    get_sales_period,
    get_stock_levels,
    get_supplier,
    get_suppliers,
)

from domains.sales.seed import seed_sales_if_empty


def add_menu(conn):
    """Two ingredients, two dishes (one of them never sold) and one recipe each."""
    conn.execute("INSERT INTO suppliers VALUES (1, 'Supplier', '600000000', NULL, 2)")
    conn.execute("INSERT INTO ingredients VALUES (1, 'Rice', 'kg', 2.0, 1, 10, '2026-09-01', 2)")
    conn.execute("INSERT INTO ingredients VALUES (2, 'Chicken', 'kg', 5.0, 1, 10, '2026-09-01', 2)")
    conn.execute("INSERT INTO menu_items VALUES ('PAE01', 'Paella', 'main')")
    conn.execute("INSERT INTO menu_items VALUES ('RIS01', 'Risotto', 'main')")
    conn.execute("INSERT INTO recipes VALUES ('PAE01', 1, 0.1)")   # 0.1 kg rice    = 0.20
    conn.execute("INSERT INTO recipes VALUES ('PAE01', 2, 0.2)")   # 0.2 kg chicken = 1.00
    conn.execute("INSERT INTO recipes VALUES ('RIS01', 1, 0.5)")   # 0.5 kg rice    = 1.00


def add_order(conn, order_id, item_code, quantity, price):
    conn.execute("INSERT INTO orders VALUES (?, 1, 2, '2026-09-01T14:00:00')", (order_id,))
    conn.execute(
        "INSERT INTO order_items (order_id, item_code, quantity, unit_price) VALUES (?, ?, ?, ?)",
        (order_id, item_code, quantity, price),
    )


def test_units_revenue_and_cost_per_dish(conn):
    add_menu(conn)
    add_order(conn, 1, "PAE01", 2, 18.0)
    add_order(conn, 2, "PAE01", 1, 20.0)   # sold at a different price later on

    paella = {d["code"]: d for d in get_dish_sales(conn)}["PAE01"]
    assert paella["units_sold"] == 3
    assert paella["revenue"] == 56            # 2 * 18 + 1 * 20
    assert paella["unit_cost"] == pytest.approx(1.20)


def test_dish_without_sales_is_still_listed(conn):
    add_menu(conn)
    risotto = {d["code"]: d for d in get_dish_sales(conn)}["RIS01"]
    assert risotto["units_sold"] == 0
    assert risotto["revenue"] == 0
    assert risotto["unit_cost"] == pytest.approx(1.00)


def test_dish_cost_follows_ingredient_price(conn):
    add_menu(conn)
    conn.execute("UPDATE ingredients SET unit_cost = 4.0 WHERE name = 'Rice'")
    risotto = {d["code"]: d for d in get_dish_sales(conn)}["RIS01"]
    assert risotto["unit_cost"] == pytest.approx(2.00)   # 0.5 kg * 4.0


def test_demo_data_loads_once(conn):
    seed_sales_if_empty(conn)
    seed_sales_if_empty(conn)
    assert conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 13


def test_supplier_needs_phone_or_email(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO suppliers (name, lead_time_days) VALUES ('No contact', 2)")


def test_stock_levels_count_only_usage_since_the_stocktake(conn):
    add_menu(conn)                                     # rice counted on 2026-09-01, 0.5 kg per risotto
    conn.execute("UPDATE ingredients SET counted_at = '2026-09-05' WHERE name = 'Rice'")
    conn.execute("INSERT INTO orders VALUES (1, 1, 2, '2026-09-04T14:00:00')")   # before the count
    conn.execute("INSERT INTO order_items (order_id, item_code, quantity, unit_price) VALUES (1, 'RIS01', 4, 16)")
    conn.execute("INSERT INTO orders VALUES (2, 1, 2, '2026-09-06T14:00:00')")   # after the count
    conn.execute("INSERT INTO order_items (order_id, item_code, quantity, unit_price) VALUES (2, 'RIS01', 2, 16)")

    rice = {i["name"]: i for i in get_stock_levels(conn)}["Rice"]
    assert rice["used_since_count"] == pytest.approx(1.0)   # only the 2 risottos after the count
    assert rice["supplier"] == "Supplier"
    assert rice["used_in_period"] == pytest.approx(3.0)     # all 6 risottos in the period
    assert get_last_order_day(conn) == "2026-09-06"


def test_add_supplier_and_list_suppliers(conn):
    add_supplier(conn, "Huerta", None, "ventas@huerta.es", 1)
    suppliers = get_suppliers(conn)
    assert [s["name"] for s in suppliers] == ["Huerta"]
    assert suppliers[0]["supplies"] == ""


def test_new_supplier_takes_over_the_ticked_ingredients(conn):
    add_menu(conn)                                     # Rice (id 1) and Chicken (id 2) belong to "Supplier"
    new_id = add_supplier(conn, "Arroces Bomba", "600", None, 3, ingredient_ids=[1])
    suppliers = {s["name"]: s for s in get_suppliers(conn)}
    assert suppliers["Arroces Bomba"]["supplies"] == "Rice"
    assert suppliers["Supplier"]["supplies"] == "Chicken"
    assert get_supplier(conn, new_id)["lead_time_days"] == 3
    assert [i["supplier"] for i in get_ingredient_choices(conn)] == ["Supplier", "Arroces Bomba"]  # Chicken, Rice


def test_unknown_supplier_is_none(conn):
    assert get_supplier(conn, 999) is None


def test_deliveries_after_the_stocktake_count_as_received(conn):
    add_menu(conn)                                      # rice counted on 2026-09-01
    add_purchase(conn, 1, 1, 20, 2.0, "2026-08-30")      # before the count: already in the counted stock
    add_purchase(conn, 1, 1, 15, 2.1, "2026-09-03")      # after the count
    rice = {i["name"]: i for i in get_stock_levels(conn)}["Rice"]
    assert rice["received_since_count"] == 15

    history = get_purchases(conn, 1)
    assert [p["received_on"] for p in history] == ["2026-09-03", "2026-08-30"]   # newest first
    assert history[0]["total"] == pytest.approx(31.5)


def test_purchase_quantity_must_be_positive(conn):
    add_menu(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_purchase(conn, 1, 1, 0, 2.0, "2026-09-03")



def test_daily_sales_add_revenue_and_ingredient_cost(conn):
    add_menu(conn)                                       # paella costs 1.20, risotto 1.00
    add_order(conn, 1, "PAE01", 2, 18.0)                 # all on 2026-09-01
    add_order(conn, 2, "RIS01", 1, 16.0)
    add_order(conn, 3, "XXX99", 1, 3.0)                  # an item with no recipe costs nothing
    day = get_daily_sales(conn, "2026-09-01", "2026-09-30")[0]
    assert day["revenue"] == 2 * 18 + 16 + 3
    assert day["ingredient_cost"] == pytest.approx(2 * 1.20 + 1.00)
    assert get_sales_period(conn) == ("2026-09-01", "2026-09-01")


def test_fixed_expenses_by_month(conn):
    add_fixed_expense(conn, "Rent", 3200, "2026-09")
    add_fixed_expense(conn, "Rent", 3200, "2026-10")
    add_fixed_expense(conn, "Insurance", 180, "2026-09")
    september = get_fixed_expenses(conn, "2026-09")
    assert [e["description"] for e in september] == ["Rent", "Insurance"]   # biggest first