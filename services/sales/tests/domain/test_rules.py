"""The rules of the sales forms: limits of each field, the business rules in services, and the messages."""
import sqlite3

import pytest
from pydantic import ValidationError

from domains.sales import services
from domains.sales.schemas import CATEGORIES, DishIn, FixedExpenseIn, IngredientIn, PurchaseIn, SupplierIn
from web import form_errors

LINE = [{"ingredient_id": 1, "quantity": 1}]
INGREDIENT = {"name": "Mascarpone", "unit": "kg", "unit_cost": 9, "counted_stock": 0, "reorder_level": 0,
              "counted_at": "2026-09-01", "supplier_id": 4}


# ---------- Limits of each field: just inside is accepted, just outside is rejected ----------

@pytest.mark.parametrize("price, accepted", [(0, False), (0.01, True), (500, True), (500.01, False)])
def test_dish_price_limits(price, accepted):
    make = lambda: DishIn(name="Flan", category="dessert", price=price, recipe=LINE)
    if accepted:
        assert make().price == price
    else:
        with pytest.raises(ValidationError):
            make()


@pytest.mark.parametrize("name, accepted", [("F", False), ("Fl", True), ("x" * 60, True), ("x" * 61, False)])
def test_dish_name_limits(name, accepted):
    make = lambda: DishIn(name=name, category="dessert", price=5, recipe=LINE)
    if accepted:
        assert make().name == name
    else:
        with pytest.raises(ValidationError):
            make()


@pytest.mark.parametrize("unit_cost, accepted", [(0, False), (0.01, True), (1000, True), (1000.01, False)])
def test_ingredient_unit_cost_limits(unit_cost, accepted):
    make = lambda: IngredientIn(**{**INGREDIENT, "unit_cost": unit_cost})
    if accepted:
        assert make().unit_cost == unit_cost
    else:
        with pytest.raises(ValidationError):
            make()


@pytest.mark.parametrize("days, accepted", [(-1, False), (0, True), (60, True), (61, False)])
def test_supplier_lead_time_limits(days, accepted):
    make = lambda: SupplierIn(name="Makro", phone="600", lead_time_days=days)
    if accepted:
        assert make().lead_time_days == days
    else:
        with pytest.raises(ValidationError):
            make()


@pytest.mark.parametrize("unit_price, accepted", [(-0.01, False), (0, True)])     # free samples are allowed
def test_purchase_price_can_be_zero_but_not_negative(unit_price, accepted):
    make = lambda: PurchaseIn(ingredient_id=1, quantity=1, unit_price=unit_price, received_on="2026-09-01")
    if accepted:
        assert make().unit_price == unit_price
    else:
        with pytest.raises(ValidationError):
            make()


@pytest.mark.parametrize("month", ["2026-00", "2026-13", "26-09", "2026-9"])
def test_expense_month_must_be_a_real_month(month):
    with pytest.raises(ValidationError):
        FixedExpenseIn(description="Rent", amount=100, month=month)


# ---------- Categories are defined once ----------

def test_every_category_is_accepted_by_the_form_and_by_the_database(conn):
    for category in CATEGORIES:
        assert DishIn(name="Dish", category=category, price=5, recipe=LINE).category == category
        conn.execute("INSERT INTO menu_items (restaurant_id, code, name, category, price) VALUES (1, ?, 'Dish', ?, 5)",
                     (category, category))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO menu_items (restaurant_id, code, name, category, price) VALUES (1, 'X', 'X', "
                     "'snack', 5)")


# ---------- Business rules, without a database ----------

def test_names_clash_whatever_the_case():
    assert services.name_taken("makro", ["Makro", "Carnes Martín"])
    assert not services.name_taken("Makro Cash", ["Makro"])


def test_a_dish_can_only_use_the_restaurants_ingredients():
    dish = DishIn(name="Flan", category="dessert", price=5, recipe=[{"ingredient_id": 9, "quantity": 1}])
    assert services.dish_problem(dish, {1, 2}) == "Recipe: unknown ingredient"
    assert services.dish_problem(dish, {9}) is None


def test_ingredient_rules():
    ingredient = IngredientIn(**INGREDIENT)
    assert services.ingredient_problem(ingredient, [], {1}, []) == "Supplier: choose one of the suppliers in the list"
    assert services.ingredient_problem(ingredient, ["mascarpone"], {4}, []).startswith("Name:")
    assert services.ingredient_problem(ingredient, [], {4}, []) is None
    new = IngredientIn(**{**INGREDIENT, "supplier_id": None,
                          "new_supplier": {"name": "makro", "phone": "600", "lead_time_days": 1}})
    assert services.ingredient_problem(new, [], set(), ["Makro"]).startswith("New supplier name:")


def test_supplier_rules():
    supplier = SupplierIn(name="Makro", phone="600", lead_time_days=1, ingredient_ids=[3])
    assert services.supplier_problem(supplier, ["MAKRO"], {3}).startswith("Name:")
    assert services.supplier_problem(supplier, [], {1}) == "Ingredients: choose ingredients from the list"
    assert services.supplier_problem(supplier, [], {3}) is None


def test_a_supplier_only_delivers_what_it_sells():
    purchase = PurchaseIn(ingredient_id=5, quantity=1, unit_price=1, received_on="2026-09-01")
    assert services.purchase_problem(purchase, {1, 2}) == "This supplier does not sell that product"
    assert services.purchase_problem(purchase, {5}) is None


# ---------- One way to write form errors ----------

def test_form_errors_name_the_field_without_list_positions():
    with pytest.raises(ValidationError) as error:
        DishIn(name="Flan", category="dessert", price=5, recipe=[{"ingredient_id": 1, "quantity": 0}])
    assert form_errors(error.value) == ["Recipe quantity: input should be greater than 0"]
    assert form_errors(error.value, {"recipe quantity": "Ingredient quantity"}) == \
        ["Ingredient quantity: input should be greater than 0"]


def test_errors_of_the_whole_form_have_no_field():
    with pytest.raises(ValidationError) as error:
        SupplierIn(name="Makro", lead_time_days=1)
    assert form_errors(error.value) == ["Add a phone number or an email"]