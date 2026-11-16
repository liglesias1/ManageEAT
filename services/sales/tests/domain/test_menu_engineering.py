from domains.sales.services import classify_menu, menu_summary


def dish(code, units, revenue, cost, category="main"):
    return {"code": code, "name": code, "category": category,
            "units_sold": units, "revenue": revenue, "unit_cost": cost}


def by_code(result):
    return {d["code"]: d for d in result}


def test_each_quadrant_is_detected():
    # 220 units in total -> popular from 38.5 units; average margin 2130 / 220 = 9.68
    result = by_code(classify_menu([
        dish("A", 100, 2000, 5),   # price 20, margin 15 -> popular and profitable
        dish("B", 100, 1000, 6),   # price 10, margin 4  -> popular, low margin
        dish("C", 10, 250, 5),     # price 25, margin 20 -> rare, high margin
        dish("D", 10, 100, 7),     # price 10, margin 3  -> rare, low margin
    ]))
    assert result["A"]["class"] == "star"
    assert result["B"]["class"] == "plowhorse"
    assert result["C"]["class"] == "puzzle"
    assert result["D"]["class"] == "dog"


def test_margin_is_average_price_minus_ingredient_cost():
    result = classify_menu([dish("A", 4, 80, 6.5)])
    assert result[0]["avg_price"] == 20
    assert result[0]["margin"] == 13.5
    assert result[0]["total_margin"] == 54


def test_categories_are_compared_separately():
    # A cheap drink should not be a "dog" just because mains have bigger margins
    result = by_code(classify_menu([
        dish("MAIN", 50, 1000, 5),
        dish("WATER", 50, 125, 0.35, category="drink"),
    ]))
    assert result["MAIN"]["class"] == "star"
    assert result["WATER"]["class"] == "star"


def test_dish_without_sales_is_new_and_does_not_change_the_others():
    alone = by_code(classify_menu([dish("A", 10, 200, 5), dish("B", 30, 300, 5)]))
    with_new = by_code(classify_menu([dish("A", 10, 200, 5), dish("B", 30, 300, 5), dish("NEW", 0, 0, 4)]))
    assert with_new["NEW"]["class"] == "new"
    assert with_new["A"]["class"] == alone["A"]["class"]
    assert with_new["A"]["popularity_threshold"] == alone["A"]["popularity_threshold"]


def test_category_with_only_new_dishes_does_not_crash():
    result = classify_menu([dish("NEW", 0, 0, 4, category="dessert")])
    assert result[0]["class"] == "new"


def test_new_dishes_are_not_the_least_ordered():
    summary = menu_summary(classify_menu([dish("A", 10, 200, 5), dish("B", 30, 300, 5), dish("NEW", 0, 0, 4)]))
    assert summary["least_ordered"] == "A"
    assert summary["class_counts"]["new"] == 1


def test_every_dish_gets_a_recommendation():
    result = classify_menu([dish("A", 10, 200, 5), dish("B", 1, 10, 8)])
    assert all(d["recommendation"] for d in result)


def test_empty_menu_returns_empty_list():
    assert classify_menu([]) == []


def test_thresholds_are_attached_to_each_dish():
    result = by_code(classify_menu([dish("A", 30, 600, 5), dish("B", 10, 100, 5)]))
    # 40 units / 2 dishes * 0.7 = 14 units; average margin (450 + 50) / 40 = 12.5
    assert result["A"]["popularity_threshold"] == 14
    assert result["A"]["average_margin"] == 12.5


def test_menu_summary_totals_and_best_seller():
    dishes = classify_menu([
        dish("Paella", 10, 200, 5),
        dish("Risotto", 2, 30, 3),
        dish("Water", 50, 125, 0.5, category="drink"),
    ])
    summary = menu_summary(dishes)
    assert summary["revenue"] == 355
    assert summary["ingredient_cost"] == 81          # 10*5 + 2*3 + 50*0.5
    assert summary["gross_margin"] == 274
    assert round(summary["food_cost_pct"], 1) == 22.8
    # Drinks are ignored for best and least ordered, otherwise Water would always win
    assert summary["best_seller"] == "Paella"
    assert summary["least_ordered"] == "Risotto"
    assert sum(summary["class_counts"].values()) == 3


def test_menu_summary_with_no_sales():
    summary = menu_summary([])
    assert summary["revenue"] == 0
    assert summary["food_cost_pct"] == 0
    assert summary["best_seller"] is None