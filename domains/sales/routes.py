"""Web pages of the sales domain.

Each route only does the web part: read the form, ask the repository for data, let the services
decide (calculations and business rules), and choose which page or redirect to send back.
The database connection comes from Depends(get_db), which also closes it after the request.
"""
from datetime import date
from typing import List
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from accounts.dependencies import current_restaurant
from database import get_db
from domains.sales import repository, services, wages  # wages: the only way sales gets numbers from personnel (ADR-2)
from domains.sales.schemas import CATEGORIES, DishIn, FixedExpenseIn, IngredientIn, PurchaseIn, SupplierIn
from web import form_errors, templates

router = APIRouter(prefix="/sales", tags=["sales"])

DISH_LABELS = {"recipe quantity": "Ingredient quantity", "recipe ingredient_id": "Ingredient"}
INGREDIENT_LABELS = {"": "Supplier"}       # the "choose a supplier or add one" rule is about the supplier


def _redirect(path, **params):
    """Post/Redirect/Get: send the browser to `path` with an encoded query string.

    Encoding matters for names typed by the user: 'Gas & water' would otherwise be cut at the '&'.
    Reloading the page after the redirect does not submit the form twice.
    """
    return RedirectResponse(url=f"{path}?{urlencode(params)}", status_code=303)


def _ingredient_ids(conn, restaurant_id):
    return {i["id"] for i in repository.get_ingredient_choices(conn, restaurant_id)}


# ---------- Menu performance ----------

@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    dishes = services.classify_menu(repository.get_dish_sales(conn, restaurant_id))
    by_category = {c: [] for c in CATEGORIES}
    for dish in sorted(dishes, key=lambda d: d["units_sold"], reverse=True):
        if dish["class"] != "new":
            by_category[dish["category"]].append(dish)

    return templates.TemplateResponse(
        request,
        "sales/menu.html",
        {
            "by_category": by_category,
            "new_dishes": [d for d in dishes if d["class"] == "new"],
            "summary": services.menu_summary(dishes),
        },
    )


# ---------- Menu and recipes ----------

def _dishes_page(request, conn, restaurant_id, errors=None, form=None, added=None, status_code=200, updated=None):
    costed = services.cost_dishes(repository.get_menu(conn, restaurant_id),
                                  repository.get_recipe_lines(conn, restaurant_id))
    by_category = {c: [d for d in costed if d["category"] == c] for c in CATEGORIES}
    return templates.TemplateResponse(
        request,
        "sales/dishes.html",
        {
            "by_category": by_category,
            "summary": services.dishes_summary(costed),
            "target": services.FOOD_COST_TARGET,
            "ingredients": repository.get_ingredient_choices(conn, restaurant_id),
            "categories": CATEGORIES,
            "errors": errors or [],
            "form": form or {},
            "added": added,
            "updated": updated,
        },
        status_code=status_code,
    )


@router.get("/dishes", response_class=HTMLResponse)
def dishes_page(request: Request, added: str = None, updated: str = None, conn=Depends(get_db),
                restaurant_id: int = Depends(current_restaurant)):
    return _dishes_page(request, conn, restaurant_id, added=added, updated=updated)


def _read_dish_form(name, category, price, ingredient_id, quantity):
    """Validates the dish form. Returns (dish or None, error messages, form values to show again)."""
    # The form has several recipe rows; rows left without an ingredient are ignored
    rows = [(i, q) for i, q in zip(ingredient_id, quantity) if i]
    form = {"name": name, "category": category, "price": price, "rows": rows}
    try:
        dish = DishIn(name=name, category=category, price=price,
                      recipe=[{"ingredient_id": i, "quantity": q} for i, q in rows])
    except ValidationError as error:
        return None, form_errors(error, DISH_LABELS), form
    return dish, [], form


@router.post("/dishes", response_class=HTMLResponse)
def create_dish(
    request: Request,
    name: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    ingredient_id: List[str] = Form([]),
    quantity: List[str] = Form([]),
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    dish, errors, form = _read_dish_form(name, category, price, ingredient_id, quantity)
    problem = dish and services.dish_problem(dish, _ingredient_ids(conn, restaurant_id))
    if errors or problem:
        return _dishes_page(request, conn, restaurant_id, errors=errors or [problem], form=form, status_code=422)

    code = services.new_dish_code(dish.name, {d["code"] for d in repository.get_menu(conn, restaurant_id)})
    repository.add_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                        [(line.ingredient_id, line.quantity) for line in dish.recipe])
    return _redirect("/sales/dishes", added=dish.name)


