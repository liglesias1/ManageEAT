"""The public face of the sales domain (Facade): the only functions the rest of the app may call.

Everything else in domains/sales (repository, services, routes) is internal and can change freely.
Each function opens its own database connection, so callers never touch sales' tables, and in
Assignment 2 each one can become an endpoint of the sales service without changing its callers.
"""
from datetime import date

from database import get_connection
from domains.sales import repository, services, wages


def overview_figures(restaurant_id):
    """The sales figures shown on the home page, for the same month the profit and loss page opens on."""
    current = date.today().strftime("%Y-%m")
    conn = get_connection()
    try:
        dishes = services.classify_menu(repository.get_dish_sales(conn, restaurant_id))
        as_of = repository.get_last_order_day(conn, restaurant_id)
        stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
        months = repository.get_months(conn, restaurant_id)
        month = services.choose_month(months, None, as_of[:7] if as_of else None, current)
        start, end = repository.get_sales_period_in_month(conn, restaurant_id, month)
        daily = repository.get_daily_sales(conn, restaurant_id, start, end) if start else []
        expenses = repository.get_fixed_expenses(conn, restaurant_id, month)
    finally:
        conn.close()
    return {
        "start": start,
        "end": end,
        "month": month,
        "pl": services.profit_and_loss(daily, expenses, wages.in_process(restaurant_id), start, end),
        "menu": services.menu_summary(dishes),
        "dogs": [d["name"] for d in dishes if d["class"] == "dog"],
        "inventory": services.inventory_summary(stock),
        "to_reorder": [i["name"] for i in stock if i["status"] != "ok"],
    }