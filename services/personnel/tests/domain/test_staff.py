"""Roles, employees and missed clock-ins through the real API: what each endpoint saves, and what it refuses.

The demo restaurant has 6 roles (ids 1-6: Waiter, Runner, Bar, Pass, Cook, Dishwasher) and 16 employees
(ids 1-16), all of them with clock-ins in September 2026.
"""
from datetime import date, timedelta

import pytest

from domain.routes import EMPLOYEE_HAS_CLOCK_INS, ROLE_HAS_STAFF

SOMMELIER = {"name": "Sommelier", "hourly_rate": 15, "covers_per_hour": 40, "min_staff": 0}
WAITER = {"name": "Waiter", "hourly_rate": 11.5, "covers_per_hour": 30, "min_staff": 1}
SHIFT = {"clock_in": "2026-09-10T12:00:00", "clock_out": "2026-09-10T16:00:00"}


def other_restaurant(visitor):
    """Registers a second restaurant and returns the headers of its manager."""
    response = visitor.post("/auth/register", json={"restaurant_name": "Bar Pepe", "name": "Pepe",
                                                    "email": "pepe@barpepe.es", "password": "tortilla99"})
    return {"Authorization": f"Bearer {response.json()['token']}"}


def roles(client):
    return {role["name"]: role for role in client.get("/personnel/roles").json()}


def employees(client):
    return {person["name"]: person for person in client.get("/personnel/employees").json()}


def payroll(client):
    return {row["employee"]: row for row in client.get("/personnel/payroll").json()["payroll"]}


def new_employee(client, name="Ana Ruiz", role_id=1):
    response = client.post("/personnel/employees", json={"name": name, "role_id": role_id})
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.parametrize("method, path", [
    ("GET", "/personnel/roles"), ("POST", "/personnel/roles"), ("PUT", "/personnel/roles/1"),
    ("DELETE", "/personnel/roles/1"), ("GET", "/personnel/employees"), ("POST", "/personnel/employees"),
    ("PUT", "/personnel/employees/1"), ("DELETE", "/personnel/employees/1"), ("POST", "/personnel/clock-ins"),
])
def test_every_staff_endpoint_needs_a_token(visitor, method, path):
    assert visitor.request(method, path).status_code == 401


# ---------- Roles ----------

def test_roles_are_listed_with_how_many_employees_have_them(client):
    listed = roles(client)
    assert list(listed) == ["Waiter", "Runner", "Bar", "Pass", "Cook", "Dishwasher"]
    assert listed["Waiter"]["employees"] == 4 and listed["Dishwasher"]["employees"] == 2
    assert listed["Waiter"]["hourly_rate"] == 11.5


def test_a_new_role_is_saved_and_used_by_the_schedule(client):
    response = client.post("/personnel/roles", json=SOMMELIER)
    assert response.status_code == 201
    assert roles(client)["Sommelier"]["employees"] == 0
    assert "Sommelier" in client.get("/personnel/schedule").json()["roles"]


