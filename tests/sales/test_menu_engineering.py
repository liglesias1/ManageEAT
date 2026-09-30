from domains.sales.services import classify_menu


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


def test_dish_without_sales_is_a_dog_and_does_not_crash():
    result = by_code(classify_menu([dish("A", 10, 200, 5), dish("NEW", 0, 0, 4)]))
    assert result["NEW"]["avg_price"] == 0
    assert result["NEW"]["class"] == "dog"


def test_every_dish_gets_a_recommendation():
    result = classify_menu([dish("A", 10, 200, 5), dish("B", 1, 10, 8)])
    assert all(d["recommendation"] for d in result)


def test_empty_menu_returns_empty_list():
    assert classify_menu([]) == []