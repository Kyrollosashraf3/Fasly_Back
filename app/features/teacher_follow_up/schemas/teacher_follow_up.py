from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import FollowEnum
from app.schemas.base import ORMResponse


class TeacherFollowUpCreate(BaseModel):
    teacher_id: int
    status: FollowEnum
    action_date: date | None = Field(None, description="Defaults to today")
    note: str | None = None


class TeacherFollowUpUpdate(BaseModel):
    status: FollowEnum | None = None
    action_date: date | None = None
    note: str | None = None


class TeacherFollowUpResponse(ORMResponse):
    id: int
    church_id: int
    teacher_id: int
    class_id: int | None = None
    action_date: date
    status: FollowEnum
    note: str | None = None
    recorded_by: int | None = None
    created_at: datetime
