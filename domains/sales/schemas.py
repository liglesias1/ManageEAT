"""Pydantic models for the data entering and leaving the sales domain."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SupplierIn(BaseModel):
    """A new supplier sent from the inventory form."""

    name: str = Field(min_length=2, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=120)
    lead_time_days: int = Field(ge=0, le=60)
    ingredient_ids: List[int] = []

    @field_validator("name", "phone", "email", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        """Empty form fields arrive as '' and are treated as missing."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def looks_like_email(cls, value):
        if value is not None and ("@" not in value or "." not in value.split("@")[-1]):
            raise ValueError("enter a valid email address")
        return value

    @model_validator(mode="after")
    def needs_a_contact(self):
        """Same rule as the CHECK constraint in the database: a supplier must be reachable."""
        if not self.phone and not self.email:
            raise ValueError("add a phone number or an email")
        return self


class PurchaseIn(BaseModel):
    """A delivery recorded from a supplier's page."""

    ingredient_id: int
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    received_on: date