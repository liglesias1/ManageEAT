"""Web pages of the sales domain."""
from typing import List

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from database import get_connection
from domains.sales import repository
from domains.sales.repository import get_dish_sales
from domains.sales.schemas import SupplierIn
from domains.sales.services import classify_menu, inventory_summary, menu_summary, stock_status, supplier_summary
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


def _inventory_page(request, errors=None, form=None, added=None, status_code=200):
    conn = get_connection()
    try:
        stock = stock_status(repository.get_stock_levels(conn), repository.get_last_order_day(conn))
        as_of = repository.get_last_order_day(conn)
        suppliers = repository.get_suppliers(conn)
        ingredients = repository.get_ingredient_choices(conn)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "sales/inventory.html",
        {
            "stock": stock,
            "as_of": as_of,
            "summary": inventory_summary(stock),
            "suppliers": suppliers,
            "ingredients": ingredients,
            "errors": errors or [],
            "form": form or {},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, added: str = None):
    return _inventory_page(request, added=added)


@router.post("/inventory/suppliers", response_class=HTMLResponse)
def create_supplier(
    request: Request,
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    lead_time_days: str = Form(""),
    ingredient_ids: List[int] = Form([]),
):
    form = {"name": name, "phone": phone, "email": email, "lead_time_days": lead_time_days,
            "ingredient_ids": ingredient_ids}
    try:
        supplier = SupplierIn(**form)
    except ValidationError as error:
        messages = [e["msg"].replace("Value error, ", "").capitalize() for e in error.errors()]
        return _inventory_page(request, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        repository.add_supplier(
            conn, supplier.name, supplier.phone, supplier.email, supplier.lead_time_days, supplier.ingredient_ids
        )
    finally:
        conn.close()
    # Post/Redirect/Get: reloading the page after saving does not submit the form twice
    return RedirectResponse(url=f"/sales/inventory?added={supplier.name}", status_code=303)


@router.get("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_page(request: Request, supplier_id: int):
    conn = get_connection()
    try:
        supplier = repository.get_supplier(conn, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        stock = stock_status(repository.get_stock_levels(conn), repository.get_last_order_day(conn))
    finally:
        conn.close()

    items = [item for item in stock if item["supplier_id"] == supplier_id]
    return templates.TemplateResponse(
        request,
        "sales/supplier.html",
        {"supplier": supplier, "items": items, "summary": supplier_summary(items)},
    )