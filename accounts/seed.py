"""The demo account: a restaurant that owns the demo data, and its manager, so the app can be tried straight away."""

DEMO_RESTAURANT_ID = 1
DEMO_RESTAURANT_NAME = "Demo restaurant"
DEMO_USER_NAME = "Demo manager"
DEMO_EMAIL = "demo@manageeat.com"
DEMO_PASSWORD = "demo1234"     # documented in the README so anyone can log in to the demo
# hash_password(DEMO_PASSWORD), computed once: hashing on every start would slow the app and the tests down
DEMO_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$69eccd2fe479383ba6b7efd91c780b42"
    "$06f5712965c7fb7151cf3e12e86acfee1801cd8a619734c9e7b97d616ea0b423"
)


def seed_demo_restaurant(conn):
    """Creates the demo restaurant and its manager on a brand-new database, and returns the restaurant's id."""
    exists = conn.execute("SELECT 1 FROM restaurants WHERE id = ?", (DEMO_RESTAURANT_ID,)).fetchone()
    if not exists:
        with conn:
            conn.execute("INSERT INTO restaurants (id, name) VALUES (?, ?)", (DEMO_RESTAURANT_ID, DEMO_RESTAURANT_NAME))
            conn.execute(
                "INSERT INTO users (restaurant_id, name, email, password_hash) VALUES (?, ?, ?, ?)",
                (DEMO_RESTAURANT_ID, DEMO_USER_NAME, DEMO_EMAIL, DEMO_PASSWORD_HASH),
            )
    return DEMO_RESTAURANT_ID