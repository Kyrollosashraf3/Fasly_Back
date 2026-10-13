from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import FatherEnum, GenderEnum
from app.schemas.base import ORMResponse
from app.schemas.user import normalise_phone


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
    father_name: FatherEnum | None = None
    national_id: str | None = Field(None, max_length=20)
    # Free text too - when «أخرى» is picked, the typed skill lives in here.
    skills: list[str] | None = None
    last_visit_date: date | None = Field(
        None, description="Last confession/visit for this boy - nullable"
    )
    note: str | None = None
    issue_flag: bool = False
    teacher_id: int | None = Field(
        None,
        description=(
            "Servant to file him under straight away - creates the "
            "groups row, so that servant can already take his attendance"
        ),
    )

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, value):
        """Accept a bare value too (old clients / Excel) - always a list."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str) and not value.strip():
            return None
        return [value]

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value

    @field_validator("last_visit_date")
    @classmethod
    def _visit_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last_visit_date cannot be in the future")
        return value

    @field_validator("phone", "phone_2", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        """Store every phone shape as ``01xxxxxxxxx`` (see ``common``)."""
        return normalise_phone(value)


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
    father_name: FatherEnum | None = None
    national_id: str | None = Field(None, max_length=20)
    # Free text too - when «أخرى» is picked, the typed skill lives in here.
    skills: list[str] | None = None
    last_visit_date: date | None = Field(
        None, description="Last confession/visit for this boy - nullable"
    )
    note: str | None = None
    issue_flag: bool | None = None
    # ``null`` = drop him from his current group; absent = leave it alone.
    teacher_id: int | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, value):
        """Accept a bare value too (old clients / Excel) - always a list."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str) and not value.strip():
            return None
        return [value]

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value

    @field_validator("last_visit_date")
    @classmethod
    def _visit_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last_visit_date cannot be in the future")
        return value

    @field_validator("phone", "phone_2", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        """Store every phone shape as ``01xxxxxxxxx`` (see ``common``)."""
        return normalise_phone(value)


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
    father_name: FatherEnum | None = None
    national_id: str | None = None
    skills: list[str] | None = None
    last_visit_date: date | None = None
    note: str | None = None
    issue_flag: bool = False
    teacher_id: int | None = None
    teacher_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
