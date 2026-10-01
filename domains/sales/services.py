'''Buisness logic of the sales domain, makes calculations, no queries to the database.'''

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