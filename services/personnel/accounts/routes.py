"""Pages to register a restaurant, log in and out, and add more managers to a restaurant."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from accounts import repository, services
from accounts.dependencies import current_user
from accounts.schemas import MIN_PASSWORD_LENGTH, LoginIn, ManagerIn, RegisterIn
from database import get_db
from web import form_errors, templates

router = APIRouter(tags=["accounts"])

EMAIL_TAKEN = "Email: there is already an account with that email"


def _safe_next(next_path):
    """Only return to a page of this site: '/sales/menu' yes, 'https://evil.com' or '//evil.com' no."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


def _log_in(request, user):
    """Starts a new session for this manager. Clearing it first means an old session is never reused.

    The names are kept only to show who is logged in; every page reads the account again by user_id.
    """
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["user_name"] = user["name"]
    request.session["restaurant_name"] = user["restaurant"]


# ---------- Log in and out ----------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if request.session.get("user_id"):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(request, "accounts/login.html", {"next": next, "form": {}, "errors": []})


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/"),
          conn=Depends(get_db)):
    try:
        credentials = LoginIn(email=email, password=password)
        user = services.authenticate(conn, credentials.email, credentials.password)
    except ValidationError:
        user = None
    if user is None:
        # One message for every failure, so the page never tells which emails have an account
        return templates.TemplateResponse(
            request, "accounts/login.html",
            {"next": next, "form": {"email": email}, "errors": ["The email or the password is not correct"]},
            status_code=401,
        )
    _log_in(request, user)
    return RedirectResponse(_safe_next(next), status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------- Register a new restaurant ----------

def _register_page(request, form=None, errors=None, status_code=200):
    return templates.TemplateResponse(
        request, "accounts/register.html",
        {"form": form or {}, "errors": errors or [], "min_password": MIN_PASSWORD_LENGTH}, status_code=status_code,
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return _register_page(request)


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    restaurant_name: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    conn=Depends(get_db),
):
    form = {"restaurant_name": restaurant_name, "name": name, "email": email}
    try:
        account = RegisterIn(restaurant_name=restaurant_name, name=name, email=email, password=password)
    except ValidationError as error:
        return _register_page(request, form, form_errors(error), status_code=422)
    if services.email_taken(conn, account.email):
        return _register_page(request, form, [EMAIL_TAKEN], status_code=422)

    user_id = services.register_restaurant(conn, account.restaurant_name, account.name, account.email,
                                           account.password)
    _log_in(request, repository.get_user(conn, user_id))   # a new restaurant starts empty, ready to fill in
    return RedirectResponse("/", status_code=303)


# ---------- Managers of the restaurant ----------

def _managers_page(request, conn, user, errors=None, form=None, added=None, status_code=200):
    return templates.TemplateResponse(
        request, "accounts/managers.html",
        {"managers": repository.get_managers(conn, user["restaurant_id"]), "user": user, "errors": errors or [],
         "form": form or {}, "added": added, "min_password": MIN_PASSWORD_LENGTH},
        status_code=status_code,
    )


@router.get("/account/managers", response_class=HTMLResponse)
def managers_page(request: Request, added: str = None, conn=Depends(get_db), user=Depends(current_user)):
    return _managers_page(request, conn, user, added=added)


@router.post("/account/managers", response_class=HTMLResponse)
def add_manager(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    conn=Depends(get_db),
    user=Depends(current_user),
):
    form = {"name": name, "email": email}
    try:
        manager = ManagerIn(name=name, email=email, password=password)
    except ValidationError as error:
        return _managers_page(request, conn, user, errors=form_errors(error), form=form, status_code=422)
    if services.email_taken(conn, manager.email):
        return _managers_page(request, conn, user, errors=[EMAIL_TAKEN], form=form, status_code=422)

    services.add_manager(conn, user["restaurant_id"], manager.name, manager.email, manager.password)
    return RedirectResponse(f"/account/managers?{urlencode({'added': manager.email})}", status_code=303)