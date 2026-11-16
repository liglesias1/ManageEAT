def test_schedule_page_shows_heatmap_and_roles(client):
    response = client.get("/personnel/schedule")
    assert response.status_code == 200
    assert "Demand by day and hour" in response.text
    assert "Dishwasher" in response.text

def test_payroll_page_shows_employees_and_total(client):
    response = client.get("/personnel/payroll")
    assert response.status_code == 200
    assert "Lucía Martín" in response.text
    assert "Total labour cost" in response.text