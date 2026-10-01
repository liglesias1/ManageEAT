"""Shared presentation setup: the Jinja2 templates used by the pages of every domain."""
from fastapi.templating import Jinja2Templates

import config

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def eur(value):
    """Formats a number as euros, e.g. 1234.5 -> €1,234.50"""
    return f"€{value:,.2f}"


templates.env.filters["eur"] = eur