"""Pages to register a restaurant, log in and out, and add more managers to a restaurant."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from accounts import repository, services
from accounts.dependencies import current_user
from accounts.schemas import MIN_PASSWORD_LENGTH, LoginIn, ManagerIn, RegisterIn
from database import get_connection
from web import templates

router = APIRouter(tags=["accounts"])


def _messages(error):
    """Pydantic errors as short sentences, e.g. 'Password: string should have at least 8 characters'."""
    messages = []
    for e in error.errors():
        field = str(e["loc"][0]).replace("_", " ").capitalize() if e["loc"] else ""
        text = e["msg"].replace("Value error, ", "")
        messages.append(f"{field}: {text.lower()}" if field else text.capitalize())
    return messages


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
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/")):
    form = {"email": email}
    try:
        credentials = LoginIn(email=email, password=password)
    except ValidationError:
        credentials = None
    user = None
    if credentials:
        conn = get_connection()
        try:
            user = services.authenticate(conn, credentials.email, credentials.password)
        finally:
            conn.close()
    if user is None:
        # One message for every failure, so the page never tells which emails have an account
        return templates.TemplateResponse(
            request, "accounts/login.html",
            {"next": next, "form": form, "errors": ["The email or the password is not correct"]},
            status_code=401,
        )
    _log_in(request, user)
    return RedirectResponse(_safe_next(next), status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------- Register a new restaurant ----------

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request, "accounts/register.html", {"form": {}, "errors": [], "min_password": MIN_PASSWORD_LENGTH}
    )


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    restaurant_name: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
):
    form = {"restaurant_name": restaurant_name, "name": name, "email": email}

    def page_with(errors):
        return templates.TemplateResponse(
            request, "accounts/register.html",
            {"form": form, "errors": errors, "min_password": MIN_PASSWORD_LENGTH}, status_code=422,
        )

    try:
        account = RegisterIn(restaurant_name=restaurant_name, name=name, email=email, password=password)
    except ValidationError as error:
        return page_with(_messages(error))

    conn = get_connection()
    try:
        if services.email_taken(conn, account.email):
            return page_with(["Email: there is already an account with that email"])
        user_id = services.register_restaurant(conn, account.restaurant_name, account.name, account.email,
                                               account.password)
        user = repository.get_user(conn, user_id)
    finally:
        conn.close()
    _log_in(request, user)                   # a new restaurant starts empty, ready to add its menu and staff
    return RedirectResponse("/", status_code=303)


# ---------- Managers of the restaurant ----------

def _managers_page(request, user, errors=None, form=None, added=None, status_code=200):
    conn = get_connection()
    try:
        managers = repository.get_managers(conn, user["restaurant_id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "accounts/managers.html",
        {"managers": managers, "user": user, "errors": errors or [], "form": form or {}, "added": added,
         "min_password": MIN_PASSWORD_LENGTH},
        status_code=status_code,
    )


@router.get("/account/managers", response_class=HTMLResponse)
def managers_page(request: Request, added: str = None, user=Depends(current_user)):
    return _managers_page(request, user, added=added)


@router.post("/account/managers", response_class=HTMLResponse)
def add_manager(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    user=Depends(current_user),
):
    form = {"name": name, "email": email}
    try:
        manager = ManagerIn(name=name, email=email, password=password)
    except ValidationError as error:
        return _managers_page(request, user, errors=_messages(error), form=form, status_code=422)

    conn = get_connection()
    try:
        if services.email_taken(conn, manager.email):
            return _managers_page(request, user, errors=["Email: there is already an account with that email"],
                                  form=form, status_code=422)
        services.add_manager(conn, user["restaurant_id"], manager.name, manager.email, manager.password)
    finally:
        conn.close()
    return RedirectResponse(f"/account/managers?{urlencode({'added': manager.email})}", status_code=303)