def _dish_edit_page(request, conn, restaurant_id, code, errors=None, form=None, status_code=200):
    dish = repository.get_dish(conn, restaurant_id, code)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    recipe = repository.get_recipe(conn, restaurant_id, code)
    return templates.TemplateResponse(
        request,
        "sales/dish_edit.html",
        {
            "dish": dish,
            "form": form or {**dish, "rows": [(str(i), f"{q:g}") for i, q in recipe]},
            "errors": errors or [],
            "categories": CATEGORIES,
            "ingredients": repository.get_ingredient_choices(conn, restaurant_id),
            "target": services.FOOD_COST_TARGET,
        },
        status_code=status_code,
    )


@router.get("/dishes/{code}/edit", response_class=HTMLResponse)
def edit_dish_page(request: Request, code: str, conn=Depends(get_db),
                   restaurant_id: int = Depends(current_restaurant)):
    return _dish_edit_page(request, conn, restaurant_id, code)


@router.post("/dishes/{code}/edit", response_class=HTMLResponse)
def update_dish(
    request: Request,
    code: str,
    name: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    ingredient_id: List[str] = Form([]),
    quantity: List[str] = Form([]),
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    if repository.get_dish(conn, restaurant_id, code) is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    dish, errors, form = _read_dish_form(name, category, price, ingredient_id, quantity)
    problem = dish and services.dish_problem(dish, _ingredient_ids(conn, restaurant_id))
    if errors or problem:
        return _dish_edit_page(request, conn, restaurant_id, code, errors=errors or [problem], form=form,
                               status_code=422)

    repository.update_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                           [(line.ingredient_id, line.quantity) for line in dish.recipe])
    return _redirect("/sales/dishes", updated=dish.name)


# ---------- Inventory: ingredients and suppliers ----------

