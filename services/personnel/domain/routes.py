"""Personnel API: roles, employees and missed clock-ins, the staffing schedule, payroll, the wage cost that
sales asks for, and the overview figures.

The schedule is the flow of personnel that crosses the seam: it needs the covers per hour, which come
from the sales service (domain/demand.py). Payroll and labor cost only use personnel's own data, so they
keep working whatever happens to sales.

Each route only does the web part: read the request, ask the repository for data, let services.py decide,
and answer with JSON. Invalid fields get FastAPI's 422; a broken business rule gets 422 with
{"detail": "<message>"}; something that does not exist in the manager's restaurant gets 404; a delete that
would erase history gets 409. Nothing is written when the answer is an error.
"""
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response

from accounts.dependencies import bearer, current_restaurant
from database import get_db
from domain import repository, services
from domain.demand import Demand, sales_client   # the only way personnel gets numbers from sales (ADR-6)
from domain.schemas import (ClockInIn, ClockInOut, Created, EmployeeIn, EmployeeOut, LaborCostOut, PayrollOut, Problem,
                            RoleIn, RoleOut)

router = APIRouter(prefix="/personnel", tags=["personnel"],
                   responses={401: {"model": Problem, "description": "Missing, invalid or expired token"}})
NOT_FOUND = {404: {"model": Problem, "description": "Not found in the manager's restaurant"}}

ROLE_HAS_STAFF = "This role still has employees: give them another role before deleting it"
EMPLOYEE_HAS_CLOCK_INS = ("This employee has clock-ins, which payroll and the schedule are calculated from, "
                          "so they cannot be deleted")


def _problem(message):
    return HTTPException(status_code=422, detail=message)


def _not_found(what):
    return HTTPException(status_code=404, detail=f"{what} not found")


def _role_ids(conn, restaurant_id):
    return {role["id"] for role in repository.get_roles(conn, restaurant_id)}


# ---------- Roles ----------

