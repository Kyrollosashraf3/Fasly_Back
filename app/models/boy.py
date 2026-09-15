# app/models/boy.py
# Boys master data (Sunday school students). One document per boy in the "boys" collection.

from datetime import date, datetime, timezone
from pydantic import BaseModel, Field
from app.models.enums import ClassEnum, GenderEnum

COLLECTION = "boys"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BoyCreate(BaseModel):
    """Payload to register a new boy."""

    boy_name: str = Field(..., min_length=1)
    gender: GenderEnum = GenderEnum.MALE
    birth_date: date | None = None
    age: int | None = Field(default=None, ge=0)
    phone: str | None = None
    phone_2: str | None = None
    address: str | None = None
    location: str | None = None  # GPS link
    class_name: ClassEnum
    note: str | None = None
    issue_flag: bool = False


class BoyUpdate(BaseModel):
    """Partial payload to edit a boy — all fields optional."""

    boy_name: str | None = Field(default=None, min_length=1)
    gender: GenderEnum | None = None
    birth_date: date | None = None
    age: int | None = Field(default=None, ge=0)
    phone: str | None = None
    phone_2: str | None = None
    address: str | None = None
    location: str | None = None
    class_name: ClassEnum | None = None
    note: str | None = None
    issue_flag: bool | None = None


class BoyResponse(BoyCreate):
    """A boy as stored in Firestore — includes the document id."""

    id: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
