"""Web pages of the personnel domain."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database import get_connection
from domains.personnel import repository
from domains.personnel.services import (
    WEEKDAYS,
    average_demand,
    average_staff_on_shift,
    build_schedule,
    schedule_summary,
)
from web import templates

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request):
    conn = get_connection()
    try:
        open_days = repository.get_open_days(conn)
        demand = average_demand(repository.get_covers_by_hour(conn), open_days)
        staff = average_staff_on_shift(repository.get_shifts(conn), open_days)
        roles = repository.get_roles(conn)
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