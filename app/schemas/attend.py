from datetime import date as DateType, datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class AttendCreate(BaseModel):
    """One boy's attendance for one day.

    ``class_id`` and ``recorded_by`` are stamped server-side: the class is a
    snapshot of the boy's class on ``date``, so it is never taken from the
    payload.
    """

    boy_id: int
    present: bool
    liturgy: bool = False
    date: DateType | None = Field(None, description="Defaults to today")
    note: str | None = None


class AttendUpdate(BaseModel):
    """Only the outcome is editable - boy/date/class are the row's identity."""

    present: bool | None = None
    liturgy: bool | None = None
    note: str | None = None


class AttendResponse(ORMResponse):
    id: int
    boy_id: int
    class_id: int
    date: DateType
    present: bool
    liturgy: bool = False
    note: str | None = None
    recorded_by: int | None = None
    created_at: datetime


class AttendItem(BaseModel):
    """One line of the Friday sheet: every boy of the class, present or not."""

    boy_id: int
    present: bool = False
    liturgy: bool = False
    note: str | None = None


class AttendBulkCreate(BaseModel):
    """Copy the class roster and tick the ones who showed up."""

    date: DateType | None = Field(None, description="Defaults to today")
    items: list[AttendItem] = Field(..., min_length=1)
