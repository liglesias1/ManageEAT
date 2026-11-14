"""Restaurant accounts: password hashing, the demo account and its managers."""
import sqlite3

import pytest

from accounts.passwords import hash_password, verify_password
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD, DEMO_PASSWORD_HASH, DEMO_RESTAURANT_ID, seed_demo_restaurant

FAST = 1_000   # few iterations so the tests stay fast; the app uses accounts.passwords.ITERATIONS


def test_the_right_password_matches_its_hash():
    stored = hash_password("s3cret!", iterations=FAST)
    assert verify_password("s3cret!", stored)
    assert not verify_password("S3cret!", stored)


def test_the_password_itself_is_never_stored():
    stored = hash_password("s3cret!", iterations=FAST)
    assert "s3cret!" not in stored
    assert stored.startswith(f"pbkdf2_sha256${FAST}$")


def test_the_same_password_gives_a_different_hash_each_time():
    # a random salt per password: two restaurants with the same password do not share a hash
    assert hash_password("s3cret!", iterations=FAST) != hash_password("s3cret!", iterations=FAST)


def test_a_malformed_or_unknown_hash_never_matches():
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "md5$1$00$00")


def test_the_demo_password_matches_the_stored_demo_hash():
    assert verify_password(DEMO_PASSWORD, DEMO_PASSWORD_HASH)


def test_demo_account_is_created_once(conn):
    assert seed_demo_restaurant(conn) == DEMO_RESTAURANT_ID
    seed_demo_restaurant(conn)
    assert conn.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_a_restaurant_can_have_several_managers_each_with_their_own_password(conn):
    seed_demo_restaurant(conn)
    conn.execute("INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (?, 'Second manager', "
                 "'second@manageeat.com', ?)", (DEMO_RESTAURANT_ID, hash_password("other-pass", iterations=FAST)))
    managers = conn.execute("SELECT email FROM users WHERE restaurant_id = ? ORDER BY id",
                            (DEMO_RESTAURANT_ID,)).fetchall()
    assert [m["email"] for m in managers] == [DEMO_EMAIL, "second@manageeat.com"]


def test_one_login_per_email_whatever_the_case(conn):
    seed_demo_restaurant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (1, 'Copy', ?, 'x')",
                     (DEMO_EMAIL.upper(),))


def test_a_manager_must_belong_to_an_existing_restaurant(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (99, 'Nobody', "
                     "'nobody@manageeat.com', 'x')")



# ---------- Checking a login ----------

def test_authenticate_returns_the_manager_only_with_the_right_password(conn):
    from accounts.services import authenticate, register_restaurant

    register_restaurant(conn, "Bar Pepe", "Pepe", "pepe@barpepe.es", "tortilla99")
    assert authenticate(conn, "pepe@barpepe.es", "tortilla99")["restaurant"] == "Bar Pepe"
    assert authenticate(conn, "PEPE@barpepe.es", "tortilla99") is not None
    assert authenticate(conn, "pepe@barpepe.es", "wrong") is None
    assert authenticate(conn, "nobody@barpepe.es", "tortilla99") is None


def test_an_unknown_user_id_finds_no_account(conn):
    from accounts.repository import get_user

    assert get_user(conn, 999) is None