def _inventory_page(request, conn, restaurant_id, errors=None, form=None, added=None, status_code=200,
                    ingredient_errors=None, ingredient_form=None):
    as_of = repository.get_last_order_day(conn, restaurant_id)
    stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
    return templates.TemplateResponse(
        request,
        "sales/inventory.html",
        {
            "stock": stock,
            "as_of": as_of,
            "summary": services.inventory_summary(stock),
            "suppliers": repository.get_suppliers(conn, restaurant_id),
            "ingredients": repository.get_ingredient_choices(conn, restaurant_id),
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
def inventory_page(request: Request, added: str = None, conn=Depends(get_db),
                   restaurant_id: int = Depends(current_restaurant)):
    return _inventory_page(request, conn, restaurant_id, added=added)


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
    conn=Depends(get_db),
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
        return _inventory_page(request, conn, restaurant_id, ingredient_errors=form_errors(error, INGREDIENT_LABELS),
                               ingredient_form=form, status_code=422)

    suppliers = repository.get_suppliers(conn, restaurant_id)
    problem = services.ingredient_problem(
        ingredient,
        [i["name"] for i in repository.get_ingredient_choices(conn, restaurant_id)],
        {s["id"] for s in suppliers},
        [s["name"] for s in suppliers],
    )
    if problem:
        return _inventory_page(request, conn, restaurant_id, ingredient_errors=[problem], ingredient_form=form,
                               status_code=422)

    new = ingredient.new_supplier
    saved_supplier = repository.add_ingredient(
        conn, restaurant_id, ingredient.name, ingredient.unit, ingredient.unit_cost, ingredient.counted_stock,
        ingredient.counted_at.isoformat(), ingredient.reorder_level,
        supplier_id=ingredient.supplier_id,
        new_supplier=(new.name, new.phone, new.email, new.lead_time_days) if new else None,
    )
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
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"name": name, "phone": phone, "email": email, "lead_time_days": lead_time_days,
            # the ticked boxes are shown again if the form has errors
            "ingredient_ids": [int(i) for i in ingredient_ids if i.isdigit()]}
    try:
        supplier = SupplierIn(**{**form, "ingredient_ids": ingredient_ids})
    except ValidationError as error:
        return _inventory_page(request, conn, restaurant_id, errors=form_errors(error), form=form, status_code=422)

    problem = services.supplier_problem(supplier, [s["name"] for s in repository.get_suppliers(conn, restaurant_id)],
                                        _ingredient_ids(conn, restaurant_id))
    if problem:
        return _inventory_page(request, conn, restaurant_id, errors=[problem], form=form, status_code=422)

    repository.add_supplier(conn, restaurant_id, supplier.name, supplier.phone, supplier.email,
                            supplier.lead_time_days, supplier.ingredient_ids)
    return _redirect("/sales/inventory", added=supplier.name)


def _ingredient_edit_page(request, conn, restaurant_id, ingredient_id, errors=None, form=None, status_code=200):
    ingredient = repository.get_ingredient(conn, restaurant_id, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return templates.TemplateResponse(
        request,
        "sales/ingredient_edit.html",
        {"ingredient": ingredient, "suppliers": repository.get_suppliers(conn, restaurant_id),
         "form": form or ingredient, "errors": errors or []},
        status_code=status_code,
    )


@router.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
def edit_ingredient_page(request: Request, ingredient_id: int, conn=Depends(get_db),
                         restaurant_id: int = Depends(current_restaurant)):
    return _ingredient_edit_page(request, conn, restaurant_id, ingredient_id)


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
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    if repository.get_ingredient(conn, restaurant_id, ingredient_id) is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    form = {"name": name, "unit": unit, "unit_cost": unit_cost, "counted_stock": counted_stock,
            "reorder_level": reorder_level, "counted_at": counted_at, "supplier_id": supplier_id}
    try:
        ingredient = IngredientIn(**form)      # same rules as when the ingredient was added
    except ValidationError as error:
        return _ingredient_edit_page(request, conn, restaurant_id, ingredient_id,
                                     errors=form_errors(error, INGREDIENT_LABELS), form=form, status_code=422)

    suppliers = repository.get_suppliers(conn, restaurant_id)
    problem = services.ingredient_problem(
        ingredient,
        [i["name"] for i in repository.get_ingredient_choices(conn, restaurant_id) if i["id"] != ingredient_id],
        {s["id"] for s in suppliers},
        [s["name"] for s in suppliers],
    )
    if problem:
        return _ingredient_edit_page(request, conn, restaurant_id, ingredient_id, errors=[problem], form=form,
                                     status_code=422)

    repository.update_ingredient(conn, restaurant_id, ingredient_id, ingredient.name, ingredient.unit,
                                 ingredient.unit_cost, ingredient.supplier_id, ingredient.counted_stock,
                                 ingredient.counted_at.isoformat(), ingredient.reorder_level)
    return _redirect(f"/sales/suppliers/{ingredient.supplier_id}", updated=ingredient.name)


def _supplier_edit_page(request, conn, restaurant_id, supplier_id, errors=None, form=None, status_code=200):
    supplier = repository.get_supplier(conn, restaurant_id, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return templates.TemplateResponse(
        request,
        "sales/supplier_edit.html",
        {"supplier": supplier, "form": form or supplier, "errors": errors or []},
        status_code=status_code,
    )


@router.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def edit_supplier_page(request: Request, supplier_id: int, conn=Depends(get_db),
                       restaurant_id: int = Depends(current_restaurant)):
    return _supplier_edit_page(request, conn, restaurant_id, supplier_id)


@router.post("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def update_supplier(
    request: Request,
    supplier_id: int,
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    lead_time_days: str = Form(""),
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    if repository.get_supplier(conn, restaurant_id, supplier_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    form = {"name": name, "phone": phone, "email": email, "lead_time_days": lead_time_days}
    try:
        supplier = SupplierIn(**form)          # same rules as a new supplier: phone or email required
    except ValidationError as error:
        return _supplier_edit_page(request, conn, restaurant_id, supplier_id, errors=form_errors(error), form=form,
                                   status_code=422)

    others = [s["name"] for s in repository.get_suppliers(conn, restaurant_id) if s["id"] != supplier_id]
    problem = services.supplier_problem(supplier, others, set())
    if problem:
        return _supplier_edit_page(request, conn, restaurant_id, supplier_id, errors=[problem], form=form,
                                   status_code=422)

    repository.update_supplier(conn, restaurant_id, supplier_id, supplier.name, supplier.phone,
                               supplier.email, supplier.lead_time_days)
    return _redirect(f"/sales/suppliers/{supplier_id}", updated=supplier.name)


# ---------- A supplier's page and its deliveries ----------

def _supplier_page(request, conn, restaurant_id, supplier_id, errors=None, form=None, added=False, status_code=200,
                   new_ingredient=None, updated=None):
    supplier = repository.get_supplier(conn, restaurant_id, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    as_of = repository.get_last_order_day(conn, restaurant_id)
    stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
    purchases = repository.get_purchases(conn, restaurant_id, supplier_id)
    items = [item for item in stock if item["supplier_id"] == supplier_id]
    return templates.TemplateResponse(
        request,
        "sales/supplier.html",
        {
            "supplier": supplier,
            "items": items,
            "purchases": purchases,
            "summary": services.supplier_summary(items, purchases),
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
                  updated: str = None, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    return _supplier_page(request, conn, restaurant_id, supplier_id, added=added, new_ingredient=new_ingredient,
                          updated=updated)


@router.post("/suppliers/{supplier_id}/purchases", response_class=HTMLResponse)
def record_purchase(
    request: Request,
    supplier_id: int,
    ingredient_id: str = Form(""),
    quantity: str = Form(""),
    unit_price: str = Form(""),
    received_on: str = Form(""),
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"ingredient_id": ingredient_id, "quantity": quantity, "unit_price": unit_price, "received_on": received_on}
    try:
        purchase = PurchaseIn(**form)
    except ValidationError as error:
        return _supplier_page(request, conn, restaurant_id, supplier_id, errors=form_errors(error), form=form,
                              status_code=422)

    sold_here = {i["id"] for i in repository.get_stock_levels(conn, restaurant_id) if i["supplier_id"] == supplier_id}
    problem = services.purchase_problem(purchase, sold_here)
    if problem:
        return _supplier_page(request, conn, restaurant_id, supplier_id, errors=[problem], form=form, status_code=422)

    repository.add_purchase(conn, supplier_id, purchase.ingredient_id, purchase.quantity,
                            purchase.unit_price, purchase.received_on.isoformat())
    return _redirect(f"/sales/suppliers/{supplier_id}", added="true")


# ---------- Profit and loss ----------

def _profit_loss_page(request, conn, restaurant_id, month=None, errors=None, form=None, added=None, status_code=200):
    current = date.today().strftime("%Y-%m")    # the only place that reads today's date, so the logic stays testable
    months = repository.get_months(conn, restaurant_id)
    last_day = repository.get_last_order_day(conn, restaurant_id)
    month = services.choose_month(months, month, last_day[:7] if last_day else None, current)
    start, end = repository.get_sales_period_in_month(conn, restaurant_id, month)
    daily = repository.get_daily_sales(conn, restaurant_id, start, end) if start else []
    expenses = repository.get_fixed_expenses(conn, restaurant_id, month)
    # Wages come from the personnel domain through one function: this is the seam between the two
    labor_cost_for = wages.in_process(restaurant_id)
    first, last = repository.get_sales_period(conn, restaurant_id)
    history = services.month_history(repository.get_daily_sales(conn, restaurant_id, first, last) if first else [],
                                     repository.get_all_fixed_expenses(conn, restaurant_id), labor_cost_for, months)

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
            "prev_month": services.shift_month(month, -1),
            "next_month": services.shift_month(month, 1) if month < latest else None,
            "history": history,
            "pl": services.profit_and_loss(daily, expenses, labor_cost_for, start, end),
            "expenses": expenses,
            "errors": errors or [],
            "form": form or {"month": month},
            "added": added,
        },
        status_code=status_code,
    )


@router.get("/profit-loss", response_class=HTMLResponse)
def profit_loss_page(request: Request, month: str = None, added: str = None, conn=Depends(get_db),
                     restaurant_id: int = Depends(current_restaurant)):
    return _profit_loss_page(request, conn, restaurant_id, month=month, added=added)


@router.post("/profit-loss/expenses", response_class=HTMLResponse)
def create_fixed_expense(
    request: Request,
    description: str = Form(""),
    amount: str = Form(""),
    month: str = Form(""),
    conn=Depends(get_db),
    restaurant_id: int = Depends(current_restaurant),
):
    form = {"description": description, "amount": amount, "month": month}
    try:
        expense = FixedExpenseIn(**form)
    except ValidationError as error:
        return _profit_loss_page(request, conn, restaurant_id, month=month, errors=form_errors(error), form=form,
                                 status_code=422)

    repository.add_fixed_expense(conn, restaurant_id, expense.description, expense.amount, expense.month)
    # Show the month the expense belongs to, which may not be the one that was on screen
    return _redirect("/sales/profit-loss", month=expense.month, added=expense.description)