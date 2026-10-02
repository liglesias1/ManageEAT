def test_menu_page_shows_dishes_and_classes(client):
    response = client.get("/sales/menu")
    assert response.status_code == 200
    assert "Valencian paella" in response.text
    assert "Plowhorse" in response.text


def test_home_redirects_to_menu_page(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/sales/menu"


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