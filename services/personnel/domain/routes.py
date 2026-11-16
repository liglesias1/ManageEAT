"""Personnel API: payroll, the wage cost that sales asks for, and the figures of the overview.

The schedule is not here yet: it needs the covers per hour, which come from the sales service, so its
endpoint is added together with that call (ADR-6).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from accounts.dependencies import current_restaurant
from database import get_db
from domain import repository, services

router = APIRouter(prefix="/personnel", tags=["personnel"])


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
def summary(conn=Depends(get_db), restaurant_id: int = Depends(current_restaurant)):
    """The personnel figures of the overview page: employees paid, hours worked and wages."""
    _, _, rows = _payroll(conn, restaurant_id)
    return {
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