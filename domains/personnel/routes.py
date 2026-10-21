"""Web pages of the personnel domain, and the JSON endpoint the sales domain uses for wage costs."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from accounts.dependencies import current_restaurant
from database import get_connection
from domains.personnel import public, repository

from domains.personnel.services import (
    WEEKDAYS,
    average_demand,
    average_staff_on_shift,
    build_schedule,
    calculate_payroll,
    payroll_by_role,
    schedule_summary,
)

from web import templates

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request, restaurant_id: int = Depends(current_restaurant)):
    conn = get_connection()
    try:
        open_days = repository.get_open_days(conn, restaurant_id)
        demand = average_demand(repository.get_covers_by_hour(conn, restaurant_id), open_days)
        staff = average_staff_on_shift(repository.get_shifts(conn, restaurant_id), open_days)
        roles = repository.get_roles(conn, restaurant_id)
    finally:
        conn.close()

    schedule = build_schedule(demand, staff, roles)
    hours = sorted({hour for _, hour in demand})
    by_day = {day: [slot for slot in schedule if slot["day_name"] == day] for day in WEEKDAYS}
    max_covers = max(demand.values(), default=0)

    return templates.TemplateResponse(
        request,
        "personnel/schedule.html",
        {
            "hours": hours,
            "demand": demand,
            "max_covers": max_covers,
            "weekdays": WEEKDAYS,
            "by_day": by_day,
            "roles": [role["name"] for role in roles],
            "summary": schedule_summary(schedule),
        },
    )



@router.get("/payroll", response_class=HTMLResponse)
def payroll_page(request: Request, restaurant_id: int = Depends(current_restaurant)):
    conn = get_connection()
    try:
        start, end = repository.get_clock_in_period(conn, restaurant_id)
        shifts = repository.get_worked_shifts(conn, restaurant_id, start, end) if start else []
    finally:
        conn.close()

    payroll = calculate_payroll(shifts)
    by_role = payroll_by_role(payroll)
    return templates.TemplateResponse(
        request,
        "personnel/payroll.html",
        {
            "start": start,
            "end": end,
            "payroll": payroll,
            "by_role": by_role,
            "total_pay": sum(p["pay"] for p in payroll),
            "total_hours": sum(p["hours"] for p in payroll),
        },
    )


# ---------- The seam, as an API ----------

@router.get("/api/labor-cost")
def labor_cost_api(start: date, end: date, restaurant_id: int = Depends(current_restaurant)):
    """Total wage cost between two dates (inclusive), as JSON: what sales asks for in its profit and loss.

    Today sales calls public.labor_cost() directly; when personnel becomes its own service in Assignment 2,
    sales asks this endpoint instead (domains/sales/wages.py), and tests/test_seam.py checks both agree.
    """
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    cost = public.labor_cost(restaurant_id, start.isoformat(), end.isoformat())
    return {"start": start.isoformat(), "end": end.isoformat(), "labor_cost": cost}