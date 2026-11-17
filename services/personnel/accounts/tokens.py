"""Login tokens: a signed note saying which manager and restaurant a request comes from (ADR-6).

A token is a JWT signed with HMAC-SHA256 and TOKEN_SECRET. Anyone can read what it says, but nobody can
change it or make a new one without the secret, so a service that has the secret can trust it without
asking anyone. Personnel creates tokens at login and renewal; both services read them.
"""
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

import config

ALGORITHM = "HS256"


def create_token(user):
    """A token for this manager that expires TOKEN_MINUTES from now."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user["id"]),                 # who: the manager (JWT requires the subject to be text)
        "restaurant_id": user["restaurant_id"],  # which restaurant's data they may see
        "iat": now,                              # issued at
        "exp": now + timedelta(minutes=config.TOKEN_MINUTES),
    }
    return jwt.encode(claims, config.TOKEN_SECRET, algorithm=ALGORITHM)


def read_token(token):
    """What the token says, or None if it was changed, signed with another secret, expired or is not a token.

    algorithms=[ALGORITHM] is required: it stops a forged token from choosing a weaker algorithm itself.
    """
    try:
        return jwt.decode(token, config.TOKEN_SECRET, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None