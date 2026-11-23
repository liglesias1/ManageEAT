"""Sales API: menu performance, dishes and recipes, inventory and suppliers, profit and loss.

Each route only does the web part: read the request, ask the repository for data, let the services decide
(calculations and business rules), and answer with JSON. Every GET returns what the old page showed, so the
static UI draws the same screens. Invalid input gets 422: FastAPI's own errors for the fields, and
{"detail": "<message>"} for the business rules in services.py.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from auth import Session, current_restaurant, current_session
from database import get_db
from domain import repository, services
from domain.schemas import (CATEGORIES, CoversOut, Created, DishCreated, DishIn, DishOut, ExpenseCreated,
                            FixedExpenseIn, IngredientCreated, IngredientIn, IngredientOut, Problem, PurchaseCreated,
                            PurchaseIn, SupplierIn)
from domain.wages import Wages, personnel_client  # the only way sales gets numbers from personnel (ADR-2)

router = APIRouter(prefix="/sales", tags=["sales"],
                   responses={401: {"model": Problem, "description": "Missing, invalid or expired token"}})
NOT_FOUND = {404: {"model": Problem, "description": "Not found in the manager's restaurant"}}


def _problem(message):
    return HTTPException(status_code=422, detail=message)


def _not_found(what):
    return HTTPException(status_code=404, detail=f"{what} not found")


def _ingredient_ids(conn, restaurant_id):
    return {i["id"] for i in repository.get_ingredient_choices(conn, restaurant_id)}


# ---------- Menu performance ----------

@router.get("/menu", response_model=dict)
def menu(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Every dish classified as star, plowhorse, puzzle or dog, by category, most sold first."""
    dishes = services.classify_menu(repository.get_dish_sales(conn, restaurant_id))
    by_category = {c: [] for c in CATEGORIES}
    for dish in sorted(dishes, key=lambda d: d["units_sold"], reverse=True):
        if dish["class"] != "new":
            by_category[dish["category"]].append(dish)
    return {
        "by_category": by_category,
        "new_dishes": [d for d in dishes if d["class"] == "new"],
        "summary": services.menu_summary(dishes),
    }


# ---------- Dishes and recipes ----------

