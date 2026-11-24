"""Request / response bodies for boys assigned to a team."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class TeamMemberCreate(BaseModel):
    """Add one boy to one team."""

    team_id: int
    boy_id: int


class TeamMemberBulkCreate(BaseModel):
    """Add several boys to the same team in one request."""

    team_id: int
    boy_ids: list[int] = Field(..., min_length=1)


class TeamMemberUpdate(BaseModel):
    """Move an existing link to another team and/or boy."""

    team_id: int | None = None
    boy_id: int | None = None


class TeamMemberUnassign(BaseModel):
    """Remove boys from a team (or from every team when ``team_id`` is omitted)."""

    boy_ids: list[int] = Field(..., min_length=1)
    team_id: int | None = None


class TeamMemberResponse(ORMResponse):
    id: int
    church_id: int
    team_id: int
    boy_id: int
    boy_name: str | None = None
    team_name: str | None = None
    created_at: datetime
