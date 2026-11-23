from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse

# The programme runs on a fixed catalogue of class names - no free typing.
CLASS_NAMES: tuple[str, ...] = (
    "أولي ابتدائي",
    "تانية ابتدائي",
    "تالتة ابتدائي",
    "رابعة ابتدائي",
    "خامسة ابتدائي",
    "سادسة ابتدائي",
    "أولي اعدادي",
    "تانية اعدادي",
    "تالتة اعدادي",
    "أولي ثانوي",
    "تانية ثانوي",
    "تالتة ثانوي",
    "شباب",
)

def normalise_class_name(value: object) -> object:
    """Collapse whitespace, reject anything outside the catalogue."""
    if not isinstance(value, str):
        return value
    cleaned = " ".join(value.split())
    if cleaned not in CLASS_NAMES:
        raise ValueError(
            "name must be one of: " + " | ".join(CLASS_NAMES)
        )
    return cleaned


class SchoolClassCreate(BaseModel):
    """One class group for one academic year (e.g. "أولي ابتدائي", 2026/2027)."""

    name: str = Field(
        ...,
        max_length=100,
        description="One of the fixed class names: " + " | ".join(CLASS_NAMES),
        examples=[CLASS_NAMES[0]],
    )
    academic_year: str = Field(
        ..., min_length=4, max_length=20, examples=["2026/2027"]
    )
    church_id: int | None = Field(
        None,
        description="Tenant that owns the class. Tenant users are pinned to their "
        "own church; only the platform owner may pick another one.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> object:
        return normalise_class_name(value)


class SchoolClassUpdate(BaseModel):
    """Partial update - all fields optional."""

    name: str | None = Field(None, max_length=100)
    academic_year: str | None = Field(None, min_length=4, max_length=20)

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> object:
        return normalise_class_name(value)


class SchoolClassResponse(ORMResponse):
    id: int
    church_id: int | None = None
    name: str
    academic_year: str
    created_at: datetime
