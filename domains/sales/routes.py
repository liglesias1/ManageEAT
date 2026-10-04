"""Web pages of the sales domain."""
from typing import List

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from database import get_connection
from domains.personnel.services import labor_cost  # the only thing sales uses from personnel (see ADR-2)
from domains.sales import repository
from domains.sales.repository import get_dish_sales
from domains.sales.schemas import DishIn, FixedExpenseIn, IngredientIn, PurchaseIn, SupplierIn
from domains.sales.services import (
    FOOD_COST_TARGET,
    classify_menu,
    cost_dishes,
    dishes_summary,
    inventory_summary,
    menu_summary,
    new_dish_code,
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
        if dish["class"] != "new":
            by_category[dish["category"]].append(dish)

    return templates.TemplateResponse(
        request,
        "sales/menu.html",
        {
            "by_category": by_category,
            "new_dishes": [d for d in dishes if d["class"] == "new"],
            "summary": menu_summary(dishes),
        },
    )


def _dishes_page(request, errors=None, form=None, added=None, status_code=200):
    conn = get_connection()
    try:
        costed = cost_dishes(repository.get_menu(conn), repository.get_recipe_lines(conn))
        ingredients = repository.get_ingredient_choices(conn)
    finally:
        conn.close()

    by_category = {c: [d for d in costed if d["category"] == c] for c in CATEGORY_ORDER}
    return templates.TemplateResponse(
        request,
        "sales/dishes.html",
        {
            "by_category": by_category,
            "summary": dishes_summary(costed),
            "target": FOOD_COST_TARGET,
            "ingredients": ingredients,
            "categories": CATEGORY_ORDER,
            "errors": errors or [],
            "form": form or {},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/dishes", response_class=HTMLResponse)
def dishes_page(request: Request, added: str = None):
    return _dishes_page(request, added=added)


@router.post("/dishes", response_class=HTMLResponse)
def create_dish(
    request: Request,
    name: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    ingredient_id: List[str] = Form([]),
    quantity: List[str] = Form([]),
):
    # The form has several recipe rows; rows left without an ingredient are ignored
    rows = [(i, q) for i, q in zip(ingredient_id, quantity) if i]
    form = {"name": name, "category": category, "price": price, "rows": rows}
    try:
        dish = DishIn(
            name=name,
            category=category,
            price=price,
            recipe=[{"ingredient_id": i, "quantity": q} for i, q in rows],
        )
    except ValidationError as error:
        messages = []
        for e in error.errors():
            field = "Ingredient quantity" if e["loc"][0] == "recipe" and len(e["loc"]) > 1 else e["loc"][0].capitalize()
            if e["loc"][0] == "recipe" and e["type"] == "too_short":
                messages.append("Recipe: add at least one ingredient")
            else:
                messages.append(f"{field}: {e['msg'].replace('Value error, ', '').lower()}")
        return _dishes_page(request, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        known = {i["id"] for i in repository.get_ingredient_choices(conn)}
        if any(line.ingredient_id not in known for line in dish.recipe):
            return _dishes_page(request, errors=["Recipe: unknown ingredient"], form=form, status_code=422)
        code = new_dish_code(dish.name, {d["code"] for d in repository.get_menu(conn)})
        repository.add_dish(conn, code, dish.name, dish.category, dish.price,
                            [(line.ingredient_id, line.quantity) for line in dish.recipe])
    finally:
        conn.close()
    return RedirectResponse(url=f"/sales/dishes?added={dish.name}", status_code=303)


def _inventory_page(request, errors=None, form=None, added=None, status_code=200,
                    ingredient_errors=None, ingredient_form=None):
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
            # The page has two forms (ingredient and supplier), each with its own messages
            "ingredient_errors": ingredient_errors or [],
            "ingredient_form": ingredient_form or {"counted_at": as_of, "unit": "kg", "supplier_choice": "existing"},
        },
        status_code=status_code,
    )


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, added: str = None):
    return _inventory_page(request, added=added)


@router.post("/inventory/ingredients", response_class=HTMLResponse)
def create_ingredient(
    request: Request,
    name: str = Form(""),
    unit: str = Form(""),
    unit_cost: str = Form(""),
    counted_stock: str = Form(""),
    reorder_level: str = Form(""),
    counted_at: str = Form(""),
    supplier_choice: str = Form("existing"),
    supplier_id: str = Form(""),
    new_supplier_name: str = Form(""),
    new_supplier_phone: str = Form(""),
    new_supplier_email: str = Form(""),
    new_supplier_lead_time: str = Form(""),
):
    form = {"name": name, "unit": unit, "unit_cost": unit_cost, "counted_stock": counted_stock,
            "reorder_level": reorder_level, "counted_at": counted_at, "supplier_choice": supplier_choice,
            "supplier_id": supplier_id, "new_supplier_name": new_supplier_name, "new_supplier_phone": new_supplier_phone,
            "new_supplier_email": new_supplier_email, "new_supplier_lead_time": new_supplier_lead_time}
    data = {key: form[key] for key in ("name", "unit", "unit_cost", "counted_stock", "reorder_level", "counted_at")}
    if supplier_choice == "new":
        data["new_supplier"] = {"name": new_supplier_name, "phone": new_supplier_phone,
                                "email": new_supplier_email, "lead_time_days": new_supplier_lead_time}
    else:
        data["supplier_id"] = supplier_id
    try:
        ingredient = IngredientIn(**data)
    except ValidationError as error:
        messages = []
        for e in error.errors():
            # e.g. ("new_supplier", "email") -> "New supplier email"
            where = " ".join(str(part) for part in e["loc"]).replace("_", " ").capitalize() or "Supplier"
            messages.append(f"{where}: {e['msg'].replace('Value error, ', '').lower()}")
        return _inventory_page(request, ingredient_errors=messages, ingredient_form=form, status_code=422)

    conn = get_connection()
    try:
        problem = None
        if ingredient.supplier_id is not None and repository.get_supplier(conn, ingredient.supplier_id) is None:
            problem = "Supplier: choose one of the suppliers in the list"
        elif ingredient.name.lower() in {i["name"].lower() for i in repository.get_ingredient_choices(conn)}:
            problem = "Name: there is already an ingredient with that name"
        else:
            new = ingredient.new_supplier
            saved_supplier = repository.add_ingredient(
                conn, ingredient.name, ingredient.unit, ingredient.unit_cost, ingredient.counted_stock,
                ingredient.counted_at.isoformat(), ingredient.reorder_level,
                supplier_id=ingredient.supplier_id,
                new_supplier=(new.name, new.phone, new.email, new.lead_time_days) if new else None,
            )
    finally:
        conn.close()

    if problem:
        return _inventory_page(request, ingredient_errors=[problem], ingredient_form=form, status_code=422)
    # The supplier's page now lists the new product, ready to record its first delivery
    return RedirectResponse(url=f"/sales/suppliers/{saved_supplier}?new_ingredient={ingredient.name}",
                            status_code=303)


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


def _supplier_page(request, supplier_id, errors=None, form=None, added=False, status_code=200,
                   new_ingredient=None):
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
            "new_ingredient": new_ingredient,
        },
        status_code=status_code,
    )


@router.get("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_page(request: Request, supplier_id: int, added: bool = False, new_ingredient: str = None):
    return _supplier_page(request, supplier_id, added=added, new_ingredient=new_ingredient)


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