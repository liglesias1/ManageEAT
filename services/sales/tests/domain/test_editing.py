"""Editing dishes and their recipes, ingredients and suppliers."""
from domain.repository import get_dish, get_ingredient, get_recipe, update_dish


def test_update_dish_replaces_the_whole_recipe(conn):
    conn.execute("INSERT INTO suppliers (id, restaurant_id, name, email, lead_time_days) VALUES (1, 1, 'S', 's@s.es', 2)")
    conn.execute("INSERT INTO ingredients VALUES (1, 1, 'Rice', 'kg', 2.0, 1, 10, '2026-09-01', 1)")
    conn.execute("INSERT INTO ingredients VALUES (2, 1, 'Chicken', 'kg', 6.0, 1, 10, '2026-09-01', 1)")
    conn.execute("INSERT INTO menu_items VALUES (1, 'PAE01', 'Paella', 'main', 18)")
    conn.execute("INSERT INTO recipes VALUES (1, 'PAE01', 1, 0.1)")
    update_dish(conn, 1, "PAE01", "Paella mixta", "main", 19.5, [(2, 0.2)])
    assert get_dish(conn, 1, "PAE01")["price"] == 19.5
    assert get_recipe(conn, 1, "PAE01") == [(2, 0.2)]          # rice removed, chicken added
    assert get_dish(conn, 1, "NOPE") is None
    assert get_ingredient(conn, 1, 99) is None


# ---------- dishes ----------

PAELLA = {"name": "Valencian paella", "category": "main", "price": 19.5,
          "recipe": [{"ingredient_id": 1, "quantity": 0.12}, {"ingredient_id": 2, "quantity": 0.25}]}


def test_a_dish_comes_with_its_current_recipe(client):
    dish = client.get("/sales/dishes/PAE01").json()
    assert dish["name"] == "Valencian paella"
    assert {"ingredient_id": 2, "quantity": 0.2} in dish["recipe"]            # 0.2 kg of chicken


def test_editing_a_dish_changes_price_and_recipe(client):
    response = client.put("/sales/dishes/PAE01", json=PAELLA)
    assert response.status_code == 200
    dish = client.get("/sales/dishes/PAE01").json()
    assert dish["price"] == 19.5
    assert dish["recipe"] == [{"ingredient_id": 1, "quantity": 0.12}, {"ingredient_id": 2, "quantity": 0.25}]


def test_editing_a_dish_with_errors_or_unknown_code(client):
    assert client.put("/sales/dishes/PAE01", json={**PAELLA, "recipe": []}).status_code == 422
    unknown_ingredient = client.put("/sales/dishes/PAE01",
                                    json={**PAELLA, "recipe": [{"ingredient_id": 999, "quantity": 1}]})
    assert unknown_ingredient.status_code == 422
    assert unknown_ingredient.json()["detail"] == "Recipe: unknown ingredient"
    assert client.get("/sales/dishes/NOPE").status_code == 404
    assert client.put("/sales/dishes/NOPE", json=PAELLA).status_code == 404


# ---------- ingredients ----------

CHICKEN = {"name": "Chicken", "unit": "kg", "unit_cost": 7.20, "counted_stock": 80, "counted_at": "2026-09-28",
           "reorder_level": 30, "supplier_id": 2}


def test_editing_an_ingredient_changes_its_price_and_stock_count(client):
    response = client.put("/sales/ingredients/2", json=CHICKEN)
    assert response.status_code == 200
    ingredient = client.get("/sales/ingredients/2").json()
    assert ingredient["unit_cost"] == 7.2 and ingredient["counted_stock"] == 80


def test_moving_an_ingredient_to_another_supplier(client):
    assert client.put("/sales/ingredients/2", json={**CHICKEN, "supplier_id": 1}).json()["supplier_id"] == 1
    assert 2 in [i["id"] for i in client.get("/sales/suppliers/1").json()["items"]]
    assert 2 not in [i["id"] for i in client.get("/sales/suppliers/2").json()["items"]]
    assert client.get("/sales/suppliers/2").json()["purchases"]              # past deliveries stay in its history


def test_editing_an_ingredient_with_errors(client):
    assert client.put("/sales/ingredients/2", json={**CHICKEN, "unit_cost": 0}).status_code == 422
    repeated = client.put("/sales/ingredients/2", json={**CHICKEN, "name": "rice"})
    assert repeated.status_code == 422
    assert "already an ingredient with that name" in repeated.json()["detail"]
    assert client.put("/sales/ingredients/2", json={**CHICKEN, "supplier_id": 99}).status_code == 422
    new_supplier = {**CHICKEN, "supplier_id": None,
                    "new_supplier": {"name": "Nuevo", "phone": "600", "lead_time_days": 1}}
    assert client.put("/sales/ingredients/2", json=new_supplier).status_code == 422   # editing cannot create one
    assert client.get("/sales/ingredients/999").status_code == 404
    assert client.put("/sales/ingredients/999", json=CHICKEN).status_code == 404


def test_keeping_its_own_name_is_allowed(client):
    assert client.put("/sales/ingredients/2", json=CHICKEN).status_code == 200


# ---------- suppliers ----------

CARNES = {"name": "Carnes Martín", "phone": "+34 911 000 000", "email": "", "lead_time_days": 1}


def test_editing_a_supplier_changes_its_contact(client):
    assert client.put("/sales/suppliers/2", json=CARNES).status_code == 200
    supplier = client.get("/sales/suppliers/2").json()["supplier"]
    assert supplier["phone"] == "+34 911 000 000" and supplier["lead_time_days"] == 1


def test_supplier_cannot_be_left_without_contact(client):
    assert client.put("/sales/suppliers/2", json={**CARNES, "phone": ""}).status_code == 422
    assert client.put("/sales/suppliers/999", json=CARNES).status_code == 404


def test_renaming_a_supplier_to_another_suppliers_name_is_rejected(client):
    taken = client.put("/sales/suppliers/2", json={**CARNES, "name": "Huerta de Madrid"})
    assert taken.status_code == 422
    assert "already a supplier with that name" in taken.json()["detail"]