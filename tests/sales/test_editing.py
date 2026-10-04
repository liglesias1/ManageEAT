"""Editing dishes and their recipes, ingredients and suppliers."""
from domains.sales.repository import get_dish, get_ingredient, get_recipe, update_dish


def test_update_dish_replaces_the_whole_recipe(conn):
    conn.execute("INSERT INTO suppliers (id, name, email, lead_time_days) VALUES (1, 'S', 's@s.es', 2)")
    conn.execute("INSERT INTO ingredients VALUES (1, 'Rice', 'kg', 2.0, 1, 10, '2026-09-01', 1)")
    conn.execute("INSERT INTO ingredients VALUES (2, 'Chicken', 'kg', 6.0, 1, 10, '2026-09-01', 1)")
    conn.execute("INSERT INTO menu_items VALUES ('PAE01', 'Paella', 'main', 18)")
    conn.execute("INSERT INTO recipes VALUES ('PAE01', 1, 0.1)")
    update_dish(conn, "PAE01", "Paella mixta", "main", 19.5, [(2, 0.2)])
    assert get_dish(conn, "PAE01")["price"] == 19.5
    assert get_recipe(conn, "PAE01") == [(2, 0.2)]          # rice removed, chicken added
    assert get_dish(conn, "NOPE") is None
    assert get_ingredient(conn, 99) is None


# ---------- dishes ----------

def test_edit_dish_page_shows_its_current_recipe(client):
    page = client.get("/sales/dishes/PAE01/edit")
    assert page.status_code == 200
    assert "Edit Valencian paella" in page.text
    assert 'value="0.2"' in page.text                        # 0.2 kg of chicken


def test_editing_a_dish_changes_price_and_recipe(client):
    response = client.post(
        "/sales/dishes/PAE01/edit",
        data={"name": "Valencian paella", "category": "main", "price": "19.50",
              "ingredient_id": ["1", "2", ""], "quantity": ["0.12", "0.25", ""]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Dish “Valencian paella” updated." in page
    assert "€19.50" in page


def test_editing_a_dish_with_errors_or_unknown_code(client):
    no_recipe = client.post("/sales/dishes/PAE01/edit", data={"name": "Paella", "category": "main", "price": "18",
                                                             "ingredient_id": [""], "quantity": [""]})
    assert no_recipe.status_code == 422
    assert "add at least one ingredient" in no_recipe.text
    unknown_ingredient = client.post("/sales/dishes/PAE01/edit", data={"name": "Paella", "category": "main",
                                                                      "price": "18", "ingredient_id": ["999"],
                                                                      "quantity": ["1"]})
    assert unknown_ingredient.status_code == 422
    assert client.get("/sales/dishes/NOPE/edit").status_code == 404
    assert client.post("/sales/dishes/NOPE/edit", data={"name": "X1", "category": "main", "price": "5",
                                                        "ingredient_id": ["1"], "quantity": ["1"]}).status_code == 404


# ---------- ingredients ----------

CHICKEN = {"name": "Chicken", "unit": "kg", "unit_cost": "7.20", "counted_stock": "80", "counted_at": "2026-09-28",
           "reorder_level": "30", "supplier_id": "2"}


def test_editing_an_ingredient_changes_its_price_and_stock_count(client):
    assert "Edit Chicken" in client.get("/sales/ingredients/2/edit").text
    response = client.post("/sales/ingredients/2/edit", data=CHICKEN, follow_redirects=False)
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "“Chicken” updated." in page
    assert "€7.20 / kg" in page


def test_moving_an_ingredient_to_another_supplier(client):
    response = client.post("/sales/ingredients/2/edit", data={**CHICKEN, "supplier_id": "1"}, follow_redirects=False)
    assert response.headers["location"].startswith("/sales/suppliers/1")
    edit_link = 'href="/sales/ingredients/2/edit"'          # appears in the supplier's product list
    assert edit_link in client.get("/sales/suppliers/1").text
    assert edit_link not in client.get("/sales/suppliers/2").text   # past deliveries stay in its history


def test_editing_an_ingredient_with_errors(client):
    bad_price = client.post("/sales/ingredients/2/edit", data={**CHICKEN, "unit_cost": "0"})
    assert bad_price.status_code == 422
    assert "Unit cost" in bad_price.text
    repeated = client.post("/sales/ingredients/2/edit", data={**CHICKEN, "name": "rice"})
    assert repeated.status_code == 422
    assert "already an ingredient with that name" in repeated.text
    unknown_supplier = client.post("/sales/ingredients/2/edit", data={**CHICKEN, "supplier_id": "99"})
    assert unknown_supplier.status_code == 422
    assert client.get("/sales/ingredients/999/edit").status_code == 404
    assert client.post("/sales/ingredients/999/edit", data=CHICKEN).status_code == 404


# ---------- suppliers ----------

def test_editing_a_supplier_changes_its_contact(client):
    assert "Edit Carnes Martín" in client.get("/sales/suppliers/2/edit").text
    response = client.post("/sales/suppliers/2/edit", data={"name": "Carnes Martín", "phone": "+34 911 000 000",
                                                            "email": "", "lead_time_days": "1"},
                           follow_redirects=False)
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "+34 911 000 000" in page
    assert "Delivers in 1 days" in page


def test_supplier_cannot_be_left_without_contact(client):
    response = client.post("/sales/suppliers/2/edit", data={"name": "Carnes Martín", "phone": "", "email": "",
                                                            "lead_time_days": "2"})
    assert response.status_code == 422
    assert "Add a phone number or an email" in response.text
    assert client.get("/sales/suppliers/999/edit").status_code == 404
    assert client.post("/sales/suppliers/999/edit", data={"name": "X1", "phone": "1", "email": "",
                                                          "lead_time_days": "2"}).status_code == 404