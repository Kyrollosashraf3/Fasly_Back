from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import FatherEnum
from app.schemas.base import ORMResponse


class TeacherCreate(BaseModel):
    """Register a servant. The login is created separately in ``users``.

    ``last_visit_date`` = last confession/visit by the father; NULL until the
    first visit is recorded.
    """

    teacher_name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    zone: str | None = Field(None, max_length=255)
    address: str | None = None
    location: str | None = Field(None, max_length=500)
    class_id: int = Field(..., description="His class - FK classes.id")
    father_name: FatherEnum | None = None
    # Free text too - when «أخرى» is picked, the typed skill lives in here.
    skills: list[str] | None = None
    last_visit_date: date | None = Field(
        None, description="Last confession/visit by the father - nullable"
    )
    note: str | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, value):
        """Accept a bare value too (old clients / Excel) - always a list."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str) and not value.strip():
            return None
        return [value]

    @field_validator("last_visit_date")
    @classmethod
    def _visit_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last_visit_date cannot be in the future")
        return value


class TeacherUpdate(BaseModel):
    """Partial update - all fields optional."""

    teacher_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    zone: str | None = Field(None, max_length=255)
    address: str | None = None
    location: str | None = Field(None, max_length=500)
    class_id: int | None = None
    father_name: FatherEnum | None = None
    # Free text too - when «أخرى» is picked, the typed skill lives in here.
    skills: list[str] | None = None
    last_visit_date: date | None = Field(
        None, description="Last confession/visit by the father - nullable"
    )
    note: str | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, value):
        """Accept a bare value too (old clients / Excel) - always a list."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str) and not value.strip():
            return None
        return [value]

    @field_validator("last_visit_date")
    @classmethod
    def _visit_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last_visit_date cannot be in the future")
        return value


class TeacherResponse(ORMResponse):
    id: int
    teacher_name: str
    phone: str | None = None
    phone_2: str | None = None
    zone: str | None = None
    address: str | None = None
    location: str | None = None
    class_id: int
    father_name: FatherEnum | None = None
    skills: list[str] | None = None
    last_visit_date: date | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
