"""Logging in and out, registering a restaurant and adding managers, through the real pages."""
import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD

PAGES = ["/", "/sales/menu", "/sales/dishes", "/sales/inventory", "/sales/profit-loss",
         "/personnel/schedule", "/personnel/payroll", "/account/managers"]


def log_in(visitor, email=DEMO_EMAIL, password=DEMO_PASSWORD, next_page="/"):
    return visitor.post("/login", data={"email": email, "password": password, "next": next_page},
                        follow_redirects=False)


def register(visitor, restaurant="Bar Pepe", name="Pepe", email="pepe@barpepe.es", password="tortilla99"):
    return visitor.post("/register", data={"restaurant_name": restaurant, "name": name, "email": email,
                                           "password": password}, follow_redirects=False)


# ---------- Logging in ----------

@pytest.mark.parametrize("page", PAGES)
def test_every_page_sends_visitors_to_the_login_and_back(visitor, page):
    response = visitor.get(page, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_public_pages_need_no_login(visitor):
    assert visitor.get("/login").status_code == 200
    assert visitor.get("/register").status_code == 200
    assert visitor.get("/health").json() == {"status": "ok"}


def test_the_demo_manager_logs_in_and_sees_the_demo_restaurant(visitor):
    response = log_in(visitor)
    assert response.status_code == 303 and response.headers["location"] == "/"
    home = visitor.get("/").text
    assert "€82,495.55" in home
    assert "Demo restaurant" in home and "Demo manager" in home          # who is logged in, in the sidebar


def test_after_logging_in_the_manager_returns_to_the_page_they_asked_for(visitor):
    assert log_in(visitor, next_page="/sales/menu").headers["location"] == "/sales/menu"


def test_the_return_page_must_be_on_this_site(visitor):
    assert log_in(visitor, next_page="https://evil.example").headers["location"] == "/"
    visitor.post("/logout")
    assert log_in(visitor, next_page="//evil.example").headers["location"] == "/"


def test_a_wrong_password_or_unknown_email_gets_the_same_message(visitor):
    wrong_password = log_in(visitor, password="nope")
    unknown_email = log_in(visitor, email="nobody@manageeat.com")
    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert "The email or the password is not correct" in response.text
    assert visitor.get("/", follow_redirects=False).status_code == 303       # still not logged in


def test_an_empty_form_gets_the_same_message(visitor):
    response = log_in(visitor, email="", password="")
    assert response.status_code == 401
    assert "The email or the password is not correct" in response.text


def test_the_email_is_not_case_sensitive(visitor):
    assert log_in(visitor, email=DEMO_EMAIL.upper()).status_code == 303


def test_logging_out_ends_the_session(visitor):
    log_in(visitor)
    assert visitor.post("/logout", follow_redirects=False).headers["location"] == "/login"
    assert visitor.get("/", follow_redirects=False).status_code == 303


def test_a_logged_in_manager_going_to_the_login_page_goes_home(visitor):
    log_in(visitor)
    assert visitor.get("/login", follow_redirects=False).headers["location"] == "/"


# ---------- Registering a restaurant ----------

def test_a_new_restaurant_starts_empty_and_never_sees_the_demo_data(visitor):
    assert register(visitor).headers["location"] == "/"
    for page in PAGES:                                         # every page works with no data at all
        response = visitor.get(page)
        assert response.status_code == 200, page
        assert "Valencian paella" not in response.text
        assert "Lucía Martín" not in response.text
        assert "Carnes Martín" not in response.text
    assert "€82,495.55" not in visitor.get("/").text
    assert visitor.get("/sales/suppliers/2").status_code == 404          # the demo's supplier is not theirs
    assert visitor.get("/sales/dishes/PAE01/edit").status_code == 404


def test_what_a_new_restaurant_adds_stays_in_that_restaurant(visitor):
    register(visitor)
    visitor.post("/sales/profit-loss/expenses", data={"description": "Pepe's rent", "amount": "900",
                                                      "month": "2026-09"})
    visitor.post("/logout")
    log_in(visitor)                                           # back as the demo manager
    assert "Pepe's rent" not in visitor.get("/sales/profit-loss?month=2026-09").text


def test_an_email_can_only_have_one_account(visitor):
    response = register(visitor, email=DEMO_EMAIL.upper())
    assert response.status_code == 422
    assert "already an account with that email" in response.text


def test_register_checks_every_field(visitor):
    response = register(visitor, restaurant="", email="not-an-email", password="short")
    assert response.status_code == 422
    assert "Restaurant name" in response.text
    assert "enter a valid email address" in response.text
    assert "at least 8 characters" in response.text


# ---------- Several managers per restaurant ----------

def test_a_manager_adds_another_manager_who_logs_in_with_their_own_password(visitor):
    log_in(visitor)
    response = visitor.post("/account/managers", data={"name": "Ana", "email": "ana@manageeat.com",
                                                       "password": "segunda-clave"}, follow_redirects=False)
    assert response.status_code == 303
    page = visitor.get(response.headers["location"]).text
    assert "Manager “ana@manageeat.com” added." in page
    assert "Demo manager" in page and "Ana" in page

    visitor.post("/logout")
    assert log_in(visitor, email="ana@manageeat.com", password="segunda-clave").status_code == 303
    assert "€82,495.55" in visitor.get("/").text               # same restaurant, same data


def test_the_second_manager_cannot_use_the_first_managers_password(visitor):
    log_in(visitor)
    visitor.post("/account/managers", data={"name": "Ana", "email": "ana@manageeat.com",
                                            "password": "segunda-clave"})
    visitor.post("/logout")
    assert log_in(visitor, email="ana@manageeat.com", password=DEMO_PASSWORD).status_code == 401


def test_adding_a_manager_checks_the_form_and_the_email(visitor):
    log_in(visitor)
    bad = visitor.post("/account/managers", data={"name": "A", "email": "x", "password": "123"})
    assert bad.status_code == 422
    taken = visitor.post("/account/managers", data={"name": "Copy", "email": DEMO_EMAIL, "password": "12345678"})
    assert taken.status_code == 422
    assert "already an account with that email" in taken.text


def test_a_session_whose_account_no_longer_exists_is_sent_to_the_login(visitor):
    from database import get_connection

    log_in(visitor)
    conn = get_connection()
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    assert visitor.get("/", follow_redirects=False).headers["location"].startswith("/login")


def test_a_manager_only_lists_the_managers_of_their_own_restaurant(visitor):
    register(visitor)
    page = visitor.get("/account/managers").text
    assert "Pepe" in page
    assert DEMO_EMAIL not in page