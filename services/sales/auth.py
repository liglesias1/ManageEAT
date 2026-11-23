"""Which restaurant a request belongs to, read from the login token that personnel signed (ADR-6).

Sales does not have the users table, so it cannot look the manager up: it trusts the token because only
someone with TOKEN_SECRET can sign one, and it refuses tokens that are expired, changed or signed with
another secret. A removed manager's token keeps working here until it expires (at most 15 minutes),
which is the cost ADR-6 accepts so that sales keeps working when personnel is down.
"""
from typing import NamedTuple

import jwt  # PyJWT
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config

ALGORITHM = "HS256"   # the algorithm personnel signs with

bearer = HTTPBearer(auto_error=False)


class Session(NamedTuple):
    restaurant_id: int
    token: str      # kept to forward it when sales asks personnel for wages


def _unauthorized(detail):
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_session(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """The restaurant in a valid token, and the token itself; 401 otherwise."""
    if credentials is None:
        raise _unauthorized("Log in first")
    try:
        # require: a token without an expiry or a restaurant is never accepted, even if correctly signed
        claims = jwt.decode(credentials.credentials, config.TOKEN_SECRET, algorithms=[ALGORITHM],
                            options={"require": ["exp", "restaurant_id"]})
    except jwt.InvalidTokenError:
        raise _unauthorized("The session has expired or is not valid; log in again")
    return Session(restaurant_id=int(claims["restaurant_id"]), token=credentials.credentials)


def current_restaurant(session: Session = Depends(current_session)):
    return session.restaurant_id
