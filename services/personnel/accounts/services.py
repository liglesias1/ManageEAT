"""Account logic: checking a login and creating accounts. Passwords are only ever handled as hashes."""
from accounts import repository
from accounts.passwords import hash_password, verify_password


def authenticate(conn, email, password):
    """The manager if the email and password match, otherwise None.

    The same None is returned for an unknown email and for a wrong password, so the login page
    never reveals which emails have an account.
    """
    user = repository.get_user_by_email(conn, email)
    if user is None or not verify_password(password, user["password_hash"]):
        return None
    return user


def email_taken(conn, email):
    return repository.get_user_by_email(conn, email) is not None


def register_restaurant(conn, restaurant_name, name, email, password):
    """Creates a restaurant with its first manager and returns the manager's id."""
    return repository.add_restaurant(conn, restaurant_name, name, email, hash_password(password))


def add_manager(conn, restaurant_id, name, email, password):
    """Gives another person their own login to the same restaurant."""
    return repository.add_manager(conn, restaurant_id, name, email, hash_password(password))