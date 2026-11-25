"""Business logic of the personnel domain: calculations and business rules, no SQL.

The routes read the data with repository.py and hand it to these functions, so every function here can be
tested with plain lists and dicts, without a database.
"""
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

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


def labor_cost(shifts):
    """Total wage cost of the given shifts (the worked shifts of one restaurant between two dates).

    This is what the sales service asks for over HTTP (GET /personnel/labor-cost): the seam between the two
    services. The route reads the shifts of the period; this function only adds up their pay.
    """
    return round(sum(person["pay"] for person in calculate_payroll(shifts)), 2)


# ---------- Business rules for the staff a manager edits ----------
# Each function returns why the data cannot be saved (the message the manager sees, with 422), or None.

def name_taken(name, names):
    """True if `name` is already in `names`, ignoring upper and lower case: 'waiter' clashes with 'Waiter'."""
    return name.lower() in {n.lower() for n in names}


def role_problem(role, other_role_names):
    """`other_role_names` leaves out the role being edited, so it can keep its own name."""
    if name_taken(role.name, other_role_names):
        return "Name: there is already a role with that name"
    return None


def employee_problem(employee, role_ids):
    """An employee can only have one of their own restaurant's roles."""
    if employee.role_id not in role_ids:
        return "Role: choose one of the roles"
    return None


def clock_in_problem(entry, employee_ids, overlaps, today):
    """Why a missed shift cannot be recorded, or None.

    The employee must belong to the restaurant, the shift cannot start on a future day, and it cannot
    overlap another clock-in of the same person (that would pay the same hours twice). `today` is passed
    in, not read here, so the rule can be tested with any date.
    """
    if entry.employee_id not in employee_ids:
        return "Employee: choose one of the employees"
    if entry.clock_in.date() > today:
        return "A clock-in cannot be on a future day"
    if overlaps:
        return "This employee already has a clock-in that overlaps these hours"
    return None
