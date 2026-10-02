"""Business logic of the personnel domain. Only calculations, no SQL."""
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from domains.personnel import repository

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weekday(day):
    """'2026-09-04' -> 4 (Friday). Monday is 0."""
    return date.fromisoformat(day).weekday()


def average_demand(covers_by_hour, open_days):
    """Average diners for each (weekday, hour), e.g. {(4, 21): 49.5}.

    Each total is divided by how many times that weekday appears in the period,
    so a Friday is only compared with other Fridays.
    """
    days_per_weekday = Counter(_weekday(day) for day in open_days)
    totals = defaultdict(float)
    for row in covers_by_hour:
        totals[(_weekday(row["day"]), row["hour"])] += row["covers"]
    return {slot: total / days_per_weekday[slot[0]] for slot, total in totals.items()}


def average_staff_on_shift(shifts, open_days):
    """Average number of people of each role working at each (weekday, hour).

    A person counts for an hour if their shift overlaps any part of it,
    e.g. a 19:05-00:10 shift counts for 19h, 20h, 21h, 22h, 23h and 0h.
    """
    days_per_weekday = Counter(_weekday(day) for day in open_days)
    totals = defaultdict(int)
    for shift in shifts:
        start = datetime.fromisoformat(shift["clock_in"])
        end = datetime.fromisoformat(shift["clock_out"])
        hour = start.replace(minute=0, second=0, microsecond=0)
        while hour < end:
            totals[(hour.weekday(), hour.hour, shift["role_id"])] += 1
            hour += timedelta(hours=1)
    return {
        slot: count / days_per_weekday[slot[0]]
        for slot, count in totals.items()
        if days_per_weekday[slot[0]]
    }


def staff_needed(covers, role):
    """People of a role needed to serve `covers` diners in one hour, never below the role's minimum."""
    return max(role["min_staff"], math.ceil(covers / role["covers_per_hour"]))


def staffing_status(gap):
    """'short' if at least half a person is missing on average, 'extra' if a whole person is spare, else 'ok'."""
    if gap >= 0.5:
        return "short"
    if gap <= -1:
        return "extra"
    return "ok"


def build_schedule(demand, staff, roles):
    """Recommended vs. actual staff for every opening hour, with the gap for each role.

    A positive gap means people are missing; a negative gap means there are more than needed.
    """
    schedule = []
    for (weekday, hour), covers in sorted(demand.items()):
        slot = {"weekday": weekday, "day_name": WEEKDAYS[weekday], "hour": hour, "covers": covers, "roles": []}
        for role in roles:
            needed = staff_needed(covers, role)
            actual = staff.get((weekday, hour, role["id"]), 0)
            slot["roles"].append({
                "role": role["name"],
                "needed": needed,
                "actual": actual,
                "gap": needed - actual,
                "status": staffing_status(needed - actual),
            })
        schedule.append(slot)
    return schedule



def schedule_summary(schedule):
    """Key figures for the schedule page: the busiest hour and how many role-slots are short or over-staffed."""
    if not schedule:
        return {"peak": None, "short": 0, "extra": 0, "most_missing_role": None}
    peak = max(schedule, key=lambda slot: slot["covers"])
    cells = [cell for slot in schedule for cell in slot["roles"]]
    missing = defaultdict(float)
    for cell in cells:
        if cell["status"] == "short":
            missing[cell["role"]] += cell["gap"]
    return {
        "peak": peak,
        "short": sum(1 for cell in cells if cell["status"] == "short"),
        "extra": sum(1 for cell in cells if cell["status"] == "extra"),
        "most_missing_role": max(missing, key=missing.get) if missing else None,
    }



# ---------- Payroll ----------

def hours_worked(clock_in, clock_out):
    """Hours between clock-in and clock-out, e.g. 19:05 -> 00:10 is 5.08 hours."""
    seconds = (datetime.fromisoformat(clock_out) - datetime.fromisoformat(clock_in)).total_seconds()
    return max(seconds, 0) / 3600


def calculate_payroll(shifts):
    """Hours and pay per employee: clocked hours x the hourly rate of their role, at a single rate.

    `shifts` is a list of dicts with: employee_id, employee, role, hourly_rate, clock_in, clock_out.
    """
    employees = {}
    for shift in shifts:
        person = employees.setdefault(shift["employee_id"], {
            "employee": shift["employee"],
            "role": shift["role"],
            "hourly_rate": shift["hourly_rate"],
            "shifts": 0,
            "hours": 0.0,
        })
        person["shifts"] += 1
        person["hours"] += hours_worked(shift["clock_in"], shift["clock_out"])
    for person in employees.values():
        person["pay"] = round(person["hours"] * person["hourly_rate"], 2)
    return list(employees.values())


def payroll_by_role(payroll):
    """Total hours and pay for each role, in the order the roles appear."""
    roles = {}
    for person in payroll:
        role = roles.setdefault(person["role"], {"role": person["role"], "people": 0, "hours": 0.0, "pay": 0.0})
        role["people"] += 1
        role["hours"] += person["hours"]
        role["pay"] += person["pay"]
    return list(roles.values())


def labor_cost(conn, start, end):
    """Total wage cost between two dates (inclusive).

    This is the ONLY function the sales domain may use from personnel: the seam between the two
    domains. In Assignment 2 it becomes an HTTP endpoint of the personnel service.
    """
    return round(sum(person["pay"] for person in calculate_payroll(repository.get_worked_shifts(conn, start, end))), 2)