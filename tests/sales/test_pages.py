def test_menu_page_shows_dishes_and_classes(client):
    response = client.get("/sales/menu")
    assert response.status_code == 200
    assert "Valencian paella" in response.text
    assert "Plowhorse" in response.text


def test_home_redirects_to_menu_page(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/sales/menu"


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok"}