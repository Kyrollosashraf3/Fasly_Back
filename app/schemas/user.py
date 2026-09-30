from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import RoleEnum
from app.schemas.base import ORMResponse

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

_TEACHER_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN)


def check_owner(role: RoleEnum, teacher_id: int | None, boy_id: int | None) -> None:
    """Mirror of the DB constraint ``ck_users_role_owner``.

    Raises ``ValueError`` with a message the API can return verbatim instead
    of leaking a raw IntegrityError.
    """
    if role in _TEACHER_ROLES:
        if teacher_id is None:
            raise ValueError(f"role '{role.value}' requires teacher_id")
        if boy_id is not None:
            raise ValueError(f"role '{role.value}' must not set boy_id")
    elif role == RoleEnum.USER:
        if boy_id is None:
            raise ValueError(f"role '{role.value}' requires boy_id")
        if teacher_id is not None:
            raise ValueError(f"role '{role.value}' must not set teacher_id")
    else:  # SUPER_ADMIN owns no record - he sees every class
        if teacher_id is not None or boy_id is not None:
            raise ValueError("role 'super_admin' must not set teacher_id or boy_id")


class UserCreate(BaseModel):
    """New login. ``password`` arrives in clear and is hashed by the service."""

    email: str = Field(..., max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)
    role: RoleEnum
    teacher_id: int | None = Field(
        None, description="Set for role=teacher/admin - the servant this login belongs to"
    )
    boy_id: int | None = Field(
        None, description="Set for role=user - the boy this login belongs to"
    )

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: object) -> object:
        # runs before the pattern check, so "  A@B.COM " is trimmed first
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_owner(self) -> "UserCreate":
        check_owner(self.role, self.teacher_id, self.boy_id)
        return self


class UserUpdate(BaseModel):
    """Partial update.

    ``password`` omitted = keep the current one.

    If ``role`` is sent, the owner links are re-checked against the *values in
    this payload* - so changing the role must carry the matching
    ``teacher_id``/``boy_id`` in the same request (a role switch can never
    leave a broken row behind).
    """

    email: str | None = Field(None, max_length=255, pattern=EMAIL_PATTERN)
    password: str | None = Field(None, min_length=8, max_length=128)
    role: RoleEnum | None = None
    teacher_id: int | None = None
    boy_id: int | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_owner(self) -> "UserUpdate":
        if self.role is not None:
            check_owner(self.role, self.teacher_id, self.boy_id)
        return self


class UserInDB(ORMResponse):
    """Raw row - includes ``password_hash``. Never leave the server."""

    id: int
    email: str
    password_hash: str
    role: RoleEnum
    teacher_id: int | None = None
    boy_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserResponse(ORMResponse):
    """What the client gets back - no credentials."""

    id: int
    email: str
    role: RoleEnum
    teacher_id: int | None = None
    boy_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    # resolved from User.display_name (teacher -> boy -> None)
    display_name: str | None = None


class Token(BaseModel):
    """OAuth2 password-flow payload returned by POST /auth/login."""

    access_token: str
    token_type: str = "bearer"
