"""Home page: the key figures of every page in one place.

This module is not a domain. It sits on top of both and only calls their public facades
(domains/sales/public.py and domains/personnel/public.py), so the rule of ADR-2 (sales and
personnel stay separable) still holds, and in Assignment 2 it becomes the client of the two services.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from accounts.dependencies import current_restaurant
from domains.personnel import public as personnel
from domains.sales import public as sales
from web import templates

router = APIRouter(tags=["overview"])


def attention_items(figures):
    """The few things a manager should act on today, each with the page where to do it."""
    items = []
    if figures["to_reorder"]:
        items.append({"text": "Ingredients to reorder: " + ", ".join(figures["to_reorder"]),
                      "link": "/sales/inventory", "page": "Inventory"})
    role = figures["schedule"]["most_missing_role"]
    if role:
        items.append({"text": f"{role} is the role most often short of people",
                      "link": "/personnel/schedule", "page": "Staff & schedule"})
    if figures["dogs"]:
        items.append({"text": f"Dishes that sell little and earn little: {', '.join(figures['dogs'])}",
                      "link": "/sales/menu", "page": "Menu performance"})
    if figures["pl"]["net_profit"] < 0:
        items.append({"text": "The month is losing money", "link": "/sales/profit-loss", "page": "Profit & loss"})
    return items


@router.get("/", response_class=HTMLResponse)
def overview_page(request: Request, restaurant_id: int = Depends(current_restaurant)):
    figures = {**sales.overview_figures(restaurant_id), **personnel.overview_figures(restaurant_id)}
    return templates.TemplateResponse(
        request, "overview.html", {**figures, "attention": attention_items(figures)}
    )