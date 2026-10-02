"""Generates realistic demo data that simulates the POS and the clock-in system.

The random generator uses a fixed seed, so every run produces exactly the same data.
"""
import random
from datetime import date, datetime, timedelta

# Dishes as the POS knows them: code -> (category, price in EUR)
MENU = {
    "SAL01": ("starter", 9.50),
    "CRO01": ("starter", 8.00),
    "GAZ01": ("starter", 7.50),
    "PAE01": ("main", 18.00),
    "SOL01": ("main", 21.00),
    "ENT01": ("main", 24.00),
    "HAM01": ("main", 14.50),
    "RIS01": ("main", 16.00),
    "TAR01": ("dessert", 6.50),
    "FLA01": ("dessert", 5.00),
    "AGU01": ("drink", 2.50),
    "VIN01": ("drink", 4.00),
    "CER01": ("drink", 3.50),
}

# How often each dish is chosen within its category (higher = more popular)
POPULARITY = {
    "SAL01": 3, "CRO01": 5, "GAZ01": 2,
    "PAE01": 6, "SOL01": 2, "ENT01": 3, "HAM01": 5, "RIS01": 1.5,
    "TAR01": 3, "FLA01": 2,
    "AGU01": 4, "VIN01": 3, "CER01": 4,
}

# Relative weight of orders at each opening hour (lunch 13-15h, dinner 20-23h)
HOURLY_WEIGHT = {13: 3, 14: 6, 15: 3, 20: 2, 21: 6, 22: 5, 23: 1}

# Demo staff: employee_id -> which service they usually work
# Demo staff: employee_id -> which service they usually work
EMPLOYEE_SHIFTS = {
    1: "lunch", 2: "lunch", 3: "dinner", 4: "dinner", 5: "lunch", 6: "dinner",
    7: "lunch", 8: "dinner", 9: "lunch", 10: "lunch", 11: "dinner", 12: "lunch",
    13: "dinner", 14: "dinner", 15: "lunch", 16: "dinner",
}

SHIFT_HOURS = {"lunch": (12, 16), "dinner": (19, 24)}

def _dishes(category):
    return [code for code, (cat, _) in MENU.items() if cat == category]

def _pick(rng, category):
    """Chooses a dish of the category, favouring the most popular ones."""
    dishes = _dishes(category)
    return rng.choices(dishes, [POPULARITY[code] for code in dishes])[0]

def _orders_for_day(rng, day):
    """Returns a list of (order_datetime, covers, items) for one day."""
    weekend = day.weekday() >= 4  # Friday to Sunday are busier
    total_orders = rng.randint(55, 75) if weekend else rng.randint(30, 45)
    hours = list(HOURLY_WEIGHT)
    weights = list(HOURLY_WEIGHT.values())

    orders = []
    for _ in range(total_orders):
        hour = rng.choices(hours, weights)[0]
        when = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59))
        covers = rng.randint(1, 6)
        items = {}
        for _ in range(covers):
            picks = [_pick(rng, "main"), _pick(rng, "drink")]
            if rng.random() < 0.5:
                picks.append(_pick(rng, "starter"))
            if rng.random() < 0.4:
                picks.append(_pick(rng, "dessert"))
            for code in picks:
                items[code] = items.get(code, 0) + 1
        orders.append((when, covers, items))
    return orders


def _shift_for(rng, day, service):
    start_h, end_h = SHIFT_HOURS[service]
    start = datetime(day.year, day.month, day.day) + timedelta(hours=start_h)
    end = datetime(day.year, day.month, day.day) + timedelta(hours=end_h)
    # People clock in/out a few minutes off the official times
    return start + timedelta(minutes=rng.randint(-10, 10)), end + timedelta(minutes=rng.randint(-5, 20))

def generate_demo_data(conn, start=date(2026, 9, 1), days=28, seed=42):
    rng = random.Random(seed)
    for offset in range(days):
        day = start + timedelta(days=offset)

        for when, covers, items in _orders_for_day(rng, day):
            cur = conn.execute(
                "INSERT INTO orders (table_no, covers, created_at) VALUES (?, ?, ?)",
                (rng.randint(1, 20), covers, when.isoformat()),
            )
            for code, qty in items.items():
                conn.execute(
                    "INSERT INTO order_items (order_id, item_code, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (cur.lastrowid, code, qty, MENU[code][1]),
                )

        for employee_id, service in EMPLOYEE_SHIFTS.items():
            if (employee_id + offset) % 7 in (0, 1):  # two days off per week
                continue
            clock_in, clock_out = _shift_for(rng, day, service)
            conn.execute(
                "INSERT INTO clock_ins (employee_id, clock_in, clock_out) VALUES (?, ?, ?)",
                (employee_id, clock_in.isoformat(), clock_out.isoformat()),
            )
    conn.commit()


def seed_if_empty(conn):
    """Only seeds a brand-new database, so restarting the app never duplicates data."""
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        generate_demo_data(conn)

        