"""Request / response bodies for servants assigned to a team."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class TeamTeacherCreate(BaseModel):
    """Add one servant to one team."""

    team_id: int
    teacher_id: int


class TeamTeacherBulkCreate(BaseModel):
    """Add several servants to the same team in one request."""

    team_id: int
    teacher_ids: list[int] = Field(..., min_length=1)


class TeamTeacherUpdate(BaseModel):
    """Move an existing link to another team and/or servant."""

    team_id: int | None = None
    teacher_id: int | None = None


class TeamTeacherUnassign(BaseModel):
    """Remove servants from a team (or from every team when ``team_id`` is omitted)."""

    teacher_ids: list[int] = Field(..., min_length=1)
    team_id: int | None = None


class TeamTeacherResponse(ORMResponse):
    id: int
    church_id: int
    team_id: int
    teacher_id: int
    teacher_name: str | None = None
    team_name: str | None = None
    created_at: datetime
