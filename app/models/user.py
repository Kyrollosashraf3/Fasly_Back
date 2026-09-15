# admins & users accounts - admin sees all classes data - user sees his class only.
# One document per account in the "users" collection.

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import ClassEnum, RoleEnum

COLLECTION = "users"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserCreate(BaseModel):
    """Payload to create an account (plain password — hash it before storing)."""

    user_name: str = Field(..., min_length=1)
    mail: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    phone: str | None = None
    role: RoleEnum = RoleEnum.USER
    class_name: ClassEnum | None = None


class UserUpdate(BaseModel):
    """Partial payload to edit an account — all fields optional."""

    user_name: str | None = Field(default=None, min_length=1)
    mail: str | None = Field(default=None, min_length=5)
    password: str | None = Field(default=None, min_length=6)
    phone: str | None = None
    role: RoleEnum | None = None
    class_name: ClassEnum | None = None


class UserResponse(BaseModel):
    """Safe public shape — never includes any password."""

    id: str
    user_name: str
    mail: str
    phone: str | None = None
    role: RoleEnum
    class_name: ClassEnum | None = None
    created_at: datetime = Field(default_factory=_now)


class UserInDB(UserResponse):
    """Stored shape — keeps the hash for login checks, never returned by the API."""

    password_hash: str
