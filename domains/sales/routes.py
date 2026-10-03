"""Web pages of the sales domain."""
from typing import List

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from database import get_connection
from domains.personnel.services import labor_cost  # the only thing sales uses from personnel (see ADR-2)
from domains.sales import repository
from domains.sales.repository import get_dish_sales
from domains.sales.schemas import FixedExpenseIn, PurchaseIn, SupplierIn
from domains.sales.services import (
    classify_menu,
    inventory_summary,
    menu_summary,
    profit_and_loss,
    stock_status,
    supplier_summary,
)
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


def _supplier_page(request, supplier_id, errors=None, form=None, added=False, status_code=200):
    conn = get_connection()
    try:
        supplier = repository.get_supplier(conn, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        as_of = repository.get_last_order_day(conn)
        stock = stock_status(repository.get_stock_levels(conn), as_of)
        purchases = repository.get_purchases(conn, supplier_id)
    finally:
        conn.close()

    items = [item for item in stock if item["supplier_id"] == supplier_id]
    return templates.TemplateResponse(
        request,
        "sales/supplier.html",
        {
            "supplier": supplier,
            "items": items,
            "purchases": purchases,
            "summary": supplier_summary(items, purchases),
            "errors": errors or [],
            "form": form or {"received_on": as_of},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_page(request: Request, supplier_id: int, added: bool = False):
    return _supplier_page(request, supplier_id, added=added)


@router.post("/suppliers/{supplier_id}/purchases", response_class=HTMLResponse)
def record_purchase(
    request: Request,
    supplier_id: int,
    ingredient_id: str = Form(""),
    quantity: str = Form(""),
    unit_price: str = Form(""),
    received_on: str = Form(""),
):
    form = {"ingredient_id": ingredient_id, "quantity": quantity, "unit_price": unit_price, "received_on": received_on}
    try:
        purchase = PurchaseIn(**form)
    except ValidationError as error:
        messages = [f"{e['loc'][0].replace('_', ' ').capitalize()}: {e['msg'].lower()}" for e in error.errors()]
        return _supplier_page(request, supplier_id, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        sold_here = [i["id"] for i in repository.get_stock_levels(conn) if i["supplier_id"] == supplier_id]
        if purchase.ingredient_id in sold_here:
            repository.add_purchase(conn, supplier_id, purchase.ingredient_id, purchase.quantity,
                                    purchase.unit_price, purchase.received_on.isoformat())
    finally:
        conn.close()

    if purchase.ingredient_id not in sold_here:
        return _supplier_page(request, supplier_id, errors=["This supplier does not sell that product"],
                              form=form, status_code=422)
    return RedirectResponse(url=f"/sales/suppliers/{supplier_id}?added=true", status_code=303)


def _profit_loss_page(request, errors=None, form=None, added=None, status_code=200):
    conn = get_connection()
    try:
        start, end = repository.get_sales_period(conn)
        month = start[:7] if start else None
        daily = repository.get_daily_sales(conn, start, end) if start else []
        expenses = repository.get_fixed_expenses(conn, month) if month else []
        # Wages come from the personnel domain through one function: this is the seam between the two
        statement = profit_and_loss(daily, expenses, lambda a, b: labor_cost(conn, a, b), start, end)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "sales/profit_loss.html",
        {
            "start": start,
            "end": end,
            "month": month,
            "pl": statement,
            "expenses": expenses,
            "errors": errors or [],
            "form": form or {"month": month},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/profit-loss", response_class=HTMLResponse)
def profit_loss_page(request: Request, added: str = None):
    return _profit_loss_page(request, added=added)


@router.post("/profit-loss/expenses", response_class=HTMLResponse)
def create_fixed_expense(
    request: Request,
    description: str = Form(""),
    amount: str = Form(""),
    month: str = Form(""),
):
    form = {"description": description, "amount": amount, "month": month}
    try:
        expense = FixedExpenseIn(**form)
    except ValidationError as error:
        messages = [f"{e['loc'][0].capitalize()}: {e['msg'].lower()}" for e in error.errors()]
        return _profit_loss_page(request, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        repository.add_fixed_expense(conn, expense.description, expense.amount, expense.month)
    finally:
        conn.close()
    return RedirectResponse(url=f"/sales/profit-loss?added={expense.description}", status_code=303)