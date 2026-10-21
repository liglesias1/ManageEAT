"""Home page: the key figures of every page in one place.

This module is not a domain. It sits on top of both and only calls their public functions,
so the rule of ADR-2 (sales and personnel stay separable) still holds.
"""
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from accounts.dependencies import current_restaurant
from database import get_connection
from domains.personnel import repository as personnel_repo
from domains.personnel import services as personnel
from domains.sales import repository as sales_repo
from domains.sales import services as sales
from domains.sales import wages
from web import templates

router = APIRouter(tags=["overview"])


def _sales_figures(conn, restaurant_id):
    dishes = sales.classify_menu(sales_repo.get_dish_sales(conn, restaurant_id))
    as_of = sales_repo.get_last_order_day(conn, restaurant_id)
    stock = sales.stock_status(sales_repo.get_stock_levels(conn, restaurant_id), as_of)
    # Same month as the profit and loss page shows by default
    current = date.today().strftime("%Y-%m")
    months = sales_repo.get_months(conn, restaurant_id)
    month = sales.choose_month(months, None, as_of[:7] if as_of else None, current)
    start, end = sales_repo.get_sales_period_in_month(conn, restaurant_id, month)
    statement = sales.profit_and_loss(
        sales_repo.get_daily_sales(conn, restaurant_id, start, end) if start else [],
        sales_repo.get_fixed_expenses(conn, restaurant_id, month),
        wages.in_process(restaurant_id),
        start,
        end,
    )
    return {
        "start": start,
        "end": end,
        "month": month,
        "pl": statement,
        "menu": sales.menu_summary(dishes),
        "dogs": [d["name"] for d in dishes if d["class"] == "dog"],
        "inventory": sales.inventory_summary(stock),
        "to_reorder": [i["name"] for i in stock if i["status"] != "ok"],
    }


def _personnel_figures(conn, restaurant_id):
    open_days = personnel_repo.get_open_days(conn, restaurant_id)
    demand = personnel.average_demand(personnel_repo.get_covers_by_hour(conn, restaurant_id), open_days)
    staff = personnel.average_staff_on_shift(personnel_repo.get_shifts(conn, restaurant_id), open_days)
    schedule = personnel.build_schedule(demand, staff, personnel_repo.get_roles(conn, restaurant_id))
    start, end = personnel_repo.get_clock_in_period(conn, restaurant_id)
    shifts = personnel_repo.get_worked_shifts(conn, restaurant_id, start, end) if start else []
    payroll = personnel.calculate_payroll(shifts)
    return {
        "schedule": personnel.schedule_summary(schedule),
        "employees": len(payroll),
        "hours": sum(p["hours"] for p in payroll),
        "wages": sum(p["pay"] for p in payroll),
    }


def attention_items(figures):
    """The few things a manager should act on today, each with the page where to do it."""
    items = []
    if figures["to_reorder"]:
        items.append({"text": "Ingredients to reorder: " + ", ".join(figures["to_reorder"]),
                      "link": "/sales/inventory", "page": "Inventory"})
    role = figures["schedule"]["most_missing_role"]
    if role:
        items.append({"text": f"{role} is the role most often short of people",
                      "link": "/personnel/schedule", "page": "Staff & schedule"})
    if figures["dogs"]:
        items.append({"text": f"Dishes that sell little and earn little: {', '.join(figures['dogs'])}",
                      "link": "/sales/menu", "page": "Menu performance"})
    if figures["pl"]["net_profit"] < 0:
        items.append({"text": "The month is losing money", "link": "/sales/profit-loss", "page": "Profit & loss"})
    return items


@router.get("/", response_class=HTMLResponse)
def overview_page(request: Request, restaurant_id: int = Depends(current_restaurant)):
    conn = get_connection()
    try:
        figures = {**_sales_figures(conn, restaurant_id), **_personnel_figures(conn, restaurant_id)}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "overview.html", {**figures, "attention": attention_items(figures)}
    )