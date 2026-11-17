"""The sales endpoints: what each one answers, what it saves, and how it rejects bad input."""
import pytest

from tests.conftest import bearer, make_token

PROTECTED = ["/sales/menu", "/sales/dishes", "/sales/inventory", "/sales/suppliers/2", "/sales/profit-loss",
             "/sales/summary", "/sales/covers"]


# ---------- Who can ask ----------

def test_health_needs_no_login(visitor):
    assert visitor.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("path", PROTECTED)
def test_every_endpoint_with_data_needs_a_token(visitor, path):
    assert visitor.get(path).status_code == 401


@pytest.mark.parametrize("token", [
    "not-a-token",
    make_token(minutes=-1),                                     # expired
    make_token(secret="someone-elses-secret-0123456789abcdef"),  # not signed by personnel
])
def test_a_bad_token_is_refused(visitor, token):
    assert visitor.get("/sales/menu", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_token_without_a_restaurant_is_refused(visitor):
    import jwt
    from tests.conftest import TEST_SECRET

    token = jwt.encode({"sub": "1", "exp": 4102444800}, TEST_SECRET, algorithm="HS256")
    assert visitor.get("/sales/menu", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_each_restaurant_only_sees_its_own_data(visitor):
    other = visitor.get("/sales/inventory", headers=bearer(restaurant_id=2)).json()
    assert other["stock"] == [] and other["suppliers"] == []


# ---------- Menu and dishes ----------

def test_menu_classifies_every_dish(client):
    body = client.get("/sales/menu").json()
    names = [d["name"] for dishes in body["by_category"].values() for d in dishes]
    assert "Valencian paella" in names and len(names) == 13
    assert {d["class"] for dishes in body["by_category"].values() for d in dishes} <= \
        {"star", "plowhorse", "puzzle", "dog"}


def test_dishes_come_with_price_cost_and_the_ingredients_a_recipe_can_use(client):
    body = client.get("/sales/dishes").json()
    paella = next(d for d in body["by_category"]["main"] if d["code"] == "PAE01")
    assert paella["price"] == 18.0 and paella["cost"] > 0
    assert body["categories"] == ["main", "starter", "dessert", "drink"]
    assert "Chicken" in [i["name"] for i in body["ingredients"]]


TIRAMISU = {"name": "Tiramisu", "category": "dessert", "price": 6.5,
            "recipe": [{"ingredient_id": 13, "quantity": 0.1}, {"ingredient_id": 11, "quantity": 0.05}]}


def test_adding_a_dish_puts_it_on_the_menu_as_new(client):
    response = client.post("/sales/dishes", json=TIRAMISU)
    assert response.status_code == 201
    assert response.json() == {"code": "TIR01", "name": "Tiramisu"}
    assert "Tiramisu" in [d["name"] for d in client.get("/sales/menu").json()["new_dishes"]]


@pytest.mark.parametrize("change", [
    {"recipe": []},                                                  # no ingredients
    {"recipe": [{"ingredient_id": 6, "quantity": -1}]},              # wrong quantity
    {"price": 0},
    {"category": "snack"},
])
def test_a_dish_with_wrong_fields_is_rejected(client, change):
    assert client.post("/sales/dishes", json={**TIRAMISU, **change}).status_code == 422


def test_a_dish_with_an_unknown_ingredient_is_rejected(client):
    response = client.post("/sales/dishes", json={**TIRAMISU, "recipe": [{"ingredient_id": 999, "quantity": 1}]})
    assert response.status_code == 422
    assert response.json()["detail"] == "Recipe: unknown ingredient"


# ---------- Inventory, ingredients and suppliers ----------

def test_inventory_shows_stock_and_suppliers(client):
    body = client.get("/sales/inventory").json()
    assert body["as_of"] == "2026-09-28"                             # the last day with demo orders
    assert "Chicken" in [i["name"] for i in body["stock"]]
    assert "Carnes Martín" in [s["name"] for s in body["suppliers"]]


NEW_INGREDIENT = {"name": "Mascarpone", "unit": "kg", "unit_cost": 7.5, "counted_stock": 6,
                  "reorder_level": 2, "counted_at": "2026-09-28", "supplier_id": 4}


def test_adding_an_ingredient_from_an_existing_supplier(client):
    response = client.post("/sales/ingredients", json=NEW_INGREDIENT)
    assert response.status_code == 201
    assert response.json() == {"name": "Mascarpone", "supplier_id": 4}            # Lácteos Sierra
    assert "Mascarpone" in [i["name"] for i in client.get("/sales/suppliers/4").json()["items"]]


def test_adding_an_ingredient_with_a_new_supplier_creates_both(client):
    data = {**NEW_INGREDIENT, "supplier_id": None,
            "new_supplier": {"name": "Quesos Italia", "email": "ordini@quesos.it", "lead_time_days": 3}}
    supplier_id = client.post("/sales/ingredients", json=data).json()["supplier_id"]
    supplier = client.get(f"/sales/suppliers/{supplier_id}").json()
    assert supplier["supplier"]["name"] == "Quesos Italia"
    assert [i["name"] for i in supplier["items"]] == ["Mascarpone"]


def test_new_supplier_without_contact_saves_nothing(client):
    data = {**NEW_INGREDIENT, "supplier_id": None, "new_supplier": {"name": "Quesos Italia", "lead_time_days": 3}}
    assert client.post("/sales/ingredients", json=data).status_code == 422
    assert "Mascarpone" not in [i["name"] for i in client.get("/sales/dishes").json()["ingredients"]]


@pytest.mark.parametrize("change, message", [
    ({"name": "chicken"}, "already an ingredient with that name"),
    ({"supplier_id": 99}, "choose one of the suppliers"),
    ({"supplier_id": None, "new_supplier": {"name": "Lácteos Sierra", "phone": "600", "lead_time_days": 2}},
     "that supplier already exists"),
])
def test_ingredient_business_rules(client, change, message):
    response = client.post("/sales/ingredients", json={**NEW_INGREDIENT, **change})
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_ingredient_with_invalid_price_or_no_supplier_is_rejected(client):
    assert client.post("/sales/ingredients", json={**NEW_INGREDIENT, "unit_cost": -3}).status_code == 422
    assert client.post("/sales/ingredients", json={**NEW_INGREDIENT, "supplier_id": None}).status_code == 422


def test_adding_a_supplier_that_takes_over_an_ingredient(client):
    response = client.post("/sales/suppliers", json={"name": "Pescados Vigo", "email": "orders@vigo.es",
                                                     "lead_time_days": 2, "ingredient_ids": [2]})
    assert response.status_code == 201
    supplier_id = response.json()["id"]
    assert [i["name"] for i in client.get(f"/sales/suppliers/{supplier_id}").json()["items"]] == ["Chicken"]


@pytest.mark.parametrize("supplier, message", [
    ({"name": "carnes martín", "phone": "600", "lead_time_days": 2}, "already a supplier with that name"),
    ({"name": "Bodegas Rioja", "phone": "600", "lead_time_days": 2, "ingredient_ids": [9999]},
     "choose ingredients from the list"),
])
def test_supplier_business_rules(client, supplier, message):
    response = client.post("/sales/suppliers", json=supplier)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_supplier_without_contact_is_rejected(client):
    assert client.post("/sales/suppliers", json={"name": "No Contact", "lead_time_days": 2}).status_code == 422


def test_supplier_page_shows_products_and_deliveries(client):
    body = client.get("/sales/suppliers/2").json()                      # Carnes Martín
    assert body["supplier"]["name"] == "Carnes Martín"
    assert "Ribeye" in [i["name"] for i in body["items"]]
    assert "2026-09-15" in [p["received_on"] for p in body["purchases"]]
    assert client.get("/sales/suppliers/999").status_code == 404


DELIVERY = {"ingredient_id": 2, "quantity": 40, "unit_price": 6.5, "received_on": "2026-09-27"}


def test_recording_a_delivery_adds_it_to_the_history(client):
    assert client.post("/sales/suppliers/2/purchases", json=DELIVERY).status_code == 201
    assert client.get("/sales/suppliers/2").json()["purchases"][0]["received_on"] == "2026-09-27"


def test_wrong_deliveries_are_rejected(client):
    assert client.post("/sales/suppliers/2/purchases", json={**DELIVERY, "quantity": -5}).status_code == 422
    rice = client.post("/sales/suppliers/2/purchases", json={**DELIVERY, "ingredient_id": 1})   # not sold here
    assert rice.status_code == 422
    assert rice.json()["detail"] == "This supplier does not sell that product"
    assert client.post("/sales/suppliers/999/purchases", json=DELIVERY).status_code == 404


# ---------- Fixed expenses ----------

def test_adding_a_fixed_expense_includes_it_in_its_month(client):
    response = client.post("/sales/expenses", json={"description": "Summer rent", "amount": 3200, "month": "2026-08"})
    assert response.status_code == 201
    august = client.get("/sales/profit-loss", params={"month": "2026-08"}).json()
    assert "Summer rent" in [e["description"] for e in august["expenses"]]


@pytest.mark.parametrize("expense", [
    {"description": "Marketing", "amount": -10, "month": "2026-09"},
    {"description": "Marketing", "amount": 10, "month": "September"},
])
def test_wrong_fixed_expenses_are_rejected(client, expense):
    assert client.post("/sales/expenses", json=expense).status_code == 422


# ---------- What personnel asks for ----------

def test_covers_per_hour_and_open_days(client):
    body = client.get("/sales/covers").json()
    assert len(body["open_days"]) == 28
    assert body["open_days"][0] == "2026-09-01"
    assert set(body["covers"][0]) == {"day", "hour", "covers"}
    assert {row["hour"] for row in body["covers"]} <= {13, 14, 15, 20, 21, 22, 23}