def test_a_role_name_cannot_repeat_and_nothing_is_saved(client):
    response = client.post("/personnel/roles", json={**SOMMELIER, "name": "waiter"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Name: there is already a role with that name"
    assert len(roles(client)) == 6


@pytest.mark.parametrize("change", [{"name": "X"}, {"hourly_rate": 0}, {"covers_per_hour": 0}, {"min_staff": -1}])
def test_a_role_with_a_wrong_field_is_rejected(client, change):
    assert client.post("/personnel/roles", json={**SOMMELIER, **change}).status_code == 422
    assert len(roles(client)) == 6


def test_a_new_hourly_rate_changes_the_pay_of_that_role(client):
    response = client.put("/personnel/roles/1", json={**WAITER, "hourly_rate": 20})
    assert response.status_code == 200
    lucia = payroll(client)["Lucía Martín"]                             # a waiter
    assert lucia["hourly_rate"] == 20
    assert lucia["pay"] == round(lucia["hours"] * 20, 2)


def test_a_role_keeps_its_own_name_but_cannot_take_another_ones(client):
    assert client.put("/personnel/roles/1", json=WAITER).status_code == 200
    taken = client.put("/personnel/roles/1", json={**WAITER, "name": "Cook"})
    assert taken.status_code == 422
    assert roles(client)["Waiter"]["id"] == 1


def test_a_role_with_employees_cannot_be_deleted(client):
    response = client.delete("/personnel/roles/1")
    assert response.status_code == 409
    assert response.json()["detail"] == ROLE_HAS_STAFF
    assert "Waiter" in roles(client)


def test_a_role_created_by_mistake_can_be_deleted(client):
    role_id = client.post("/personnel/roles", json=SOMMELIER).json()["id"]
    assert client.delete(f"/personnel/roles/{role_id}").status_code == 204
    assert "Sommelier" not in roles(client)


def test_unknown_roles_are_not_found(client):
    assert client.put("/personnel/roles/999", json=SOMMELIER).status_code == 404
    assert client.delete("/personnel/roles/999").status_code == 404


def test_a_manager_cannot_change_another_restaurants_roles(client):
    pepe = other_restaurant(client)
    assert client.put("/personnel/roles/1", json=SOMMELIER, headers=pepe).status_code == 404
    assert client.delete("/personnel/roles/1", headers=pepe).status_code == 404
    assert client.get("/personnel/roles", headers=pepe).json() == []
    assert roles(client)["Waiter"]["hourly_rate"] == 11.5


# ---------- Employees ----------

def test_employees_are_listed_with_their_role_and_clock_ins(client):
    listed = employees(client)
    assert len(listed) == 16
    assert listed["Lucía Martín"]["role"] == "Waiter"
    assert all(person["clock_ins"] > 0 for person in listed.values())


def test_a_new_employee_is_saved_without_clock_ins(client):
    employee_id = new_employee(client)
    ana = employees(client)["Ana Ruiz"]
    assert (ana["id"], ana["role"], ana["clock_ins"]) == (employee_id, "Waiter", 0)
    assert roles(client)["Waiter"]["employees"] == 5
    assert "Ana Ruiz" not in payroll(client)                            # no shifts yet, so no pay


def test_an_employee_needs_a_role_of_their_own_restaurant(client):
    pepe = other_restaurant(client)
    peps_role = client.post("/personnel/roles", json=SOMMELIER, headers=pepe).json()["id"]
    for role_id in (999, peps_role):
        response = client.post("/personnel/employees", json={"name": "Ana Ruiz", "role_id": role_id})
        assert response.status_code == 422
        assert response.json()["detail"] == "Role: choose one of the roles"
    assert len(employees(client)) == 16


def test_an_employee_needs_a_real_name(client):
    assert client.post("/personnel/employees", json={"name": "A", "role_id": 1}).status_code == 422


def test_changing_an_employees_role_moves_their_pay_to_that_role(client):
    response = client.put("/personnel/employees/1", json={"name": "Lucía Martín", "role_id": 3})
    assert response.status_code == 200
    assert employees(client)["Lucía Martín"]["role"] == "Bar"
    assert payroll(client)["Lucía Martín"]["role"] == "Bar"


def test_editing_an_employee_checks_the_role_too(client):
    response = client.put("/personnel/employees/1", json={"name": "Lucía Martín", "role_id": 999})
    assert response.status_code == 422
    assert employees(client)["Lucía Martín"]["role"] == "Waiter"


def test_an_employee_with_clock_ins_cannot_be_deleted(client):
    response = client.delete("/personnel/employees/1")
    assert response.status_code == 409
    assert response.json()["detail"] == EMPLOYEE_HAS_CLOCK_INS
    assert "Lucía Martín" in employees(client)


def test_an_employee_who_never_started_can_be_deleted(client):
    employee_id = new_employee(client)
    assert client.delete(f"/personnel/employees/{employee_id}").status_code == 204
    assert "Ana Ruiz" not in employees(client)


def test_unknown_employees_are_not_found(client):
    assert client.put("/personnel/employees/999", json={"name": "Ana Ruiz", "role_id": 1}).status_code == 404
    assert client.delete("/personnel/employees/999").status_code == 404


def test_a_manager_cannot_change_another_restaurants_employees(client):
    pepe = other_restaurant(client)
    assert client.put("/personnel/employees/1", json={"name": "X Y", "role_id": 1}, headers=pepe).status_code == 404
    assert client.delete("/personnel/employees/1", headers=pepe).status_code == 404
    assert "Lucía Martín" in employees(client)


# ---------- Missed clock-ins ----------

def test_a_missed_shift_counts_in_payroll_and_labor_cost_at_once(client):
    period = {"start": "2026-09-01", "end": "2026-09-30"}
    before = client.get("/personnel/labor-cost", params=period).json()["labor_cost"]
    employee_id = new_employee(client)                                  # a waiter: 11.50 per hour

    response = client.post("/personnel/clock-ins", json={"employee_id": employee_id, **SHIFT})
    assert response.status_code == 201
    assert response.json()["hours"] == 4.0
    assert payroll(client)["Ana Ruiz"]["pay"] == 46.0
    assert client.get("/personnel/labor-cost", params=period).json()["labor_cost"] == round(before + 46.0, 2)


def test_once_they_have_a_clock_in_an_employee_cannot_be_deleted(client):
    employee_id = new_employee(client)
    client.post("/personnel/clock-ins", json={"employee_id": employee_id, **SHIFT})
    assert client.delete(f"/personnel/employees/{employee_id}").status_code == 409


def test_overlapping_shifts_are_refused_but_back_to_back_ones_are_fine(client):
    employee_id = new_employee(client)
    client.post("/personnel/clock-ins", json={"employee_id": employee_id, **SHIFT})        # 12:00-16:00

    overlap = client.post("/personnel/clock-ins", json={
        "employee_id": employee_id, "clock_in": "2026-09-10T15:00:00", "clock_out": "2026-09-10T18:00:00"})
    assert overlap.status_code == 422
    assert overlap.json()["detail"] == "This employee already has a clock-in that overlaps these hours"

    after = client.post("/personnel/clock-ins", json={
        "employee_id": employee_id, "clock_in": "2026-09-10T16:00:00", "clock_out": "2026-09-10T18:00:00"})
    assert after.status_code == 201
    assert employees(client)["Ana Ruiz"]["clock_ins"] == 2


def test_a_shift_on_a_future_day_is_refused(client):
    employee_id = new_employee(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = client.post("/personnel/clock-ins", json={
        "employee_id": employee_id, "clock_in": f"{tomorrow}T12:00:00", "clock_out": f"{tomorrow}T16:00:00"})
    assert response.status_code == 422
    assert response.json()["detail"] == "A clock-in cannot be on a future day"
    assert employees(client)["Ana Ruiz"]["clock_ins"] == 0


@pytest.mark.parametrize("times", [
    {"clock_in": "2026-09-10T16:00:00", "clock_out": "2026-09-10T12:00:00"},   # ends before it starts
    {"clock_in": "2026-09-10T08:00:00", "clock_out": "2026-09-11T08:00:00"},   # 24 hours
    {"clock_in": "2026-09-10T12:00:00Z", "clock_out": "2026-09-10T16:00:00Z"},  # with a time zone
    {"clock_in": "yesterday", "clock_out": "2026-09-10T16:00:00"},
])
def test_wrong_times_are_rejected_and_nothing_is_saved(client, times):
    employee_id = new_employee(client)
    assert client.post("/personnel/clock-ins", json={"employee_id": employee_id, **times}).status_code == 422
    assert employees(client)["Ana Ruiz"]["clock_ins"] == 0


def test_a_clock_in_needs_an_employee_of_the_restaurant(client):
    pepe = other_restaurant(client)
    response = client.post("/personnel/clock-ins", json={"employee_id": 1, **SHIFT}, headers=pepe)
    assert response.status_code == 422
    assert response.json()["detail"] == "Employee: choose one of the employees"