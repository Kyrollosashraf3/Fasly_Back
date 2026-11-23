from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import FollowEnum
from app.schemas.base import ORMResponse


class FollowUpCreate(BaseModel):
    """A servant logs one contact with one boy.

    ``class_id`` (historical snapshot) and ``recorded_by`` are stamped
    server-side, so they are absent from the payload.
    """

    teacher_id: int
    boy_id: int
    status: FollowEnum = Field(..., description="How the boy was reached")
    action_date: date | None = Field(None, description="Defaults to today")
    note: str | None = None


class FollowUpUpdate(BaseModel):
    """Partial update - the (teacher, boy, class) identity never changes."""

    status: FollowEnum | None = None
    action_date: date | None = None
    note: str | None = None


class FollowUpResponse(ORMResponse):
    id: int
    teacher_id: int
    boy_id: int
    class_id: int
    action_date: date
    status: FollowEnum
    note: str | None = None
    recorded_by: int | None = None
    created_at: datetime
