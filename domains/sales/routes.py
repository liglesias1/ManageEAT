"""Web pages of the sales domain."""
from datetime import date
from typing import List
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from accounts.dependencies import current_restaurant
from database import get_connection
from domains.personnel.services import labor_cost  # the only thing sales uses from personnel (see ADR-2)
from domains.sales import repository
from domains.sales.repository import get_dish_sales
from domains.sales.schemas import DishIn, FixedExpenseIn, IngredientIn, PurchaseIn, SupplierIn
from domains.sales.services import (
    FOOD_COST_TARGET,
    choose_month,
    classify_menu,
    cost_dishes,
    dishes_summary,
    inventory_summary,
    menu_summary,
    month_history,
    new_dish_code,
    profit_and_loss,
    shift_month,
    stock_status,
    supplier_summary,
)
from web import templates

router = APIRouter(prefix="/sales", tags=["sales"])

CATEGORY_ORDER = ["main", "starter", "dessert", "drink"]


def _redirect(path, **params):
    """Post/Redirect/Get: send the browser to `path` with an encoded query string.

    Encoding matters for names typed by the user: 'Gas & water' would otherwise be cut at the '&'.
    Reloading the page after the redirect does not submit the form twice.
    """
    return RedirectResponse(url=f"{path}?{urlencode(params)}", status_code=303)


@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request, restaurant_id: int = Depends(current_restaurant)):
    conn = get_connection()
    try:
        dishes = classify_menu(get_dish_sales(conn, restaurant_id))
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


def _dishes_page(request, restaurant_id, errors=None, form=None, added=None, status_code=200, updated=None):
    conn = get_connection()
    try:
        costed = cost_dishes(repository.get_menu(conn, restaurant_id),
                             repository.get_recipe_lines(conn, restaurant_id))
        ingredients = repository.get_ingredient_choices(conn, restaurant_id)
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
            "updated": updated,
        },
        status_code=status_code,
    )


@router.get("/dishes", response_class=HTMLResponse)
def dishes_page(request: Request, added: str = None, updated: str = None,
                restaurant_id: int = Depends(current_restaurant)):
    return _dishes_page(request, restaurant_id, added=added, updated=updated)


def _read_dish_form(name, category, price, ingredient_id, quantity):
    """Validates the dish form. Returns (dish or None, error messages, form values to show again)."""
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
        return None, messages, form
    return dish, [], form


def _unknown_ingredients(conn, restaurant_id, dish):
    known = {i["id"] for i in repository.get_ingredient_choices(conn, restaurant_id)}
    return any(line.ingredient_id not in known for line in dish.recipe)


@router.post("/dishes", response_class=HTMLResponse)
def create_dish(
    request: Request,
    name: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    ingredient_id: List[str] = Form([]),
    quantity: List[str] = Form([]),
    restaurant_id: int = Depends(current_restaurant),
):
    dish, errors, form = _read_dish_form(name, category, price, ingredient_id, quantity)
    if errors:
        return _dishes_page(request, restaurant_id, errors=errors, form=form, status_code=422)

    conn = get_connection()
    try:
        if _unknown_ingredients(conn, restaurant_id, dish):
            return _dishes_page(request, restaurant_id, errors=["Recipe: unknown ingredient"], form=form,
                                status_code=422)
        code = new_dish_code(dish.name, {d["code"] for d in repository.get_menu(conn, restaurant_id)})
        repository.add_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                            [(line.ingredient_id, line.quantity) for line in dish.recipe])
    finally:
        conn.close()
    return _redirect("/sales/dishes", added=dish.name)


def _dish_edit_page(request, restaurant_id, code, errors=None, form=None, status_code=200):
    conn = get_connection()
    try:
        dish = repository.get_dish(conn, restaurant_id, code)
        if dish is None:
            raise HTTPException(status_code=404, detail="Dish not found")
        recipe = repository.get_recipe(conn, restaurant_id, code)
        ingredients = repository.get_ingredient_choices(conn, restaurant_id)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "sales/dish_edit.html",
        {
            "dish": dish,
            "form": form or {**dish, "rows": [(str(i), f"{q:g}") for i, q in recipe]},
            "errors": errors or [],
            "categories": CATEGORY_ORDER,
            "ingredients": ingredients,
            "target": FOOD_COST_TARGET,
        },
        status_code=status_code,
    )


@router.get("/dishes/{code}/edit", response_class=HTMLResponse)
def edit_dish_page(request: Request, code: str,
                   restaurant_id: int = Depends(current_restaurant)):
    return _dish_edit_page(request, restaurant_id, code)


