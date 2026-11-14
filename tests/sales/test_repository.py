import sqlite3

import pytest

from domains.sales.repository import (
    add_fixed_expense,
    add_purchase,
    add_supplier,
    get_daily_sales,
    get_dish,
    get_dish_sales,
    get_fixed_expenses,
    get_ingredient,
    get_ingredient_choices,
    get_months,
    get_purchases,
    get_last_order_day,
    get_sales_period,
    get_sales_period_in_month,
    get_stock_levels,
    get_supplier,
    get_suppliers,
)

from domains.sales.seed import seed_sales_if_empty

R = 1        # the restaurant most tests work with
OTHER = 2    # a second restaurant, to check that data never leaks between them


def add_menu(conn, restaurant_id=R, first_id=1):
    """Two ingredients, two dishes (one of them never sold) and one recipe each."""
    supplier, rice, chicken = first_id, first_id, first_id + 1
    conn.execute("INSERT INTO suppliers VALUES (?, ?, 'Supplier', '600000000', NULL, 2)", (supplier, restaurant_id))
    conn.execute("INSERT INTO ingredients VALUES (?, ?, 'Rice', 'kg', 2.0, ?, 10, '2026-09-01', 2)",
                 (rice, restaurant_id, supplier))
    conn.execute("INSERT INTO ingredients VALUES (?, ?, 'Chicken', 'kg', 5.0, ?, 10, '2026-09-01', 2)",
                 (chicken, restaurant_id, supplier))
    conn.execute("INSERT INTO menu_items VALUES (?, 'PAE01', 'Paella', 'main', 18)", (restaurant_id,))
    conn.execute("INSERT INTO menu_items VALUES (?, 'RIS01', 'Risotto', 'main', 16)", (restaurant_id,))
    conn.execute("INSERT INTO recipes VALUES (?, 'PAE01', ?, 0.1)", (restaurant_id, rice))      # 0.1 kg rice    = 0.20
    conn.execute("INSERT INTO recipes VALUES (?, 'PAE01', ?, 0.2)", (restaurant_id, chicken))   # 0.2 kg chicken = 1.00
    conn.execute("INSERT INTO recipes VALUES (?, 'RIS01', ?, 0.5)", (restaurant_id, rice))      # 0.5 kg rice    = 1.00


def add_order(conn, order_id, item_code, quantity, price, restaurant_id=R, created_at="2026-09-01T14:00:00"):
    conn.execute("INSERT INTO orders VALUES (?, ?, 1, 2, ?)", (order_id, restaurant_id, created_at))
    conn.execute(
        "INSERT INTO order_items (order_id, item_code, quantity, unit_price) VALUES (?, ?, ?, ?)",
        (order_id, item_code, quantity, price),
    )


def test_units_revenue_and_cost_per_dish(conn):
    add_menu(conn)
    add_order(conn, 1, "PAE01", 2, 18.0)
    add_order(conn, 2, "PAE01", 1, 20.0)   # sold at a different price later on

    paella = {d["code"]: d for d in get_dish_sales(conn, R)}["PAE01"]
    assert paella["units_sold"] == 3
    assert paella["revenue"] == 56            # 2 * 18 + 1 * 20
    assert paella["unit_cost"] == pytest.approx(1.20)


def test_dish_without_sales_is_still_listed(conn):
    add_menu(conn)
    risotto = {d["code"]: d for d in get_dish_sales(conn, R)}["RIS01"]
    assert risotto["units_sold"] == 0
    assert risotto["revenue"] == 0
    assert risotto["unit_cost"] == pytest.approx(1.00)


def test_dish_cost_follows_ingredient_price(conn):
    add_menu(conn)
    conn.execute("UPDATE ingredients SET unit_cost = 4.0 WHERE name = 'Rice'")
    risotto = {d["code"]: d for d in get_dish_sales(conn, R)}["RIS01"]
    assert risotto["unit_cost"] == pytest.approx(2.00)   # 0.5 kg * 4.0


def test_demo_data_loads_once(conn):
    seed_sales_if_empty(conn, R)
    seed_sales_if_empty(conn, R)
    assert conn.execute("SELECT COUNT(*) FROM menu_items WHERE restaurant_id = ?", (R,)).fetchone()[0] == 13


