'''Buisness logic of the sales domain, makes calculations, no queries to the database.'''

import calendar
import math
from datetime import date, timedelta

# Kasavana & Smith menu engineering: a dish is "popular" if it sells at least
# 70% of what it would sell if every dish in its category sold the same amount.
POPULARITY_FACTOR = 0.7

RECOMMENDATIONS = {
    "star": "Keep it and give it a prominent place on the menu.",
    "plowhorse": "Popular but low margin: review its price or ingredient cost.",
    "puzzle": "Profitable but rarely ordered: promote it or reposition it on the menu.",
    "dog": "Low sales and low margin: consider removing it.",
    "new": "No sales yet: wait until it has been on the menu for a while before judging it.",
}


def classify_menu(dishes):
    """Adds price, margin and a menu engineering class to each dish.

    `dishes` is a list of dicts with: code, name, category, units_sold, revenue, unit_cost.
    Each category is analysed separately, so a drink is only compared with other drinks.
    """
    result = []
    for category in sorted({dish["category"] for dish in dishes}):
        group = [dish for dish in dishes if dish["category"] == category and dish["units_sold"] > 0]
        # A dish that has never been sold cannot be judged yet, and would lower the category's averages
        for dish in dishes:
            if dish["category"] == category and dish["units_sold"] == 0:
                result.append({**dish, "avg_price": 0.0, "margin": 0.0, "total_margin": 0.0,
                               "class": "new", "recommendation": RECOMMENDATIONS["new"]})
        if not group:
            continue
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
            popular = dish["units_sold"] >= popularity_threshold
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
    food = [d for d in dishes if d["category"] != "drink" and d["class"] != "new"]
    return {
        "revenue": revenue,
        "ingredient_cost": ingredient_cost,
        "gross_margin": revenue - ingredient_cost,
        "food_cost_pct": ingredient_cost / revenue * 100 if revenue else 0.0,
        "best_seller": max(food, key=lambda d: d["units_sold"])["name"] if food else None,
        "least_ordered": min(food, key=lambda d: d["units_sold"])["name"] if food else None,
        "class_counts": {c: sum(1 for d in dishes if d["class"] == c) for c in RECOMMENDATIONS},
    }


# ---------- Dishes and recipes ----------

# Food cost a restaurant usually aims for: ingredients should be at most 35% of the menu price
FOOD_COST_TARGET = 35


def cost_dishes(dishes, recipe_lines):
    """Adds the recipe, ingredient cost, margin, markup and food cost % to each dish on the menu.

    `dishes` is a list of dicts with: code, name, category, price.
    `recipe_lines` is a list of dicts with: item_code, ingredient, unit, quantity, unit_cost.
    Markup = how much the price is above the cost; food cost % = how much of the price goes on ingredients.
    """
    result = []
    for dish in dishes:
        recipe = [
            {**line, "line_cost": line["quantity"] * line["unit_cost"]}
            for line in recipe_lines
            if line["item_code"] == dish["code"]
        ]
        cost = sum(line["line_cost"] for line in recipe)
        food_cost_pct = cost / dish["price"] * 100
        result.append({
            **dish,
            "recipe": sorted(recipe, key=lambda line: line["line_cost"], reverse=True),
            "cost": cost,
            "margin": dish["price"] - cost,
            "markup_pct": (dish["price"] - cost) / cost * 100 if cost else None,
            "food_cost_pct": food_cost_pct,
            "above_target": food_cost_pct > FOOD_COST_TARGET,
        })
    return result


def dishes_summary(costed):
    """Key figures for the menu page, from the output of cost_dishes."""
    if not costed:
        return {"dishes": 0, "avg_food_cost_pct": 0.0, "above_target": 0, "highest": None}
    highest = max(costed, key=lambda d: d["food_cost_pct"])
    return {
        "dishes": len(costed),
        "avg_food_cost_pct": sum(d["food_cost_pct"] for d in costed) / len(costed),
        "above_target": sum(1 for d in costed if d["above_target"]),
        "highest": highest,
    }


