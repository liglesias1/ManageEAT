"""Who is logged in, and which restaurant the current request belongs to.

Every page asks for its restaurant with `restaurant_id: int = Depends(current_restaurant)` and passes
it to the repositories, so every query only sees that restaurant's rows. If nobody is logged in,
LoginRequired is raised and app.py sends the browser to the login page.
"""
from fastapi import Depends, Request

from accounts import repository
from database import get_db


class LoginRequired(Exception):
    """Raised when a page needs a logged-in manager; `path` is where to return after logging in."""

    def __init__(self, path):
        super().__init__(path)
        self.path = path


def current_user(request: Request, conn=Depends(get_db)):
    """The logged-in manager, read from the signed session cookie."""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise LoginRequired(request.url.path)
    user = repository.get_user(conn, user_id)
    if user is None:                      # the account was removed after logging in
        request.session.clear()
        raise LoginRequired(request.url.path)
    return user


def current_restaurant(user=Depends(current_user)):
    return user["restaurant_id"]