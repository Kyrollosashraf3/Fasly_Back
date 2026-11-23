from datetime import date as DateType, datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class TeacherCheckCreate(BaseModel):
    """The amin's Friday review of one servant.

    The four flags are required: an empty body must not silently read as
    "nothing was done". ``class_id`` and ``recorded_by`` are server-stamped
    (``class_id`` = the servant's class on ``date``).
    """

    teacher_id: int
    attend: bool = Field(..., description="Did he take the attendance?")
    prepare: bool = Field(..., description="Did he prepare the lesson?")
    liturgy: bool = Field(..., description="Did he attend the liturgy?")
    follow: bool = Field(..., description="Did he run his follow-ups?")
    teachers_meeting: bool = Field(
        ..., description="Did he attend the servants' meeting?"
    )
    date: DateType | None = Field(None, description="Defaults to today")
    note: str | None = None


class TeacherCheckUpdate(BaseModel):
    """Partial update - only the answers and the note can change.

    ``date`` is part of the row's identity (one check per servant per day),
    so it is not editable.
    """

    attend: bool | None = None
    prepare: bool | None = None
    liturgy: bool | None = None
    follow: bool | None = None
    teachers_meeting: bool | None = None
    note: str | None = None


class TeacherCheckResponse(ORMResponse):
    id: int
    teacher_id: int
    class_id: int
    date: DateType
    attend: bool
    prepare: bool
    liturgy: bool
    follow: bool
    teachers_meeting: bool = False
    note: str | None = None
    recorded_by: int | None = None
    created_at: datetime


class TeacherCheckItem(BaseModel):
    """One servant's answers inside a whole-class review."""

    teacher_id: int
    attend: bool
    prepare: bool
    liturgy: bool
    follow: bool
    teachers_meeting: bool = Field(
        ..., description="Did he attend the servants' meeting?"
    )
    note: str | None = None


class TeacherCheckBulkCreate(BaseModel):
    """Every servant of the class reviewed in one Friday POST."""

    date: DateType | None = Field(None, description="Defaults to today")
    items: list[TeacherCheckItem] = Field(..., min_length=1)
