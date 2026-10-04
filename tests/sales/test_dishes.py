"""Dish costing, new dish codes and validation of the new dish form."""
import pytest
from pydantic import ValidationError

from domains.sales.repository import add_dish, get_menu, get_recipe_lines
from domains.sales.schemas import DishIn
from domains.sales.services import FOOD_COST_TARGET, cost_dishes, dishes_summary, new_dish_code


def line(item_code, ingredient, quantity, unit_cost):
    return {"item_code": item_code, "ingredient": ingredient, "unit": "kg", "quantity": quantity, "unit_cost": unit_cost}


PAELLA = {"code": "PAE01", "name": "Paella", "category": "main", "price": 18.0}
RECIPE = [line("PAE01", "Rice", 0.1, 2.0), line("PAE01", "Chicken", 0.2, 7.0), line("OTHER", "Rice", 1, 2.0)]


def test_cost_is_the_sum_of_each_ingredient_times_its_quantity():
    dish = cost_dishes([PAELLA], RECIPE)[0]
    assert dish["cost"] == pytest.approx(0.1 * 2.0 + 0.2 * 7.0)       # 1.60
    assert [l["ingredient"] for l in dish["recipe"]] == ["Chicken", "Rice"]   # most expensive first


def test_margin_markup_and_food_cost():
    dish = cost_dishes([PAELLA], RECIPE)[0]
    assert dish["margin"] == pytest.approx(16.40)
    assert dish["markup_pct"] == pytest.approx(16.40 / 1.60 * 100)     # +1025%
    assert dish["food_cost_pct"] == pytest.approx(1.60 / 18 * 100)     # 8.9%
    assert dish["above_target"] is False


def test_dish_above_the_food_cost_target_is_flagged():
    cheap = {**PAELLA, "price": 4.0}                                    # 1.60 / 4 = 40%
    assert FOOD_COST_TARGET < 40
    assert cost_dishes([cheap], RECIPE)[0]["above_target"] is True


def test_dish_without_recipe_has_no_markup():
    dish = cost_dishes([{**PAELLA, "code": "X"}], RECIPE)[0]
    assert dish["cost"] == 0
    assert dish["markup_pct"] is None


def test_summary_of_the_menu():
    costed = cost_dishes([PAELLA, {**PAELLA, "code": "PAE02", "name": "Cheap", "price": 4.0}],
                         RECIPE + [line("PAE02", "Rice", 0.8, 2.0)])
    summary = dishes_summary(costed)
    assert summary["dishes"] == 2
    assert summary["above_target"] == 1
    assert summary["highest"]["name"] == "Cheap"
    assert dishes_summary([])["highest"] is None


def test_new_dish_code_uses_the_name_and_skips_codes_in_use():
    assert new_dish_code("Tiramisu", set()) == "TIR01"
    assert new_dish_code("Tiramisu", {"TIR01", "TIR02"}) == "TIR03"
    assert new_dish_code("Pà", set()) == "PXX01"         # letters only, padded to three


def test_dish_form_needs_a_recipe_without_repeated_ingredients():
    with pytest.raises(ValidationError):
        DishIn(name="Tiramisu", category="dessert", price=6, recipe=[])
    with pytest.raises(ValidationError):
        DishIn(name="Tiramisu", category="dessert", price=6,
               recipe=[{"ingredient_id": 1, "quantity": 1}, {"ingredient_id": 1, "quantity": 2}])
    with pytest.raises(ValidationError):
        DishIn(name="Tiramisu", category="snack", price=6, recipe=[{"ingredient_id": 1, "quantity": 1}])
    dish = DishIn(name="  Tiramisu ", category="dessert", price="6.5", recipe=[{"ingredient_id": 1, "quantity": "0.1"}])
    assert dish.name == "Tiramisu"


def test_add_dish_saves_dish_and_recipe_together(conn):
    conn.execute("INSERT INTO suppliers (id, name, email, lead_time_days) VALUES (1, 'S', 's@s.es', 2)")
    conn.execute("INSERT INTO ingredients VALUES (1, 'Rice', 'kg', 2.0, 1, 10, '2026-09-01', 1)")
    add_dish(conn, "RIC01", "Rice bowl", "main", 9.5, [(1, 0.2)])
    assert get_menu(conn) == [{"code": "RIC01", "name": "Rice bowl", "category": "main", "price": 9.5}]
    assert get_recipe_lines(conn)[0]["quantity"] == 0.2


def test_add_dish_saves_nothing_if_the_recipe_fails(conn):
    # Ingredient 99 does not exist: the foreign key fails, so the dish must not be saved either
    with pytest.raises(Exception):
        add_dish(conn, "BAD01", "Bad", "main", 9.5, [(99, 1)])
    assert get_menu(conn) == []