def new_dish_code(name, existing_codes):
    """A POS-style code for a new dish: first three letters of its name and a number, e.g. Tiramisu -> TIR01."""
    letters = "".join(c for c in name.upper() if "A" <= c <= "Z")[:3].ljust(3, "X")
    number = 1
    while f"{letters}{number:02d}" in existing_codes:
        number += 1
    return f"{letters}{number:02d}"


# ---------- Inventory ----------

# When suggesting an order, buy enough for the supplier's delivery time plus one more week
ORDER_COVER_DAYS = 7


def stock_status(ingredients, as_of):
    """Current stock, daily use, days left and whether to reorder, for each ingredient.

    Current stock = last stocktake + deliveries received since then - what the recipes say was used.
    An ingredient needs reordering if it is below its reorder level, or if it will run out
    before a new delivery could arrive (days left <= the supplier's lead time).
    """
    result = []
    for item in ingredients:
        current = item["counted_stock"] + item.get("received_since_count", 0) - item["used_since_count"]
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


def supplier_summary(stock, purchases=()):
    """Key figures for one supplier's page, from the stock_status of its ingredients and its deliveries."""
    return {
        "purchased": sum(p["total"] for p in purchases),
        "deliveries": len(purchases),
        "spend": sum(i["spend_in_period"] for i in stock),
        "to_reorder": sum(1 for i in stock if i["status"] != "ok"),
        "order_value": sum(i["suggested_order"] * i["unit_cost"] for i in stock),
    }



# ---------- Profit and loss ----------

def _week_ranges(start, end):
    """Splits a period into blocks of 7 days: [('2026-09-01', '2026-09-07'), ...]."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    weeks = []
    while first <= last:
        week_end = min(first + timedelta(days=6), last)
        weeks.append((first.isoformat(), week_end.isoformat()))
        first = week_end + timedelta(days=1)
    return weeks


def profit_and_loss(daily_sales, fixed_expenses, labor_cost_for, start, end):
    """Monthly profit and loss statement with a week-by-week breakdown.

    `labor_cost_for(start, end)` returns the wage cost of a period. It is passed in rather than
    imported so that this function never depends on how the personnel domain calculates payroll.
    Fixed expenses are monthly, so each week gets its share by number of days.
    """
    fixed_total = sum(e["amount"] for e in fixed_expenses)
    days_in_month = calendar.monthrange(int(start[:4]), int(start[5:7]))[1] if start else 1

    weeks = []
    for week_start, week_end in (_week_ranges(start, end) if start else []):
        days = [d for d in daily_sales if week_start <= d["day"] <= week_end]
        length = (date.fromisoformat(week_end) - date.fromisoformat(week_start)).days + 1
        revenue = sum(d["revenue"] for d in days)
        ingredients = sum(d["ingredient_cost"] for d in days)
        labor = labor_cost_for(week_start, week_end)
        fixed = fixed_total / days_in_month * length
        weeks.append({
            "start": week_start, "end": week_end, "revenue": revenue, "ingredients": ingredients,
            "labor": labor, "fixed": fixed, "profit": revenue - ingredients - labor - fixed,
        })

    revenue = sum(d["revenue"] for d in daily_sales)
    ingredients = sum(d["ingredient_cost"] for d in daily_sales)
    labor = labor_cost_for(start, end) if start else 0.0
    gross_profit = revenue - ingredients
    net_profit = gross_profit - labor - fixed_total

    def share(amount):
        return amount / revenue * 100 if revenue else 0.0

    return {
        "revenue": revenue,
        "ingredients": ingredients,
        "gross_profit": gross_profit,
        "labor": labor,
        "fixed": fixed_total,
        "net_profit": net_profit,
        "ingredients_pct": share(ingredients),
        "labor_pct": share(labor),
        "fixed_pct": share(fixed_total),
        "net_margin_pct": share(net_profit),
        "weeks": weeks,
    }