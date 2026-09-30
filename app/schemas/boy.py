from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GenderEnum
from app.schemas.base import ORMResponse


class BoyCreate(BaseModel):
    """Core boy record. ``age`` is derived from ``birth_date`` - never sent."""

    boy_name: str = Field(..., min_length=1, max_length=255)
    gender: GenderEnum
    class_id: int = Field(..., description="His current class - FK classes.id")
    birth_date: date | None = None
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    zone: str | None = Field(None, max_length=255)
    address: str | None = None
    location: str | None = Field(None, max_length=500)
    note: str | None = None
    issue_flag: bool = False

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value


class BoyUpdate(BaseModel):
    """Partial update - all fields optional. ``age`` is never accepted."""

    boy_name: str | None = Field(None, min_length=1, max_length=255)
    gender: GenderEnum | None = None
    class_id: int | None = None
    birth_date: date | None = None
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    zone: str | None = Field(None, max_length=255)
    address: str | None = None
    location: str | None = Field(None, max_length=500)
    note: str | None = None
    issue_flag: bool | None = None

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value


class BoyResponse(ORMResponse):
    id: int
    boy_name: str
    gender: GenderEnum
    class_id: int
    birth_date: date | None = None
    age: int | None = None  # filled from the Boy.age property
    phone: str | None = None
    phone_2: str | None = None
    zone: str | None = None
    address: str | None = None
    location: str | None = None
    note: str | None = None
    issue_flag: bool = False
    created_at: datetime
    updated_at: datetime | None = None