@router.get("/dishes", response_model=dict)
def dishes(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """The menu with the cost and margin of every dish, and the ingredients a recipe can use."""
    costed = services.cost_dishes(repository.get_menu(conn, restaurant_id),
                                  repository.get_recipe_lines(conn, restaurant_id))
    return {
        "by_category": {c: [d for d in costed if d["category"] == c] for c in CATEGORIES},
        "summary": services.dishes_summary(costed),
        "target": services.FOOD_COST_TARGET,
        "ingredients": repository.get_ingredient_choices(conn, restaurant_id),
        "categories": list(CATEGORIES),
    }


@router.post("/dishes", status_code=201, response_model=DishCreated)
def create_dish(dish: DishIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    problem = services.dish_problem(dish, _ingredient_ids(conn, restaurant_id))
    if problem:
        raise _problem(problem)
    code = services.new_dish_code(dish.name, {d["code"] for d in repository.get_menu(conn, restaurant_id)})
    repository.add_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                        [(line.ingredient_id, line.quantity) for line in dish.recipe])
    return {"code": code, "name": dish.name}


@router.get("/dishes/{code}", response_model=DishOut, responses=NOT_FOUND)
def get_dish(code: str, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """One dish and its recipe, to fill the edit form."""
    dish = repository.get_dish(conn, restaurant_id, code)
    if dish is None:
        raise _not_found("Dish")
    recipe = repository.get_recipe(conn, restaurant_id, code)
    return {**dish, "recipe": [{"ingredient_id": i, "quantity": q} for i, q in recipe]}


@router.put("/dishes/{code}", response_model=DishCreated, responses=NOT_FOUND)
def update_dish(code: str, dish: DishIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Replaces the dish's name, category, price and whole recipe."""
    if repository.get_dish(conn, restaurant_id, code) is None:
        raise _not_found("Dish")
    problem = services.dish_problem(dish, _ingredient_ids(conn, restaurant_id))
    if problem:
        raise _problem(problem)
    repository.update_dish(conn, restaurant_id, code, dish.name, dish.category, dish.price,
                           [(line.ingredient_id, line.quantity) for line in dish.recipe])
    return {"code": code, "name": dish.name}


# ---------- Inventory: ingredients and suppliers ----------

@router.get("/inventory", response_model=dict)
def inventory(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Current stock of every ingredient (as of the last day with orders), what to reorder, and the suppliers."""
    as_of = repository.get_last_order_day(conn, restaurant_id)
    stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
    return {
        "stock": stock,
        "as_of": as_of,
        "summary": services.inventory_summary(stock),
        "suppliers": repository.get_suppliers(conn, restaurant_id),
        "ingredients": repository.get_ingredient_choices(conn, restaurant_id),
    }


def _check_ingredient(conn, restaurant_id, ingredient, editing_id=None):
    """Raises 422 if the ingredient breaks a business rule; `editing_id` may keep its own name."""
    suppliers = repository.get_suppliers(conn, restaurant_id)
    others = [i["name"] for i in repository.get_ingredient_choices(conn, restaurant_id) if i["id"] != editing_id]
    problem = services.ingredient_problem(ingredient, others, {s["id"] for s in suppliers},
                                          [s["name"] for s in suppliers])
    if problem:
        raise _problem(problem)


@router.post("/ingredients", status_code=201, response_model=IngredientCreated)
def create_ingredient(ingredient: IngredientIn, conn=Depends(get_db),
                      restaurant_id: int = Depends(current_restaurant)):
    """A new ingredient with its first stock count, bought from an existing supplier or a new one."""
    _check_ingredient(conn, restaurant_id, ingredient)
    new = ingredient.new_supplier
    supplier_id = repository.add_ingredient(
        conn, restaurant_id, ingredient.name, ingredient.unit, ingredient.unit_cost, ingredient.counted_stock,
        ingredient.counted_at.isoformat(), ingredient.reorder_level,
        supplier_id=ingredient.supplier_id,
        new_supplier=(new.name, new.phone, new.email, new.lead_time_days) if new else None,
    )
    # The UI opens the supplier's page next, ready to record the first delivery
    return {"name": ingredient.name, "supplier_id": supplier_id}


@router.get("/ingredients/{ingredient_id}", response_model=IngredientOut, responses=NOT_FOUND)
def get_ingredient(ingredient_id: int, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    ingredient = repository.get_ingredient(conn, restaurant_id, ingredient_id)
    if ingredient is None:
        raise _not_found("Ingredient")
    return ingredient


@router.put("/ingredients/{ingredient_id}", response_model=IngredientCreated, responses=NOT_FOUND)
def update_ingredient(ingredient_id: int, ingredient: IngredientIn, conn=Depends(get_db),
                      restaurant_id: int = Depends(current_restaurant)):
    """Same rules as a new ingredient, but it can only move to a supplier that already exists."""
    if repository.get_ingredient(conn, restaurant_id, ingredient_id) is None:
        raise _not_found("Ingredient")
    if ingredient.new_supplier is not None:
        raise _problem("Supplier: choose one of the suppliers in the list")
    _check_ingredient(conn, restaurant_id, ingredient, editing_id=ingredient_id)
    repository.update_ingredient(conn, restaurant_id, ingredient_id, ingredient.name, ingredient.unit,
                                 ingredient.unit_cost, ingredient.supplier_id, ingredient.counted_stock,
                                 ingredient.counted_at.isoformat(), ingredient.reorder_level)
    return {"name": ingredient.name, "supplier_id": ingredient.supplier_id}


@router.post("/suppliers", status_code=201, response_model=Created)
def create_supplier(supplier: SupplierIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """A new supplier, which can take over some existing ingredients."""
    problem = services.supplier_problem(supplier, [s["name"] for s in repository.get_suppliers(conn, restaurant_id)],
                                        _ingredient_ids(conn, restaurant_id))
    if problem:
        raise _problem(problem)
    supplier_id = repository.add_supplier(conn, restaurant_id, supplier.name, supplier.phone, supplier.email,
                                          supplier.lead_time_days, supplier.ingredient_ids)
    return {"id": supplier_id, "name": supplier.name}


@router.get("/suppliers/{supplier_id}", response_model=dict, responses=NOT_FOUND)
def get_supplier(supplier_id: int, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """A supplier with the products it sells, their stock, and its delivery history."""
    supplier = repository.get_supplier(conn, restaurant_id, supplier_id)
    if supplier is None:
        raise _not_found("Supplier")
    as_of = repository.get_last_order_day(conn, restaurant_id)
    stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
    purchases = repository.get_purchases(conn, restaurant_id, supplier_id)
    items = [item for item in stock if item["supplier_id"] == supplier_id]
    return {
        "supplier": supplier,
        "items": items,
        "purchases": purchases,
        "summary": services.supplier_summary(items, purchases),
        "as_of": as_of,
    }


@router.put("/suppliers/{supplier_id}", response_model=Created, responses=NOT_FOUND)
def update_supplier(supplier_id: int, supplier: SupplierIn, conn=Depends(get_db),
                    restaurant_id: int = Depends(current_restaurant)):
    """Changes a supplier's name and contact; same rules as a new supplier (phone or email required)."""
    if repository.get_supplier(conn, restaurant_id, supplier_id) is None:
        raise _not_found("Supplier")
    others = [s["name"] for s in repository.get_suppliers(conn, restaurant_id) if s["id"] != supplier_id]
    problem = services.supplier_problem(supplier, others, set())
    if problem:
        raise _problem(problem)
    repository.update_supplier(conn, restaurant_id, supplier_id, supplier.name, supplier.phone,
                               supplier.email, supplier.lead_time_days)
    return {"id": supplier_id, "name": supplier.name}


@router.post("/suppliers/{supplier_id}/purchases", status_code=201, response_model=PurchaseCreated,
             responses=NOT_FOUND)
def record_purchase(supplier_id: int, purchase: PurchaseIn, conn=Depends(get_db),
                    restaurant_id: int = Depends(current_restaurant)):
    """A delivery from the supplier; it only delivers the products it sells."""
    if repository.get_supplier(conn, restaurant_id, supplier_id) is None:
        raise _not_found("Supplier")
    sold_here = {i["id"] for i in repository.get_stock_levels(conn, restaurant_id) if i["supplier_id"] == supplier_id}
    problem = services.purchase_problem(purchase, sold_here)
    if problem:
        raise _problem(problem)
    repository.add_purchase(conn, supplier_id, purchase.ingredient_id, purchase.quantity,
                            purchase.unit_price, purchase.received_on.isoformat())
    return {"supplier_id": supplier_id, "ingredient_id": purchase.ingredient_id}


# ---------- Profit and loss: the flow that crosses the seam ----------

def _wages(client=Depends(personnel_client), session: Session = Depends(current_session), conn=Depends(get_db)):
    """FastAPI gives _wages the same connection as the route: dependencies are shared within one request."""
    return Wages(client, session.token, conn, session.restaurant_id)


@router.get("/profit-loss", response_model=dict)
def profit_loss(month: str = None, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant),
                wages: Wages = Depends(_wages)):
    """The monthly statement, week by week, and the history of every month.

    Wages come from personnel. If it does not answer, the last wages received are used and `wages` says
    from when; if there are none, every figure that depends on wages is null, while revenue, ingredients
    and fixed costs are still shown (ADR-6).
    """
    current = date.today().strftime("%Y-%m")    # the only place that reads today's date, so the logic stays testable
    months = repository.get_months(conn, restaurant_id)
    last_day = repository.get_last_order_day(conn, restaurant_id)
    month = services.choose_month(months, month, last_day[:7] if last_day else None, current)
    start, end = repository.get_sales_period_in_month(conn, restaurant_id, month)
    daily = repository.get_daily_sales(conn, restaurant_id, start, end) if start else []
    expenses = repository.get_fixed_expenses(conn, restaurant_id, month)
    first, last = repository.get_sales_period(conn, restaurant_id)

    statement = services.profit_and_loss(daily, expenses, wages.labor_cost_for, start, end)
    history = services.month_history(repository.get_daily_sales(conn, restaurant_id, first, last) if first else [],
                                     repository.get_all_fixed_expenses(conn, restaurant_id),
                                     wages.labor_cost_for, months)
    if wages.source == "unavailable":
        statement = services.without_wages(statement)
        history = [services.without_wages(row) for row in history]

    latest = max(months + [current])            # no "next" arrow past the current month or the last month with data
    return {
        "month": month,
        "start": start,
        "end": end,
        "has_data": bool(daily or expenses),
        "in_progress": month == current,
        "prev_month": services.shift_month(month, -1),
        "next_month": services.shift_month(month, 1) if month < latest else None,
        "wages": wages.report(),
        "pl": statement,
        "history": history,
        "expenses": expenses,
    }


@router.post("/expenses", status_code=201, response_model=ExpenseCreated)
def create_fixed_expense(expense: FixedExpenseIn, conn=Depends(get_db),
                         restaurant_id: int = Depends(current_restaurant)):
    repository.add_fixed_expense(conn, restaurant_id, expense.description, expense.amount, expense.month)
    # The UI shows the month the expense belongs to, which may not be the one that was on screen
    return {"description": expense.description, "month": expense.month}


# ---------- Overview, and what personnel asks for ----------

@router.get("/summary", response_model=dict)
def summary(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant), wages: Wages = Depends(_wages)):
    """The sales figures of the overview page, for the month the profit and loss opens on."""
    current = date.today().strftime("%Y-%m")
    dishes_sold = services.classify_menu(repository.get_dish_sales(conn, restaurant_id))
    as_of = repository.get_last_order_day(conn, restaurant_id)
    stock = services.stock_status(repository.get_stock_levels(conn, restaurant_id), as_of)
    months = repository.get_months(conn, restaurant_id)
    month = services.choose_month(months, None, as_of[:7] if as_of else None, current)
    start, end = repository.get_sales_period_in_month(conn, restaurant_id, month)
    daily = repository.get_daily_sales(conn, restaurant_id, start, end) if start else []
    expenses = repository.get_fixed_expenses(conn, restaurant_id, month)

    statement = services.profit_and_loss(daily, expenses, wages.labor_cost_for, start, end)
    if wages.source == "unavailable":
        statement = services.without_wages(statement)
    return {
        "month": month,
        "start": start,
        "end": end,
        "wages": wages.report(),
        "pl": statement,
        "menu": services.menu_summary(dishes_sold),
        "dogs": [d["name"] for d in dishes_sold if d["class"] == "dog"],
        "inventory": services.inventory_summary(stock),
        "to_reorder": [i["name"] for i in stock if i["status"] != "ok"],
    }


@router.get("/covers", response_model=CoversOut)
def covers(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Diners per day and hour, and the days the restaurant was open: what personnel needs for the schedule."""
    return {
        "covers": repository.get_covers_by_hour(conn, restaurant_id),
        "open_days": repository.get_open_days(conn, restaurant_id),
    }
