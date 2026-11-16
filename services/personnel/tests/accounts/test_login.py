"""Logging in, renewing the token, registering a restaurant and adding managers, through the real API."""
import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from database import get_connection
from tests.conftest import log_in

PROTECTED = ["/auth/me", "/account/managers", "/personnel/payroll", "/personnel/summary",
             "/personnel/labor-cost?start=2026-09-01&end=2026-09-30"]

NEW_RESTAURANT = {"restaurant_name": "Bar Pepe", "name": "Pepe", "email": "pepe@barpepe.es",
                  "password": "tortilla99"}


def register(visitor, **changes):
    return visitor.post("/auth/register", json={**NEW_RESTAURANT, **changes})


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['token']}"}


# ---------- Logging in ----------

@pytest.mark.parametrize("path", PROTECTED)
def test_every_endpoint_with_data_needs_a_token(visitor, path):
    assert visitor.get(path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED)
def test_a_bad_token_is_refused(visitor, path):
    assert visitor.get(path, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_health_needs_no_login(visitor):
    assert visitor.get("/health").json() == {"status": "ok"}


def test_the_demo_manager_logs_in_and_gets_a_token_for_the_demo_restaurant(visitor):
    response = visitor.post("/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["restaurant"] == {"id": 1, "name": "Demo restaurant"}
    assert body["user"]["name"] == "Demo manager"
    assert body["expires_in"] == 15 * 60
    assert visitor.get("/auth/me", headers=bearer(response)).json()["email"] == DEMO_EMAIL


def test_a_wrong_password_or_unknown_email_gets_the_same_answer(visitor):
    wrong_password = visitor.post("/auth/login", json={"email": DEMO_EMAIL, "password": "nope"})
    unknown_email = visitor.post("/auth/login", json={"email": "nobody@manageeat.com", "password": "nope"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_the_email_is_not_case_sensitive(visitor):
    log_in(visitor, email="DEMO@ManageEat.com")


def test_a_token_is_renewed_while_the_account_exists(client):
    response = client.post("/auth/refresh")
    assert response.status_code == 200
    assert client.get("/auth/me", headers=bearer(response)).status_code == 200


def test_a_removed_manager_is_refused_at_once_and_cannot_renew(client):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE email = ?", (DEMO_EMAIL,))
    conn.commit()
    conn.close()
    assert client.get("/personnel/payroll").status_code == 401        # personnel checks the database every time
    assert client.post("/auth/refresh").status_code == 401             # so no new token for sales either


# ---------- Registering a restaurant ----------

def test_a_new_restaurant_starts_empty_and_never_sees_the_demo_data(visitor):
    response = register(visitor)
    assert response.status_code == 201
    payroll = visitor.get("/personnel/payroll", headers=bearer(response)).json()
    assert payroll["payroll"] == [] and payroll["total_pay"] == 0


def test_an_email_can_only_have_one_account(visitor):
    assert register(visitor, email=DEMO_EMAIL).status_code == 409


@pytest.mark.parametrize("field, value", [
    ("restaurant_name", "X"), ("name", "P"), ("email", "not-an-email"), ("password", "short"),
])
def test_register_checks_every_field(visitor, field, value):
    assert register(visitor, **{field: value}).status_code == 422


# ---------- Several managers per restaurant ----------

def test_a_manager_adds_another_manager_who_logs_in_with_their_own_password(client):
    response = client.post("/account/managers", json={"name": "Ana", "email": "ana@manageeat.com",
                                                      "password": "segunda-clave"})
    assert response.status_code == 201
    assert [m["name"] for m in client.get("/account/managers").json()] == ["Demo manager", "Ana"]

    ana = client.post("/auth/login", json={"email": "ana@manageeat.com", "password": "segunda-clave"})
    assert ana.json()["restaurant"]["id"] == 1                         # same restaurant, same data


def test_the_second_manager_cannot_use_the_first_managers_password(client):
    client.post("/account/managers", json={"name": "Ana", "email": "ana@manageeat.com", "password": "segunda-clave"})
    response = client.post("/auth/login", json={"email": "ana@manageeat.com", "password": DEMO_PASSWORD})
    assert response.status_code == 401


def test_adding_a_manager_checks_the_form_and_the_email(client):
    assert client.post("/account/managers", json={"name": "A", "email": "x", "password": "123"}).status_code == 422
    taken = client.post("/account/managers", json={"name": "Copy", "email": DEMO_EMAIL, "password": "12345678"})
    assert taken.status_code == 409


def test_a_manager_only_lists_the_managers_of_their_own_restaurant(visitor):
    response = register(visitor)
    managers = visitor.get("/account/managers", headers=bearer(response)).json()
    assert [m["email"] for m in managers] == ["pepe@barpepe.es"]