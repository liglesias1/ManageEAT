"""Login tokens: what they contain, and every way a token must be refused."""
from datetime import datetime, timedelta, timezone

import jwt

import config
from accounts.tokens import ALGORITHM, create_token, read_token

MANAGER = {"id": 7, "restaurant_id": 3}


def test_a_token_says_who_and_which_restaurant():
    claims = read_token(create_token(MANAGER))
    assert claims["sub"] == "7" and claims["restaurant_id"] == 3


def test_a_token_expires_after_token_minutes():
    claims = read_token(create_token(MANAGER))
    assert claims["exp"] - claims["iat"] == config.TOKEN_MINUTES * 60


def test_an_expired_token_is_refused():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = jwt.encode({"sub": "7", "restaurant_id": 3, "exp": past}, config.TOKEN_SECRET, algorithm=ALGORITHM)
    assert read_token(expired) is None


def test_a_token_signed_with_another_secret_is_refused():
    forged = jwt.encode({"sub": "7", "restaurant_id": 3}, "someone-elses-secret-0123456789abcdef",
                        algorithm=ALGORITHM)
    assert read_token(forged) is None


def test_a_token_changed_after_signing_is_refused():
    header, payload, signature = create_token(MANAGER).split(".")
    other = create_token({"id": 7, "restaurant_id": 999}).split(".")[1]     # someone else's restaurant
    assert read_token(f"{header}.{other}.{signature}") is None


def test_an_unsigned_token_is_refused():
    unsigned = jwt.encode({"sub": "7", "restaurant_id": 3}, key=None, algorithm="none")
    assert read_token(unsigned) is None


def test_garbage_is_not_a_token():
    assert read_token("not-a-token") is None