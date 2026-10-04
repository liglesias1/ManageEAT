def test_menu_page_shows_dishes_and_classes(client):
    response = client.get("/sales/menu")
    assert response.status_code == 200
    assert "Valencian paella" in response.text
    assert "Plowhorse" in response.text


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_inventory_page_shows_stock_and_suppliers(client):
    response = client.get("/sales/inventory")
    assert response.status_code == 200
    assert "Chicken" in response.text
    assert "Carnes Martín" in response.text


def test_adding_a_supplier_redirects_and_lists_it(client):
    response = client.post(
        "/sales/inventory/suppliers",
        data={"name": "Pescados Vigo", "phone": "", "email": "orders@vigo.es", "lead_time_days": "2",
              "ingredient_ids": ["2"]},   # takes over Chicken
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Pescados Vigo" in page
    assert "Supplier “Pescados Vigo” added." in page


def test_supplier_without_contact_shows_an_error_and_is_not_saved(client):
    response = client.post(
        "/sales/inventory/suppliers",
        data={"name": "No Contact", "phone": "", "email": "", "lead_time_days": "2"},
    )
    assert response.status_code == 422
    assert "Add a phone number or an email" in response.text
    assert "No Contact</td>" not in response.text


def test_supplier_page_shows_products_and_prices(client):
    response = client.get("/sales/suppliers/2")          # Carnes Martín
    assert response.status_code == 200
    assert "Carnes Martín" in response.text
    assert "Ribeye" in response.text
    assert "Order history" in response.text
    assert "2026-09-15" in response.text            # demo deliveries


def test_unknown_supplier_page_is_404(client):
    assert client.get("/sales/suppliers/999").status_code == 404


def test_recording_a_delivery_adds_it_to_the_history(client):
    response = client.post(
        "/sales/suppliers/2/purchases",
        data={"ingredient_id": "2", "quantity": "40", "unit_price": "6.50", "received_on": "2026-09-27"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Delivery recorded." in page
    assert "2026-09-27" in page


def test_delivery_with_invalid_quantity_is_rejected(client):
    response = client.post(
        "/sales/suppliers/2/purchases",
        data={"ingredient_id": "2", "quantity": "-5", "unit_price": "6.50", "received_on": "2026-09-27"},
    )
    assert response.status_code == 422
    assert "Quantity" in response.text


def test_delivery_of_a_product_the_supplier_does_not_sell_is_rejected(client):
    response = client.post(
        "/sales/suppliers/2/purchases",                    # Carnes Martín does not sell rice (id 1)
        data={"ingredient_id": "1", "quantity": "10", "unit_price": "2", "received_on": "2026-09-27"},
    )
    assert response.status_code == 422
    assert "does not sell that product" in response.text



def test_profit_loss_page_shows_statement_with_wages_from_payroll(client):
    response = client.get("/sales/profit-loss")
    assert response.status_code == 200
    assert "Net profit" in response.text
    assert "from payroll" in response.text
    assert "Electricity and water" in response.text


def test_adding_a_fixed_expense_includes_it_in_the_month(client):
    response = client.post(
        "/sales/profit-loss/expenses",
        data={"description": "Marketing", "amount": "750", "month": "2026-09"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Expense “Marketing” added." in page
    assert "Marketing</td>" in page


def test_fixed_expense_with_wrong_amount_is_rejected(client):
    response = client.post(
        "/sales/profit-loss/expenses",
        data={"description": "Marketing", "amount": "-10", "month": "2026-09"},
    )
    assert response.status_code == 422
    assert "Amount" in response.text



def test_dishes_page_shows_price_cost_and_recipe(client):
    response = client.get("/sales/dishes")
    assert response.status_code == 200
    assert "Valencian paella" in response.text
    assert "€18.00" in response.text
    assert "Markup" in response.text


def test_adding_a_dish_puts_it_on_the_menu_as_new(client):
    response = client.post(
        "/sales/dishes",
        data={"name": "Tiramisu", "category": "dessert", "price": "6.50",
              "ingredient_id": ["13", "11", ""], "quantity": ["0.1", "0.05", ""]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Dish “Tiramisu” added to the menu." in page
    assert "TIR01" in page
    menu = client.get("/sales/menu").text
    assert "New on the menu" in menu
    assert "Tiramisu" in menu


def test_dish_without_recipe_is_rejected(client):
    response = client.post("/sales/dishes", data={"name": "Air", "category": "main", "price": "5",
                                                  "ingredient_id": [""], "quantity": [""]})
    assert response.status_code == 422
    assert "add at least one ingredient" in response.text


def test_dish_with_wrong_quantity_or_unknown_ingredient_is_rejected(client):
    bad_quantity = client.post("/sales/dishes", data={"name": "Soup", "category": "starter", "price": "5",
                                                      "ingredient_id": ["6"], "quantity": ["-1"]})
    assert bad_quantity.status_code == 422
    assert "Ingredient quantity" in bad_quantity.text
    unknown = client.post("/sales/dishes", data={"name": "Soup", "category": "starter", "price": "5",
                                                 "ingredient_id": ["999"], "quantity": ["1"]})
    assert unknown.status_code == 422
    assert "unknown ingredient" in unknown.text



NEW_INGREDIENT = {"name": "Mascarpone", "unit": "kg", "unit_cost": "7.50", "counted_stock": "6",
                  "reorder_level": "2", "counted_at": "2026-09-28", "supplier_choice": "existing", "supplier_id": "4"}


def test_adding_an_ingredient_from_an_existing_supplier(client):
    response = client.post("/sales/inventory/ingredients", data=NEW_INGREDIENT, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/sales/suppliers/4")     # Lácteos Sierra
    supplier_page = client.get(response.headers["location"]).text
    assert "Ingredient “Mascarpone” added and linked to Lácteos Sierra." in supplier_page
    assert "Mascarpone (€7.50/kg)" in client.get("/sales/dishes").text      # it can go in a recipe now


def test_adding_an_ingredient_with_a_new_supplier_creates_both(client):
    data = {**NEW_INGREDIENT, "supplier_choice": "new", "supplier_id": "", "new_supplier_name": "Quesos Italia",
            "new_supplier_email": "ordini@quesos.it", "new_supplier_lead_time": "3"}
    response = client.post("/sales/inventory/ingredients", data=data, follow_redirects=False)
    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Quesos Italia" in page
    assert "Mascarpone" in page
    assert "Quesos Italia" in client.get("/sales/inventory").text


def test_new_supplier_without_contact_saves_nothing(client):
    data = {**NEW_INGREDIENT, "supplier_choice": "new", "new_supplier_name": "Quesos Italia",
            "new_supplier_lead_time": "3"}
    response = client.post("/sales/inventory/ingredients", data=data)
    assert response.status_code == 422
    assert "New supplier: add a phone number or an email" in response.text
    assert "Mascarpone (€" not in client.get("/sales/dishes").text


def test_ingredient_with_a_name_in_use_or_unknown_supplier_is_rejected(client):
    repeated = client.post("/sales/inventory/ingredients", data={**NEW_INGREDIENT, "name": "chicken"})
    assert repeated.status_code == 422
    assert "already an ingredient with that name" in repeated.text
    unknown = client.post("/sales/inventory/ingredients", data={**NEW_INGREDIENT, "supplier_id": "99"})
    assert unknown.status_code == 422
    assert "choose one of the suppliers" in unknown.text


def test_ingredient_with_invalid_price_or_no_supplier_is_rejected(client):
    bad_price = client.post("/sales/inventory/ingredients", data={**NEW_INGREDIENT, "unit_cost": "-3"})
    assert bad_price.status_code == 422
    assert "Unit cost" in bad_price.text
    no_supplier = client.post("/sales/inventory/ingredients", data={**NEW_INGREDIENT, "supplier_id": ""})
    assert no_supplier.status_code == 422
    assert "choose an existing supplier or add a new one" in no_supplier.text