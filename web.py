"""Shared presentation setup: the Jinja2 templates used by the pages of every domain."""
from fastapi.templating import Jinja2Templates

import config

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def eur(value):
    """Formats a number as euros, e.g. 1234.5 -> €1,234.50 and -3200 -> -€3,200.00"""
    sign = "-" if value < 0 else ""
    return f"{sign}€{abs(value):,.2f}"


templates.env.filters["eur"] = eur



def form_errors(error, labels=None):
    """Pydantic errors as short sentences for the forms, e.g. 'Unit cost: input should be greater than 0'.

    Every form of the app shows its errors with this one function. The field comes from the error's
    location without list positions ('recipe', 0, 'quantity' -> 'Recipe quantity'), `labels` can rename
    a field ({'new_supplier lead_time_days': ...}), and errors of the whole form have no field.
    """
    labels = labels or {}
    messages = []
    for e in error.errors():
        key = " ".join(str(part) for part in e["loc"] if not isinstance(part, int))
        where = labels.get(key, key.replace("_", " ").capitalize())
        text = e["msg"].replace("Value error, ", "")
        messages.append(f"{where}: {text[0].lower() + text[1:]}" if where else text[0].upper() + text[1:])
    return messages