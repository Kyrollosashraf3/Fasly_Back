"""Request / response bodies for teams (الفرق)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse


def _clean_team_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("team_name cannot be blank")
    return cleaned


class TeamCreate(BaseModel):
    """One named team inside a class."""

    team_name: str = Field(..., min_length=1, max_length=100)
    class_id: int = Field(..., description="الفصل الذي يتبعه الفريق - FK classes.id")
    church_id: int | None = Field(
        None,
        description="Tenant that owns the team. Tenant users are pinned to their "
        "own church; only the platform owner may pick another one.",
    )

    @field_validator("team_name", mode="before")
    @classmethod
    def _normalise(cls, value: object) -> object:
        return _clean_team_name(value)


class TeamUpdate(BaseModel):
    """Partial update - only the fields the client actually sent."""

    team_name: str | None = Field(None, min_length=1, max_length=100)
    class_id: int | None = None
    church_id: int | None = None

    @field_validator("team_name", mode="before")
    @classmethod
    def _normalise(cls, value: object) -> object:
        return _clean_team_name(value)


class TeamResponse(ORMResponse):
    id: int
    church_id: int
    class_id: int
    team_name: str
    member_count: int = 0
    teacher_count: int = 0
    class_name: str | None = None
    created_at: datetime
