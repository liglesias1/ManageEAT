"""Business logic of the personnel domain. Only calculations, no SQL."""
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