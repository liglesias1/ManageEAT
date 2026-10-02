import sqlite3

import pytest

from domains.sales.repository import (
    add_supplier,
    get_dish_sales,
    get_ingredient_choices,
    get_last_order_day,
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