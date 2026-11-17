"""Personnel API: the staffing schedule, payroll, the wage cost that sales asks for, and the overview figures.

The schedule is the flow of personnel that crosses the seam: it needs the covers per hour, which come
from the sales service (domain/demand.py). Payroll and labor cost only use personnel's own data, so they
keep working whatever happens to sales.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from accounts.dependencies import bearer, current_restaurant
from database import get_db
from domain import repository, services
from domain.demand import Demand, sales_client   # the only way personnel gets numbers from sales (ADR-6)

router = APIRouter(prefix="/personnel", tags=["personnel"])


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


@router.get("/schedule")
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


@router.get("/payroll")
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


@router.get("/summary")
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

@router.get("/labor-cost")
def labor_cost(start: date, end: date, conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """Total wage cost between two dates (inclusive), for the profit and loss of the sales service.

    Sales forwards the manager's token, so the restaurant is the one of the manager who asked.
    """
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    cost = services.labor_cost(conn, restaurant_id, start.isoformat(), end.isoformat())
    return {"start": start.isoformat(), "end": end.isoformat(), "labor_cost": cost}