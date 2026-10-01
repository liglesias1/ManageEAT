"""Web pages of the sales domain."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database import get_connection
from domains.sales.repository import get_dish_sales
from domains.sales.services import classify_menu, menu_summary
from web import templates

router = APIRouter(prefix="/sales", tags=["sales"])

CATEGORY_ORDER = ["main", "starter", "dessert", "drink"]


@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request):
    conn = get_connection()
    try:
        dishes = classify_menu(get_dish_sales(conn))
    finally:
        conn.close()

    by_category = {c: [] for c in CATEGORY_ORDER}
    for dish in sorted(dishes, key=lambda d: d["units_sold"], reverse=True):
        by_category[dish["category"]].append(dish)

    return templates.TemplateResponse(
        request,
        "sales/menu.html",
        {"by_category": by_category, "summary": menu_summary(dishes)},
    )