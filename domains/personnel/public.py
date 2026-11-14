"""The public face of the personnel domain (Facade): the only functions the rest of the app may call.

Everything else in domains/personnel (repository, services, routes) is internal and can change freely.
Each function opens its own database connection, so callers never touch personnel's tables, and in
Assignment 2 each one can become an endpoint of the personnel service without changing its callers.
"""
from database import get_connection
from domains.personnel import repository, services


def labor_cost(restaurant_id, start, end):
    """Total wage cost of a restaurant between two dates (inclusive): the seam used by sales (ADR-2)."""
    conn = get_connection()
    try:
        return services.labor_cost(conn, restaurant_id, start, end)
    finally:
        conn.close()


def overview_figures(restaurant_id):
    """The personnel figures shown on the home page: schedule gaps, staff, hours and wages."""
    conn = get_connection()
    try:
        open_days = repository.get_open_days(conn, restaurant_id)
        demand = services.average_demand(repository.get_covers_by_hour(conn, restaurant_id), open_days)
        staff = services.average_staff_on_shift(repository.get_shifts(conn, restaurant_id), open_days)
        schedule = services.build_schedule(demand, staff, repository.get_roles(conn, restaurant_id))
        start, end = repository.get_clock_in_period(conn, restaurant_id)
        shifts = repository.get_worked_shifts(conn, restaurant_id, start, end) if start else []
    finally:
        conn.close()
    payroll = services.calculate_payroll(shifts)
    return {
        "schedule": services.schedule_summary(schedule),
        "employees": len(payroll),
        "hours": sum(p["hours"] for p in payroll),
        "wages": sum(p["pay"] for p in payroll),
    }