@router.post("/dishes/{code}/edit", response_class=HTMLResponse)
def update_dish(
    request: Request,
    code: str,
    name: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    ingredient_id: List[str] = Form([]),
    quantity: List[str] = Form([]),
    restaurant_id: int = Depends(current_restaurant),
):
    dish, errors, form = _read_dish_form(name, category, price, ingredient_id, quantity)
    if errors:
        return _dish_edit_page(request, restaurant_id, code, errors=errors, form=form, status_code=422)

    conn = get_connection()
    try:
        if repository.get_dish(conn, restaurant_id, code) is None:
            raise HTTPException(status_code=404, detail="Dish not found")
        if _unknown_ingredients(conn, restaurant_id, dish):
            return _dish_edit_page(request, restaurant_id, code, errors=["Recipe: unknown ingredient"], form=form,
                                   status_code=422)
        repository.update_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                               [(line.ingredient_id, line.quantity) for line in dish.recipe])
    finally:
        conn.close()
    return _redirect("/sales/dishes", updated=dish.name)


def _inventory_page(request, restaurant_id, errors=None, form=None, added=None, status_code=200,
                    ingredient_errors=None, ingredient_form=None):
    conn = get_connection()
    try:
        as_of = repository.get_last_order_day(conn, restaurant_id)
        stock = stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
        suppliers = repository.get_suppliers(conn, restaurant_id)
        ingredients = repository.get_ingredient_choices(conn, restaurant_id)
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
def inventory_page(request: Request, added: str = None,
                   restaurant_id: int = Depends(current_restaurant)):
    return _inventory_page(request, restaurant_id, added=added)


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
    restaurant_id: int = Depends(current_restaurant),
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
        return _inventory_page(request, restaurant_id, ingredient_errors=messages, ingredient_form=form,
                               status_code=422)

    conn = get_connection()
    try:
        problem = None
        names_in_use = {i["name"].lower() for i in repository.get_ingredient_choices(conn, restaurant_id)}
        if ingredient.supplier_id is not None and repository.get_supplier(conn, restaurant_id,
                                                                          ingredient.supplier_id) is None:
            problem = "Supplier: choose one of the suppliers in the list"
        elif ingredient.name.lower() in names_in_use:
            problem = "Name: there is already an ingredient with that name"
        elif ingredient.new_supplier and _supplier_name_taken(conn, restaurant_id, ingredient.new_supplier.name):
            problem = "New supplier name: that supplier already exists, choose it from the list"
        else:
            new = ingredient.new_supplier
            saved_supplier = repository.add_ingredient(
                conn, restaurant_id, ingredient.name, ingredient.unit, ingredient.unit_cost, ingredient.counted_stock,
                ingredient.counted_at.isoformat(), ingredient.reorder_level,
                supplier_id=ingredient.supplier_id,
                new_supplier=(new.name, new.phone, new.email, new.lead_time_days) if new else None,
            )
    finally:
        conn.close()

    if problem:
        return _inventory_page(request, restaurant_id, ingredient_errors=[problem], ingredient_form=form,
                               status_code=422)
    # The supplier's page now lists the new product, ready to record its first delivery
    return _redirect(f"/sales/suppliers/{saved_supplier}", new_ingredient=ingredient.name)


@router.post("/inventory/suppliers", response_class=HTMLResponse)
def create_supplier(
    request: Request,
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    lead_time_days: str = Form(""),
    ingredient_ids: List[str] = Form([]),   # read as text, so a bad value gets a message instead of a JSON error
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"name": name, "phone": phone, "email": email, "lead_time_days": lead_time_days,
            # the ticked boxes are shown again if the form has errors
            "ingredient_ids": [int(i) for i in ingredient_ids if i.isdigit()]}
    try:
        supplier = SupplierIn(**{**form, "ingredient_ids": ingredient_ids})
    except ValidationError as error:
        messages = [e["msg"].replace("Value error, ", "").capitalize() for e in error.errors()]
        return _inventory_page(request, restaurant_id, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        problem = None
        known = {i["id"] for i in repository.get_ingredient_choices(conn, restaurant_id)}
        if _supplier_name_taken(conn, restaurant_id, supplier.name):
            problem = "Name: there is already a supplier with that name"
        elif any(i not in known for i in supplier.ingredient_ids):
            problem = "Ingredients: choose ingredients from the list"
        else:
            repository.add_supplier(conn, restaurant_id, supplier.name, supplier.phone, supplier.email,
                                    supplier.lead_time_days, supplier.ingredient_ids)
    finally:
        conn.close()

    if problem:
        return _inventory_page(request, restaurant_id, errors=[problem], form=form, status_code=422)
    return _redirect("/sales/inventory", added=supplier.name)


def _supplier_name_taken(conn, restaurant_id, name, except_id=None):
    """True if another supplier already has this name, ignoring upper and lower case."""
    suppliers = repository.get_suppliers(conn, restaurant_id)
    return any(s["name"].lower() == name.lower() and s["id"] != except_id for s in suppliers)


def _error_messages(error):
    """Pydantic errors as short sentences for the forms, e.g. 'Unit cost: input should be greater than 0'."""
    messages = []
    for e in error.errors():
        where = " ".join(str(part) for part in e["loc"]).replace("_", " ").capitalize()
        message = e["msg"].replace("Value error, ", "")
        messages.append(f"{where}: {message.lower()}" if where else message.capitalize())
    return messages


def _ingredient_edit_page(request, restaurant_id, ingredient_id, errors=None, form=None, status_code=200):
    conn = get_connection()
    try:
        ingredient = repository.get_ingredient(conn, restaurant_id, ingredient_id)
        if ingredient is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        suppliers = repository.get_suppliers(conn, restaurant_id)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "sales/ingredient_edit.html",
        {"ingredient": ingredient, "suppliers": suppliers, "form": form or ingredient, "errors": errors or []},
        status_code=status_code,
    )