def test_supplier_needs_phone_or_email(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO suppliers (restaurant_id, name, lead_time_days) VALUES (1, 'No contact', 2)")


def test_stock_levels_count_only_usage_since_the_stocktake(conn):
    add_menu(conn)                                     # rice counted on 2026-09-01, 0.5 kg per risotto
    conn.execute("UPDATE ingredients SET counted_at = '2026-09-05' WHERE name = 'Rice'")
    add_order(conn, 1, "RIS01", 4, 16, created_at="2026-09-04T14:00:00")    # before the count
    add_order(conn, 2, "RIS01", 2, 16, created_at="2026-09-06T14:00:00")    # after the count

    rice = {i["name"]: i for i in get_stock_levels(conn, R)}["Rice"]
    assert rice["used_since_count"] == pytest.approx(1.0)   # only the 2 risottos after the count
    assert rice["supplier"] == "Supplier"
    assert rice["used_in_period"] == pytest.approx(3.0)     # all 6 risottos in the period
    assert get_last_order_day(conn, R) == "2026-09-06"


def test_add_supplier_and_list_suppliers(conn):
    add_supplier(conn, R, "Huerta", None, "ventas@huerta.es", 1)
    suppliers = get_suppliers(conn, R)
    assert [s["name"] for s in suppliers] == ["Huerta"]
    assert suppliers[0]["supplies"] == ""


def test_new_supplier_takes_over_the_ticked_ingredients(conn):
    add_menu(conn)                                     # Rice (id 1) and Chicken (id 2) belong to "Supplier"
    new_id = add_supplier(conn, R, "Arroces Bomba", "600", None, 3, ingredient_ids=[1])
    suppliers = {s["name"]: s for s in get_suppliers(conn, R)}
    assert suppliers["Arroces Bomba"]["supplies"] == "Rice"
    assert suppliers["Supplier"]["supplies"] == "Chicken"
    assert get_supplier(conn, R, new_id)["lead_time_days"] == 3
    assert [i["supplier"] for i in get_ingredient_choices(conn, R)] == ["Supplier", "Arroces Bomba"]  # Chicken, Rice


def test_unknown_supplier_is_none(conn):
    assert get_supplier(conn, R, 999) is None


def test_deliveries_after_the_stocktake_count_as_received(conn):
    add_menu(conn)                                      # rice counted on 2026-09-01
    add_purchase(conn, 1, 1, 20, 2.0, "2026-08-30")      # before the count: already in the counted stock
    add_purchase(conn, 1, 1, 15, 2.1, "2026-09-03")      # after the count
    rice = {i["name"]: i for i in get_stock_levels(conn, R)}["Rice"]
    assert rice["received_since_count"] == 15

    history = get_purchases(conn, R, 1)
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
    day = get_daily_sales(conn, R, "2026-09-01", "2026-09-30")[0]
    assert day["revenue"] == 2 * 18 + 16 + 3
    assert day["ingredient_cost"] == pytest.approx(2 * 1.20 + 1.00)
    assert get_sales_period(conn, R) == ("2026-09-01", "2026-09-01")


def test_fixed_expenses_by_month(conn):
    add_fixed_expense(conn, R, "Rent", 3200, "2026-09")
    add_fixed_expense(conn, R, "Rent", 3200, "2026-10")
    add_fixed_expense(conn, R, "Insurance", 180, "2026-09")
    september = get_fixed_expenses(conn, R, "2026-09")
    assert [e["description"] for e in september] == ["Rent", "Insurance"]   # biggest first


def test_months_come_from_orders_and_fixed_expenses(conn):
    add_menu(conn)
    add_order(conn, 1, "PAE01", 1, 18)                       # an order in 2026-09
    add_fixed_expense(conn, R, "Rent", 3000, "2026-10")      # an expense in a month with no orders yet
    add_fixed_expense(conn, R, "Water", 100, "2026-09")
    assert get_months(conn, R) == ["2026-09", "2026-10"]


def test_sales_period_in_month_only_looks_at_that_month(conn):
    add_menu(conn)
    add_order(conn, 1, "PAE01", 1, 18)                       # 2026-09-01
    add_order(conn, 2, "PAE01", 1, 18, created_at="2026-10-05T14:00:00")
    assert get_sales_period_in_month(conn, R, "2026-09") == ("2026-09-01", "2026-09-01")
    assert get_sales_period_in_month(conn, R, "2026-10") == ("2026-10-05", "2026-10-05")
    assert get_sales_period_in_month(conn, R, "2026-11") == (None, None)


def test_database_rejects_repeated_names_whatever_the_case(conn):
    add_menu(conn)                                           # supplier "Supplier", ingredients Rice and Chicken
    with pytest.raises(sqlite3.IntegrityError):
        add_supplier(conn, R, "SUPPLIER", "600", None, 2)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO ingredients VALUES (3, 1, 'rice', 'kg', 2.0, 1, 10, '2026-09-01', 2)")


# ---------- Two restaurants never see each other's data ----------

def test_two_restaurants_can_use_the_same_names_and_dish_codes(conn):
    add_menu(conn, R, first_id=1)
    add_menu(conn, OTHER, first_id=10)                       # also a "Supplier", "Rice" and a dish PAE01
    assert [s["name"] for s in get_suppliers(conn, OTHER)] == ["Supplier"]
    assert get_dish(conn, OTHER, "PAE01")["name"] == "Paella"


def test_each_restaurant_only_sees_its_own_sales_and_costs(conn):
    add_menu(conn, R, first_id=1)
    add_menu(conn, OTHER, first_id=10)
    conn.execute("UPDATE ingredients SET unit_cost = 4.0 WHERE restaurant_id = ? AND name = 'Rice'", (OTHER,))
    add_order(conn, 1, "PAE01", 2, 18.0, restaurant_id=R)
    add_order(conn, 2, "PAE01", 5, 20.0, restaurant_id=OTHER, created_at="2026-10-01T14:00:00")

    mine = {d["code"]: d for d in get_dish_sales(conn, R)}["PAE01"]
    assert (mine["units_sold"], mine["revenue"]) == (2, 36)
    assert mine["unit_cost"] == pytest.approx(1.20)           # the other restaurant's dearer rice does not count
    assert get_daily_sales(conn, R, "2026-01-01", "2026-12-31")[0]["revenue"] == 36
    assert get_months(conn, R) == ["2026-09"]
    assert get_last_order_day(conn, R) == "2026-09-01"
    rice = {i["name"]: i for i in get_stock_levels(conn, R)}["Rice"]
    assert rice["used_in_period"] == pytest.approx(0.2)       # 2 paellas x 0.1 kg, not the other restaurant's 5


def test_a_restaurant_cannot_read_or_edit_another_restaurants_rows(conn):
    add_menu(conn, R, first_id=1)
    add_fixed_expense(conn, OTHER, "Their rent", 5000, "2026-09")
    assert get_supplier(conn, OTHER, 1) is None               # supplier 1 belongs to restaurant 1
    assert get_ingredient(conn, OTHER, 1) is None
    assert get_dish(conn, OTHER, "PAE01") is None
    assert get_purchases(conn, OTHER, 1) == []
    assert get_fixed_expenses(conn, R, "2026-09") == []