@router.get("/roles", response_model=List[RoleOut])
def list_roles(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Every role, with how many employees have it."""
    return repository.get_roles_with_staff(conn, restaurant_id)


@router.post("/roles", status_code=201, response_model=Created)
def create_role(role: RoleIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    problem = services.role_problem(role, [r["name"] for r in repository.get_roles(conn, restaurant_id)])
    if problem:
        raise _problem(problem)
    role_id = repository.add_role(conn, restaurant_id, role.name, role.hourly_rate, role.covers_per_hour,
                                  role.min_staff)
    return {"id": role_id, "name": role.name}


@router.put("/roles/{role_id}", response_model=Created, responses=NOT_FOUND)
def update_role(role_id: int, role: RoleIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Changes a role. Payroll always uses the role's current hourly rate, so a new rate also changes past pay."""
    if repository.get_role(conn, restaurant_id, role_id) is None:
        raise _not_found("Role")
    others = [r["name"] for r in repository.get_roles(conn, restaurant_id) if r["id"] != role_id]
    problem = services.role_problem(role, others)
    if problem:
        raise _problem(problem)
    repository.update_role(conn, restaurant_id, role_id, role.name, role.hourly_rate, role.covers_per_hour,
                           role.min_staff)
    return {"id": role_id, "name": role.name}


@router.delete("/roles/{role_id}", status_code=204, response_class=Response,
                responses={**NOT_FOUND, 409: {"model": Problem, "description": "The role still has employees"}})
def delete_role(role_id: int, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Deletes a role created by mistake; 409 if any employee still has it."""
    if repository.get_role(conn, restaurant_id, role_id) is None:
        raise _not_found("Role")
    if not repository.delete_role_without_staff(conn, restaurant_id, role_id):
        raise HTTPException(status_code=409, detail=ROLE_HAS_STAFF)
    return Response(status_code=204)


# ---------- Employees ----------

@router.get("/employees", response_model=List[EmployeeOut])
def list_employees(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Every employee with their role and how many clock-ins they have."""
    return repository.get_employees(conn, restaurant_id)


@router.post("/employees", status_code=201, response_model=Created)
def create_employee(employee: EmployeeIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    problem = services.employee_problem(employee, _role_ids(conn, restaurant_id))
    if problem:
        raise _problem(problem)
    employee_id = repository.add_employee(conn, restaurant_id, employee.name, employee.role_id)
    return {"id": employee_id, "name": employee.name}


@router.put("/employees/{employee_id}", response_model=Created, responses=NOT_FOUND)
def update_employee(employee_id: int, employee: EmployeeIn, conn=Depends(get_db),
                    restaurant_id: int = Depends(current_restaurant)):
    """Changes an employee's name or role (a role change also changes the rate of their past shifts)."""
    if repository.get_employee(conn, restaurant_id, employee_id) is None:
        raise _not_found("Employee")
    problem = services.employee_problem(employee, _role_ids(conn, restaurant_id))
    if problem:
        raise _problem(problem)
    repository.update_employee(conn, restaurant_id, employee_id, employee.name, employee.role_id)
    return {"id": employee_id, "name": employee.name}


@router.delete("/employees/{employee_id}", status_code=204, response_class=Response,
                responses={**NOT_FOUND, 409: {"model": Problem, "description": "The employee has clock-ins"}})
def delete_employee(employee_id: int, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Deletes an employee created by mistake (e.g. someone who never started); 409 if they have clock-ins."""
    if repository.get_employee(conn, restaurant_id, employee_id) is None:
        raise _not_found("Employee")
    if not repository.delete_employee_without_clock_ins(conn, restaurant_id, employee_id):
        raise HTTPException(status_code=409, detail=EMPLOYEE_HAS_CLOCK_INS)
    return Response(status_code=204)


# ---------- Clock-ins the clock-in system missed ----------

@router.post("/clock-ins", status_code=201, response_model=ClockInOut)
def record_clock_in(entry: ClockInIn, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Records by hand a shift the clock-in system missed. It counts in payroll and the schedule at once."""
    employee_ids = {e["id"] for e in repository.get_employees(conn, restaurant_id)}
    overlaps = entry.employee_id in employee_ids and repository.has_overlapping_clock_in(
        conn, restaurant_id, entry.employee_id, entry.clock_in, entry.clock_out)
    problem = services.clock_in_problem(entry, employee_ids, overlaps, date.today())
    if problem:
        raise _problem(problem)
    clock_in_id = repository.add_clock_in(conn, restaurant_id, entry.employee_id, entry.clock_in, entry.clock_out)
    hours = services.hours_worked(entry.clock_in.isoformat(), entry.clock_out.isoformat())
    return {"id": clock_in_id, "employee_id": entry.employee_id, "hours": round(hours, 2)}


# ---------- Schedule, payroll and overview ----------

def _demand(client=Depends(sales_client), credentials=Depends(bearer), conn=Depends(get_db),
            restaurant_id: int = Depends(current_restaurant)):
    """current_restaurant has already checked the token, so it can be forwarded to sales as it came."""
    return Demand(client, credentials.credentials, conn, restaurant_id)


def _schedule(conn, restaurant_id, demand):
    """(average covers per weekday and hour, recommended vs actual staff per slot, roles), or Nones without demand."""
    roles = repository.get_roles(conn, restaurant_id)
    data = demand.get()
    if data is None:
        return None, None, roles
    covers = services.average_demand(data["covers"], data["open_days"])
    staff = services.average_staff_on_shift(repository.get_shifts(conn, restaurant_id), data["open_days"])
    return covers, services.build_schedule(covers, staff, roles), roles


@router.get("/schedule", response_model=dict)
def schedule(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant), demand: Demand = Depends(_demand)):
    """Recommended against actual staff for every opening hour, and the average covers that drive it.

    Covers come from sales. If it does not answer, the last covers received are used and `demand` says from
    when; if there are none, `demand` is unavailable and the schedule is empty, but the roles are listed.
    """
    covers, slots, roles = _schedule(conn, restaurant_id, demand)
    heatmap = [
        {"weekday": weekday, "day_name": services.WEEKDAYS[weekday], "hour": hour, "covers": value}
        for (weekday, hour), value in sorted((covers or {}).items())
    ]
    return {
        "demand": demand.report(),
        "weekdays": services.WEEKDAYS,
        "hours": sorted({row["hour"] for row in heatmap}),
        "heatmap": heatmap,
        "max_covers": max((row["covers"] for row in heatmap), default=0),
        "roles": [role["name"] for role in roles],
        "by_day": {day: [slot for slot in slots or [] if slot["day_name"] == day] for day in services.WEEKDAYS},
        "summary": services.schedule_summary(slots) if slots is not None else None,
    }


def _payroll(conn, restaurant_id):
    """Payroll of the whole period with clock-ins: (start, end, one row per employee)."""
    start, end = repository.get_clock_in_period(conn, restaurant_id)
    shifts = repository.get_worked_shifts(conn, restaurant_id, start, end) if start else []
    return start, end, services.calculate_payroll(shifts)


@router.get("/payroll", response_model=PayrollOut)
def payroll(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Hours and pay of every employee, and the totals per role, over the period with clock-ins."""
    start, end, rows = _payroll(conn, restaurant_id)
    return {
        "start": start,
        "end": end,
        "payroll": rows,
        "by_role": services.payroll_by_role(rows),
        "total_pay": round(sum(p["pay"] for p in rows), 2),
        "total_hours": round(sum(p["hours"] for p in rows), 2),
    }


@router.get("/summary", response_model=dict)
def summary(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant), demand: Demand = Depends(_demand)):
    """The personnel figures of the overview page: schedule gaps, employees paid, hours worked and wages."""
    _, slots, _ = _schedule(conn, restaurant_id, demand)
    _, _, rows = _payroll(conn, restaurant_id)
    return {
        "demand": demand.report(),
        "schedule": services.schedule_summary(slots) if slots is not None else None,
        "employees": len(rows),
        "hours": round(sum(p["hours"] for p in rows), 2),
        "wages": round(sum(p["pay"] for p in rows), 2),
    }


# ---------- The seam: what the sales service calls ----------

@router.get("/labor-cost", response_model=LaborCostOut)
def labor_cost(start: date, end: date, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Total wage cost between two dates (inclusive), for the profit and loss of the sales service.

    Sales forwards the manager's token, so the restaurant is the one of the manager who asked.
    """
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    shifts = repository.get_worked_shifts(conn, restaurant_id, start.isoformat(), end.isoformat())
    cost = services.labor_cost(shifts)
    return {"start": start.isoformat(), "end": end.isoformat(), "labor_cost": cost}