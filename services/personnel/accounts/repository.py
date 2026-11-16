"""SQL queries for accounts: restaurants and the managers who log in to them."""


def get_user_by_email(conn, email):
    """The manager with this email (ignoring upper and lower case), with their restaurant's name, or None."""
    row = conn.execute(
        """
        SELECT u.id, u.restaurant_id, u.name, u.email, u.password_hash, r.name AS restaurant
          FROM users u
          JOIN restaurants r ON r.id = u.restaurant_id
         WHERE u.email = ? COLLATE NOCASE
        """,
        (email,),
    ).fetchone()
    return dict(row) if row else None


def get_user(conn, user_id):
    """One manager with their restaurant's name, or None if the account no longer exists."""
    row = conn.execute(
        """
        SELECT u.id, u.restaurant_id, u.name, u.email, r.name AS restaurant
          FROM users u
          JOIN restaurants r ON r.id = u.restaurant_id
         WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def get_managers(conn, restaurant_id):
    """Every manager of one restaurant, in the order they joined."""
    rows = conn.execute(
        "SELECT id, name, email FROM users WHERE restaurant_id = ? ORDER BY id", (restaurant_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def add_restaurant(conn, restaurant_name, name, email, password_hash):
    """Creates a restaurant and its first manager in one transaction; returns the new manager's id."""
    with conn:
        restaurant_id = conn.execute("INSERT INTO restaurants (name) VALUES (?)", (restaurant_name,)).lastrowid
        user_id = conn.execute(
            "INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            (restaurant_id, name, email, password_hash),
        ).lastrowid
    return user_id


def add_manager(conn, restaurant_id, name, email, password_hash):
    """Adds another manager to an existing restaurant; returns their id."""
    with conn:
        user_id = conn.execute(
            "INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            (restaurant_id, name, email, password_hash),
        ).lastrowid
    return user_id