"""Password hashing: only a salted hash is stored, never the password itself.

Uses PBKDF2-SHA256 from Python's standard library, so it needs no extra package and works on
every Python version the app supports. The stored value records the algorithm, the number of
iterations and the salt, so the cost can be raised later without breaking existing accounts.
"""
import hashlib
import hmac
import os

ITERATIONS = 600_000   # OWASP's recommendation for PBKDF2-SHA256


def hash_password(password, iterations=ITERATIONS):
    """'secret' -> 'pbkdf2_sha256$600000$<salt>$<hash>', different every time because of the random salt."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    """True if `password` produces the stored hash. Compares in constant time."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)