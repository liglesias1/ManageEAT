"""Accounts API: register a restaurant, log in, renew the token, and manage the restaurant's managers.

There is no logout endpoint: the token lives in the browser, so logging out is the UI forgetting it.
A forgotten token still works until it expires (at most TOKEN_MINUTES), which ADR-6 accepts.
"""
from fastapi import APIRouter, Depends, HTTPException

import config
from accounts import repository, services
from accounts.dependencies import current_user
from accounts.schemas import LoginIn, ManagerIn, ManagerOut, RegisterIn, SessionOut
from accounts.tokens import create_token
from database import get_db

router = APIRouter(tags=["accounts"])

# Documented answers besides the success one (the body is {"detail": "<message>"})
NO_TOKEN = {401: {"description": "Missing, invalid or expired token, or the account no longer exists"}}
EMAIL_IN_USE = {409: {"description": "There is already an account with that email"}}

EMAIL_TAKEN = "There is already an account with that email"
WRONG_LOGIN = "The email or the password is not correct"


def _session(user):
    """Token plus who it belongs to; `user` is a row from accounts.repository (with the restaurant's name)."""
    return {
        "token": create_token(user),
        "expires_in": config.TOKEN_MINUTES * 60,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        "restaurant": {"id": user["restaurant_id"], "name": user["restaurant"]},
    }


@router.post("/auth/login", response_model=SessionOut,
             responses={401: {"description": "The email or the password is not correct"}})
def login(credentials: LoginIn, conn=Depends(get_db)):
    user = services.authenticate(conn, credentials.email, credentials.password)
    if user is None:
        # One message for an unknown email and a wrong password, so the API never tells which emails exist
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)
    return _session(user)


@router.post("/auth/register", response_model=SessionOut, status_code=201, responses=EMAIL_IN_USE)
def register(account: RegisterIn, conn=Depends(get_db)):
    """Creates a restaurant with its first manager and logs them in. A new restaurant starts empty."""
    if services.email_taken(conn, account.email):
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)
    user_id = services.register_restaurant(conn, account.restaurant_name, account.name, account.email,
                                           account.password)
    return _session(repository.get_user(conn, user_id))


@router.post("/auth/refresh", response_model=SessionOut, responses=NO_TOKEN)
def refresh(user=Depends(current_user)):
    """A new token for a manager whose current token is still valid.

    current_user has already looked the manager up, so a removed manager gets 401 here and their
    last token stops working in sales within TOKEN_MINUTES (ADR-6).
    """
    return _session(user)


@router.get("/auth/me", response_model=ManagerOut, responses=NO_TOKEN)
def me(user=Depends(current_user)):
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


@router.get("/account/managers", response_model=list[ManagerOut], responses=NO_TOKEN)
def list_managers(conn=Depends(get_db), user=Depends(current_user)):
    """Every manager of the logged-in manager's restaurant, and only of that restaurant."""
    return repository.get_managers(conn, user["restaurant_id"])


@router.post("/account/managers", response_model=ManagerOut, status_code=201,
             responses={**NO_TOKEN, **EMAIL_IN_USE})
def add_manager(manager: ManagerIn, conn=Depends(get_db), user=Depends(current_user)):
    """Gives another person their own login to the same restaurant."""
    if services.email_taken(conn, manager.email):
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)
    manager_id = services.add_manager(conn, user["restaurant_id"], manager.name, manager.email, manager.password)
    return {"id": manager_id, "name": manager.name, "email": manager.email}
