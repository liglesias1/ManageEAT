"""The home page brings together figures from both domains."""
from overview import attention_items


def test_home_page_is_the_overview(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Needs your attention" in response.text
    assert "Net profit" in response.text
    assert "Payroll" in response.text


def test_overview_matches_the_profit_and_loss_page(client):
    overview = client.get("/").text
    profit_loss = client.get("/sales/profit-loss").text
    assert "€82,495.55" in overview
    assert "€82,495.55" in profit_loss


def test_overview_lists_ingredients_to_reorder(client):
    assert "Ingredients to reorder: " in client.get("/").text


def figures(**changes):
    base = {"to_reorder": [], "schedule": {"most_missing_role": None}, "dogs": [], "pl": {"net_profit": 100}}
    return {**base, **changes}


def test_nothing_to_flag_gives_an_empty_list():
    assert attention_items(figures()) == []


def test_every_problem_links_to_the_page_where_to_fix_it():
    items = attention_items(figures(
        to_reorder=["Tomato"], schedule={"most_missing_role": "Cook"}, dogs=["Flan"], pl={"net_profit": -50},
    ))
    assert [i["link"] for i in items] == ["/sales/inventory", "/personnel/schedule", "/sales/menu", "/sales/profit-loss"]
    assert items[0]["text"] == "Ingredients to reorder: Tomato"