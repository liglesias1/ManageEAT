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
            result.append(dish)
    return result