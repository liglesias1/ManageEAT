"""Pydantic models for the staff data a manager sends: roles, employees and missed clock-ins.

They check each field on its own (lengths, ranges, a clock-out after its clock-in). The rules that need the
database (a unique role name, a role or employee of the same restaurant, no overlapping clock-ins) are in
services.py, as in the sales service.
"""
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# A shift longer than this is almost certainly a forgotten clock-out, not real work
MAX_SHIFT_HOURS = 16


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class RoleIn(BaseModel):
    """A job in the restaurant: what it pays, how many diners one person serves per hour, and the minimum staff."""

    name: str = Field(min_length=2, max_length=60)
    hourly_rate: float = Field(gt=0, le=200)
    covers_per_hour: int = Field(gt=0, le=500)
    min_staff: int = Field(ge=0, le=50)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    role_id: int

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class ClockInIn(BaseModel):
    """A shift the clock-in system missed, entered by hand, in the restaurant's local time."""

    employee_id: int
    clock_in: datetime
    clock_out: datetime

    @field_validator("clock_in", "clock_out")
    @classmethod
    def local_time(cls, value):
        """Clock-ins are stored in local time without a time zone, like the ones the clock-in system sends."""
        if value.tzinfo is not None:
            raise ValueError("use the restaurant's local time, without a time zone")
        return value

    @model_validator(mode="after")
    def a_real_shift(self):
        if self.clock_out <= self.clock_in:
            raise ValueError("the clock-out must be after the clock-in")
        if (self.clock_out - self.clock_in).total_seconds() > MAX_SHIFT_HOURS * 3600:
            raise ValueError(f"a shift cannot be longer than {MAX_SHIFT_HOURS} hours")
        return self



# ---------- What the API answers ----------
# Response models: FastAPI checks every answer against them and puts them in the OpenAPI document
# (openapi.yaml). The pages with many nested figures (schedule, summary) are documented as JSON objects.

class Problem(BaseModel):
    """The body of every 401, 404, 409 and business-rule 422 answer."""

    detail: str


class Created(BaseModel):
    id: int
    name: str


class RoleOut(BaseModel):
    id: int
    name: str
    hourly_rate: float
    covers_per_hour: int
    min_staff: int
    employees: int = Field(description="How many employees have this role (it can only be deleted at 0)")


class EmployeeOut(BaseModel):
    id: int
    name: str
    role_id: int
    role: str
    clock_ins: int = Field(description="How many clock-ins they have (they can only be deleted at 0)")


class ClockInOut(BaseModel):
    id: int
    employee_id: int
    hours: float


class PayrollRow(BaseModel):
    employee: str
    role: str
    hourly_rate: float
    shifts: int
    hours: float
    pay: float


class RolePay(BaseModel):
    role: str
    people: int
    hours: float
    pay: float


class PayrollOut(BaseModel):
    start: Optional[date] = Field(description="First day with clock-ins, or null if there are none")
    end: Optional[date]
    payroll: List[PayrollRow]
    by_role: List[RolePay]
    total_pay: float
    total_hours: float


class LaborCostOut(BaseModel):
    """What the sales service receives from GET /personnel/labor-cost (the seam, ADR-6)."""

    start: date
    end: date
    labor_cost: float = Field(description="Total wages of the restaurant's clock-ins in the period, in EUR")