@router.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
def edit_ingredient_page(request: Request, ingredient_id: int,
                         restaurant_id: int = Depends(current_restaurant)):
    return _ingredient_edit_page(request, restaurant_id, ingredient_id)


@router.post("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
def update_ingredient(
    request: Request,
    ingredient_id: int,
    name: str = Form(""),
    unit: str = Form(""),
    unit_cost: str = Form(""),
    counted_stock: str = Form(""),
    reorder_level: str = Form(""),
    counted_at: str = Form(""),
    supplier_id: str = Form(""),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"name": name, "unit": unit, "unit_cost": unit_cost, "counted_stock": counted_stock,
            "reorder_level": reorder_level, "counted_at": counted_at, "supplier_id": supplier_id}
    try:
        ingredient = IngredientIn(**form)      # same rules as when the ingredient was added
    except ValidationError as error:
        return _ingredient_edit_page(request, restaurant_id, ingredient_id, errors=_error_messages(error), form=form,
                                     status_code=422)

    conn = get_connection()
    try:
        current = repository.get_ingredient(conn, restaurant_id, ingredient_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        others = {i["name"].lower() for i in repository.get_ingredient_choices(conn, restaurant_id)
                  if i["id"] != ingredient_id}
        problem = None
        if repository.get_supplier(conn, restaurant_id, ingredient.supplier_id) is None:
            problem = "Supplier: choose one of the suppliers in the list"
        elif ingredient.name.lower() in others:
            problem = "Name: there is already an ingredient with that name"
        else:
            repository.update_ingredient(conn, restaurant_id, ingredient_id, ingredient.name, ingredient.unit,
                                         ingredient.unit_cost, ingredient.supplier_id, ingredient.counted_stock,
                                         ingredient.counted_at.isoformat(), ingredient.reorder_level)
    finally:
        conn.close()

    if problem:
        return _ingredient_edit_page(request, restaurant_id, ingredient_id, errors=[problem], form=form,
                                     status_code=422)
    return _redirect(f"/sales/suppliers/{ingredient.supplier_id}", updated=ingredient.name)


def _supplier_edit_page(request, restaurant_id, supplier_id, errors=None, form=None, status_code=200):
    conn = get_connection()
    try:
        supplier = repository.get_supplier(conn, restaurant_id, supplier_id)
    finally:
        conn.close()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return templates.TemplateResponse(
        request,
        "sales/supplier_edit.html",
        {"supplier": supplier, "form": form or supplier, "errors": errors or []},
        status_code=status_code,
    )


@router.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def edit_supplier_page(request: Request, supplier_id: int,
                       restaurant_id: int = Depends(current_restaurant)):
    return _supplier_edit_page(request, restaurant_id, supplier_id)


@router.post("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def update_supplier(
    request: Request,
    supplier_id: int,
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    lead_time_days: str = Form(""),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"name": name, "phone": phone, "email": email, "lead_time_days": lead_time_days}
    try:
        supplier = SupplierIn(**form)          # same rules as a new supplier: phone or email required
    except ValidationError as error:
        return _supplier_edit_page(request, restaurant_id, supplier_id, errors=_error_messages(error), form=form,
                                   status_code=422)

    conn = get_connection()
    try:
        if repository.get_supplier(conn, restaurant_id, supplier_id) is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        taken = _supplier_name_taken(conn, restaurant_id, supplier.name, except_id=supplier_id)
        if not taken:
            repository.update_supplier(conn, restaurant_id, supplier_id, supplier.name, supplier.phone,
                                       supplier.email, supplier.lead_time_days)
    finally:
        conn.close()

    if taken:
        return _supplier_edit_page(request, restaurant_id, supplier_id,
                                   errors=["Name: there is already a supplier with that name"], form=form,
                                   status_code=422)
    return _redirect(f"/sales/suppliers/{supplier_id}", updated=supplier.name)


def _supplier_page(request, restaurant_id, supplier_id, errors=None, form=None, added=False, status_code=200,
                   new_ingredient=None, updated=None):
    conn = get_connection()
    try:
        supplier = repository.get_supplier(conn, restaurant_id, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        as_of = repository.get_last_order_day(conn, restaurant_id)
        stock = stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
        purchases = repository.get_purchases(conn, restaurant_id, supplier_id)
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
            "updated": updated,
        },
        status_code=status_code,
    )


@router.get("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_page(request: Request, supplier_id: int, added: bool = False, new_ingredient: str = None,
                  updated: str = None, restaurant_id: int = Depends(current_restaurant)):
    return _supplier_page(request, restaurant_id, supplier_id, added=added, new_ingredient=new_ingredient,
                          updated=updated)


@router.post("/suppliers/{supplier_id}/purchases", response_class=HTMLResponse)
def record_purchase(
    request: Request,
    supplier_id: int,
    ingredient_id: str = Form(""),
    quantity: str = Form(""),
    unit_price: str = Form(""),
    received_on: str = Form(""),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"ingredient_id": ingredient_id, "quantity": quantity, "unit_price": unit_price, "received_on": received_on}
    try:
        purchase = PurchaseIn(**form)
    except ValidationError as error:
        messages = [f"{e['loc'][0].replace('_', ' ').capitalize()}: {e['msg'].lower()}" for e in error.errors()]
        return _supplier_page(request, restaurant_id, supplier_id, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        sold_here = [i["id"] for i in repository.get_stock_levels(conn, restaurant_id)
                     if i["supplier_id"] == supplier_id]
        if purchase.ingredient_id in sold_here:
            repository.add_purchase(conn, supplier_id, purchase.ingredient_id, purchase.quantity,
                                    purchase.unit_price, purchase.received_on.isoformat())
    finally:
        conn.close()

    if purchase.ingredient_id not in sold_here:
        return _supplier_page(request, restaurant_id, supplier_id, errors=["This supplier does not sell that product"],
                              form=form, status_code=422)
    return _redirect(f"/sales/suppliers/{supplier_id}", added="true")


def _profit_loss_page(request, restaurant_id, month=None, errors=None, form=None, added=None, status_code=200):
    current = date.today().strftime("%Y-%m")    # the only place that reads today's date, so the logic stays testable
    conn = get_connection()
    try:
        months = repository.get_months(conn, restaurant_id)
        last_day = repository.get_last_order_day(conn, restaurant_id)
        month = choose_month(months, month, last_day[:7] if last_day else None, current)
        start, end = repository.get_sales_period_in_month(conn, restaurant_id, month)
        daily = repository.get_daily_sales(conn, restaurant_id, start, end) if start else []
        expenses = repository.get_fixed_expenses(conn, restaurant_id, month)
        # Wages come from the personnel domain through one function: this is the seam between the two
        def wages(start_day, end_day):
            return labor_cost(conn, restaurant_id, start_day, end_day)

        statement = profit_and_loss(daily, expenses, wages, start, end)
        first, last = repository.get_sales_period(conn, restaurant_id)
        history = month_history(repository.get_daily_sales(conn, restaurant_id, first, last) if first else [],
                                repository.get_all_fixed_expenses(conn, restaurant_id), wages, months)
    finally:
        conn.close()

    latest = max(months + [current])            # no "next" arrow past the current month or the last month with data
    return templates.TemplateResponse(
        request,
        "sales/profit_loss.html",
        {
            "start": start,
            "end": end,
            "month": month,
            "has_data": bool(daily or expenses),
            "in_progress": month == current,
            "prev_month": shift_month(month, -1),
            "next_month": shift_month(month, 1) if month < latest else None,
            "history": history,
            "pl": statement,
            "expenses": expenses,
            "errors": errors or [],
            "form": form or {"month": month},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/profit-loss", response_class=HTMLResponse)
def profit_loss_page(request: Request, month: str = None, added: str = None,
                     restaurant_id: int = Depends(current_restaurant)):
    return _profit_loss_page(request, restaurant_id, month=month, added=added)


@router.post("/profit-loss/expenses", response_class=HTMLResponse)
def create_fixed_expense(
    request: Request,
    description: str = Form(""),
    amount: str = Form(""),
    month: str = Form(""),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"description": description, "amount": amount, "month": month}
    try:
        expense = FixedExpenseIn(**form)
    except ValidationError as error:
        messages = [f"{e['loc'][0].capitalize()}: {e['msg'].lower()}" for e in error.errors()]
        return _profit_loss_page(request, restaurant_id, month=month, errors=messages, form=form, status_code=422)

    conn = get_connection()
    try:
        repository.add_fixed_expense(conn, restaurant_id, expense.description, expense.amount, expense.month)
    finally:
        conn.close()
    # Show the month the expense belongs to, which may not be the one that was on screen
    return _redirect("/sales/profit-loss", month=expense.month, added=expense.description)