from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class GroupAssign(BaseModel):
    """Put boys into a servant's follow-up group (replaces their old one)."""

    teacher_id: int
    boy_ids: list[int] = Field(..., min_length=1)


class GroupUnassign(BaseModel):
    """Remove boys from any group."""

    boy_ids: list[int] = Field(..., min_length=1)


class GroupResponse(ORMResponse):
    id: int
    teacher_id: int
    boy_id: int
    created_at: datetime
