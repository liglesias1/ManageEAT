"""Pydantic models for the account forms: register a restaurant, log in, add a manager."""
from pydantic import BaseModel, Field, field_validator

MIN_PASSWORD_LENGTH = 8


def _clean(value):
    return value.strip() if isinstance(value, str) else value


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value):
        return _clean(value)


class ManagerIn(BaseModel):
    """A manager's own login: name, email and password (used when registering and when adding a manager)."""

    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @field_validator("name", "email", mode="before")
    @classmethod
    def strip(cls, value):
        return _clean(value)

    @field_validator("email")
    @classmethod
    def looks_like_email(cls, value):
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("enter a valid email address")
        return value.lower()


class RegisterIn(ManagerIn):
    """A new restaurant and the manager who creates it."""

    restaurant_name: str = Field(min_length=2, max_length=80)

    @field_validator("restaurant_name", mode="before")
    @classmethod
    def strip_restaurant(cls, value):
        return _clean(value)

# ---------- What the API answers ----------

class ManagerOut(BaseModel):
    id: int
    name: str
    email: str


class RestaurantOut(BaseModel):
    id: int
    name: str


class SessionOut(BaseModel):
    """Answer to login, register and refresh: the token the UI sends with every request, and who it belongs to."""

    token: str
    expires_in: int = Field(description="Seconds until the token expires")
    user: ManagerOut
    restaurant: RestaurantOut