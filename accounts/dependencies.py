"""Which restaurant the current request belongs to.

Every page asks for it with `restaurant_id: int = Depends(current_restaurant)` and passes it to
the repositories, so every query only sees that restaurant's rows. For now there is no login yet,
so it is always the demo restaurant; the login step only has to change this one function.
"""
from accounts.seed import DEMO_RESTAURANT_ID


def current_restaurant():
    return DEMO_RESTAURANT_ID