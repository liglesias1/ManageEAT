"""Who is making the request, and which restaurant it belongs to.

Every endpoint that needs a manager asks for `restaurant_id: int = Depends(current_restaurant)` (or
`user = Depends(current_user)`). The token comes in the header `Authorization: Bearer <token>`. Personnel
owns the users table, so besides checking the token it looks the manager up on every request: a removed
manager is refused at once, as in the monolith (ADR-6).
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from accounts import repository
from accounts.tokens import read_token
from database import get_db

# auto_error=False: a missing header reaches current_user, which answers 401 with the same shape as a bad token
bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail):
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), conn=Depends(get_db)):
    """The logged-in manager, or 401 if the token is missing, invalid or expired, or the account is gone."""
    if credentials is None:
        raise _unauthorized("Log in first")
    claims = read_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("The session has expired or is not valid; log in again")
    user = repository.get_user(conn, int(claims["sub"]))
    if user is None:
        raise _unauthorized("This account no longer exists")
    return user


def current_restaurant(user=Depends(current_user)):
    return user["restaurant_id"]
