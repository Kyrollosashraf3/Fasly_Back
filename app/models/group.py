"""Group assignment payloads (servant follow-up groups)."""

from pydantic import BaseModel, Field


class GroupAssign(BaseModel):
    """Put a list of boys into a servant's group (replaces their old group)."""

    teacher_id: str = Field(..., min_length=1)
    boy_ids: list[str] = Field(..., min_length=1)


class GroupUnassign(BaseModel):
    """Remove boys from any group."""

    boy_ids: list[str] = Field(..., min_length=1)
