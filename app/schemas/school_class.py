from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class SchoolClassCreate(BaseModel):
    """One class group for one academic year (e.g. "1st Primary", 2026/2027)."""

    name: str = Field(..., min_length=1, max_length=100)
    grade_number: int = Field(..., ge=1, le=6, description="1..6")
    academic_year: str = Field(
        ..., min_length=4, max_length=20, examples=["2026/2027"]
    )


class SchoolClassUpdate(BaseModel):
    """Partial update - all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    grade_number: int | None = Field(None, ge=1, le=6)
    academic_year: str | None = Field(None, min_length=4, max_length=20)


class SchoolClassResponse(ORMResponse):
    id: int
    name: str
    grade_number: int
    academic_year: str
    created_at: datetime
