'''Buisness logic of the sales domain, makes calculations, no queries to the database.'''

import math
from datetime import date

# Kasavana & Smith menu engineering: a dish is "popular" if it sells at least
# 70% of what it would sell if every dish in its category sold the same amount.
POPULARITY_FACTOR = 0.7

RECOMMENDATIONS = {
    "star": "Keep it and give it a prominent place on the menu.",
    "plowhorse": "Popular but low margin: review its price or ingredient cost.",
    "puzzle": "Profitable but rarely ordered: promote it or reposition it on the menu.",
    "dog": "Low sales and low margin: consider removing it.",
}


def classify_menu(dishes):
    """Adds price, margin and a menu engineering class to each dish.

    `dishes` is a list of dicts with: code, name, category, units_sold, revenue, unit_cost.
    Each category is analysed separately, so a drink is only compared with other drinks.
    """
    result = []
    for category in sorted({dish["category"] for dish in dishes}):
        group = [dish for dish in dishes if dish["category"] == category]
        total_units = sum(dish["units_sold"] for dish in group)

        analysed = []
        for dish in group:
            units = dish["units_sold"]
            avg_price = dish["revenue"] / units if units else 0.0
            margin = avg_price - dish["unit_cost"]
            analysed.append({**dish, "avg_price": avg_price, "margin": margin, "total_margin": margin * units})

        popularity_threshold = POPULARITY_FACTOR * total_units / len(group)
        average_margin = sum(d["total_margin"] for d in analysed) / total_units if total_units else 0.0

        for dish in analysed:
            popular = dish["units_sold"] > 0 and dish["units_sold"] >= popularity_threshold
            profitable = dish["margin"] >= average_margin
            if popular and profitable:
                dish["class"] = "star"
            elif popular:
                dish["class"] = "plowhorse"
            elif profitable:
                dish["class"] = "puzzle"
            else:
                dish["class"] = "dog"
            dish["recommendation"] = RECOMMENDATIONS[dish["class"]]
            dish["popularity_threshold"] = popularity_threshold
            dish["average_margin"] = average_margin
            result.append(dish)
    return result


def menu_summary(dishes):
    """Key figures for the whole menu, from the output of classify_menu."""
    revenue = sum(d["revenue"] for d in dishes)
    ingredient_cost = sum(d["unit_cost"] * d["units_sold"] for d in dishes)
    # Drinks always sell the most units, so best/least ordered only look at food
    food = [d for d in dishes if d["category"] != "drink"]
    return {
        "revenue": revenue,
        "ingredient_cost": ingredient_cost,
        "gross_margin": revenue - ingredient_cost,
        "food_cost_pct": ingredient_cost / revenue * 100 if revenue else 0.0,
        "best_seller": max(food, key=lambda d: d["units_sold"])["name"] if food else None,
        "least_ordered": min(food, key=lambda d: d["units_sold"])["name"] if food else None,
        "class_counts": {c: sum(1 for d in dishes if d["class"] == c) for c in RECOMMENDATIONS},
    }



# ---------- Inventory ----------

# When suggesting an order, buy enough for the supplier's delivery time plus one more week
ORDER_COVER_DAYS = 7


def stock_status(ingredients, as_of):
    """Current stock, daily use, days left and whether to reorder, for each ingredient.

    Current stock = last stocktake - what the recipes say was used since then.
    An ingredient needs reordering if it is below its reorder level, or if it will run out
    before a new delivery could arrive (days left <= the supplier's lead time).
    """
    result = []
    for item in ingredients:
        current = item["counted_stock"] - item["used_since_count"]
        days_counted = (date.fromisoformat(as_of) - date.fromisoformat(item["counted_at"])).days + 1 if as_of else 0
        daily_use = item["used_since_count"] / days_counted if days_counted > 0 else 0.0
        days_left = max(current, 0) / daily_use if daily_use else None

        if current <= 0:
            status = "out"
        elif current < item["reorder_level"] or (days_left is not None and days_left <= item["lead_time_days"]):
            status = "reorder"
        else:
            status = "ok"

        needed = daily_use * (item["lead_time_days"] + ORDER_COVER_DAYS) + item["reorder_level"] - max(current, 0)
        result.append({
            **item,
            "current": current,
            "daily_use": daily_use,
            "days_left": days_left,
            "status": status,
            "suggested_order": math.ceil(needed) if status != "ok" and needed > 0 else 0,
            "stock_value": max(current, 0) * item["unit_cost"],
            "spend_in_period": item.get("used_in_period", 0) * item["unit_cost"],
        })
    order = {"out": 0, "reorder": 1, "ok": 2}
    return sorted(result, key=lambda i: (order[i["status"]], i["days_left"] if i["days_left"] is not None else 1e9))


def inventory_summary(stock):
    return {
        "to_reorder": sum(1 for i in stock if i["status"] == "reorder"),
        "out_of_stock": sum(1 for i in stock if i["status"] == "out"),
        "stock_value": sum(i["stock_value"] for i in stock),
        "order_value": sum(i["suggested_order"] * i["unit_cost"] for i in stock),
    }



def supplier_summary(stock):
    """Key figures for one supplier's page, from the stock_status of its ingredients."""
    return {
        "spend": sum(i["spend_in_period"] for i in stock),
        "to_reorder": sum(1 for i in stock if i["status"] != "ok"),
        "order_value": sum(i["suggested_order"] * i["unit_cost"] for i in stock),
    }