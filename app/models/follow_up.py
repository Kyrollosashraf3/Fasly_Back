"""Every teacher has a group of students to call every week to check on them.
One document per (teacher, boy, week) call in the "follow_ups" collection."""

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import FollowEnum

COLLECTION = "follow_ups"


class FollowUpCreate(BaseModel):
    """Payload to log one weekly follow-up call from a teacher to a boy."""

    teacher_id: str = Field(..., min_length=1, description="Firestore document id of the servant (teachers collection)")
    teacher_name: str | None = Field(default=None, description="Denormalized for listing without a join")
    boy_id: str = Field(..., min_length=1, description="Firestore document id of the boy")
    boy_name: str | None = Field(default=None, description="Denormalized for listing without a join")
    action_date: date = Field(default_factory=date.today)
    status: FollowEnum = FollowEnum.CALL
    note: str | None = None


class FollowUpUpdate(BaseModel):
    """Partial payload to edit a follow-up — all fields optional."""

    teacher_id: str | None = Field(default=None, min_length=1)
    teacher_name: str | None = None
    boy_id: str | None = Field(default=None, min_length=1)
    boy_name: str | None = None
    action_date: date | None = None
    status: FollowEnum | None = None
    note: str | None = None


class FollowUpResponse(FollowUpCreate):
    """A follow-up as stored in Firestore — includes the document id."""

    id: str
