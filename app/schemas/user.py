from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import RoleEnum
from app.schemas.base import ORMResponse

PHONE_PATTERN = r"^01[0-9]{9}$"


_TEACHER_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN)

# Roles the Excel import may grant. super_admin is included on purpose:
# it is the only role that does not need a servant / boy behind it.
IMPORT_ROLES = (RoleEnum.SUPER_ADMIN, RoleEnum.ADMIN, RoleEnum.TEACHER, RoleEnum.USER)


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
    elif role == RoleEnum.GENERAL_ADMIN:
        # A stage amin IS a servant: the classes he answers for are rows of his
        # teacher record, so the link is what makes the role meaningful.
        if teacher_id is None:
            raise ValueError("role 'general_admin' requires teacher_id")
        if boy_id is not None:
            raise ValueError("role 'general_admin' must not set boy_id")
    else:  # SUPER_ADMIN may carry a teacher (his name) but never a boy
        if boy_id is not None:
            raise ValueError("role 'super_admin' must not set boy_id")


def normalise_phone(value: object) -> object:
    """Delegate to :func:`app.core.data.common.normalise_phone`.

    The rule itself lives in ``common`` so the service layer can use the same
    one; it is imported lazily on purpose because importing the service
    package at module load would be a circular import (``app.core.data``
    imports these schemas).
    """
    from app.core.data.common import normalise_phone as _normalise_phone

    return _normalise_phone(value)


class UserCreate(BaseModel):
    """New login created by an administrator.

    ``password`` is optional: an account registered without one is created
    with ``password_hash = NULL`` and the owner finishes it himself from the
    signup screen.
    """

    phone: str = Field(
        ..., max_length=20, pattern=PHONE_PATTERN, description="e.g. 01012345678"
    )
    password: str | None = Field(None, min_length=8, max_length=128)
    role: RoleEnum
    teacher_id: int | None = Field(
        None, description="Set for role=teacher/admin - the servant this login belongs to"
    )
    boy_id: int | None = Field(
        None, description="Set for role=user - the boy this login belongs to"
    )
    class_ids: list[int] = Field(
        default_factory=list,
        description="Set for role=general_admin - the classes he is answerable for",
    )

    @field_validator("phone", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        return normalise_phone(value)

    @model_validator(mode="after")
    def _check_owner(self) -> "UserCreate":
        check_owner(self.role, self.teacher_id, self.boy_id)
        return self


class ManagedClassesUpdate(BaseModel):
    """The whole class list of a stage amin - sent again on every change."""

    class_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """Partial update.

    ``password`` omitted = keep the current one.

    If ``role`` is sent, the owner links are re-checked against the *values in
    this payload* - so changing the role must carry the matching
    ``teacher_id``/``boy_id`` in the same request (a role switch can never
    leave a broken row behind).
    """

    phone: str | None = Field(None, max_length=20, pattern=PHONE_PATTERN)
    password: str | None = Field(None, min_length=8, max_length=128)
    role: RoleEnum | None = None
    teacher_id: int | None = None
    boy_id: int | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        return normalise_phone(value)

    @model_validator(mode="after")
    def _check_owner(self) -> "UserUpdate":
        if self.role is not None:
            check_owner(self.role, self.teacher_id, self.boy_id)
        return self


class UserImportRow(BaseModel):
    """One row of the accounts sheet: phone | class_name | name | role.

    The sheet carries *descriptions*, not ids - the service resolves the
    servant / boy behind ``name`` in ``class_name`` (creating the servant
    when he is not there yet) before turning this into a :class:`UserCreate`.
    """

    phone: str = Field(..., max_length=20, pattern=PHONE_PATTERN)
    class_name: str | None = Field(None, max_length=100)
    name: str | None = Field(None, max_length=255)
    role: RoleEnum
    # resolved by the reader from class_name (blank for super_admin)
    class_id: int | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        return normalise_phone(value)

    @field_validator("name", "class_name", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_row(self) -> "UserImportRow":
        if self.role == RoleEnum.SUPER_ADMIN:
            return self
        if not self.class_name:
            raise ValueError("class_name is required")
        if not self.name:
            raise ValueError("name is required")
        if self.class_id is None:
            raise ValueError(f"unknown class_name {self.class_name!r}")
        return self


class SignupCheckRequest(BaseModel):
    """Is this phone on file, and is it still waiting for a password?"""

    phone: str = Field(..., max_length=20, pattern=PHONE_PATTERN)

    @field_validator("phone", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        return normalise_phone(value)


class SignupCheckResponse(BaseModel):
    exists: bool
    needs_signup: bool
    display_name: str | None = None
    role: RoleEnum | None = None


class SignupRequest(BaseModel):
    """The owner picks the password for his phone-registered account."""

    phone: str = Field(..., max_length=20, pattern=PHONE_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)
    password_confirm: str = Field(..., min_length=8, max_length=128)

    @field_validator("phone", mode="before")
    @classmethod
    def _normalise_phone(cls, value: object) -> object:
        return normalise_phone(value)

    @model_validator(mode="after")
    def _same_passwords(self) -> "SignupRequest":
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self


class UserInDB(ORMResponse):
    """Raw row - includes ``password_hash``. Never leave the server."""

    id: int
    phone: str
    password_hash: str | None = None
    role: RoleEnum
    teacher_id: int | None = None
    boy_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserResponse(ORMResponse):
    """What the client gets back - no credentials."""

    id: int
    phone: str
    role: RoleEnum
    teacher_id: int | None = None
    boy_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    # resolved from User.display_name (teacher -> boy -> None)
    display_name: str | None = None
    # True while password_hash is still NULL (signup not finished)
    pending_signup: bool = False
    # the classes a stage amin answers for (empty for every other role) -
    # resolved from User.managed_class_ids, so /auth/me carries his scope
    managed_class_ids: list[int] = []


class Token(BaseModel):
    """OAuth2 password-flow payload returned by POST /auth/login."""

    access_token: str
    token_type: str = "bearer"
