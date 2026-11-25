from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse


class ServantTripCreate(BaseModel):
    name: str = Field(..., max_length=200)
    cost: int = Field(..., ge=0, description="قيمة الاشتراك لكل خادم بالجنيه")
    created_at: date | None = None
    status: str | None = "active"

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: object) -> object:
        if value is None:
            return "active"
        status_value = str(value).strip().lower()
        if status_value not in ("active", "inactive"):
            return "active"
        return status_value

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or value
        return value


class ServantTripUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    cost: int | None = Field(None, ge=0)
    created_at: date | None = None
    status: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or value
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: object) -> object:
        if value is None:
            return value
        status_value = str(value).strip().lower()
        if status_value not in ("active", "inactive"):
            return value
        return status_value


class ServantTripResponse(ORMResponse):
    id: int
    church_id: int
    name: str
    cost: int
    created_at: date
    status: str
    recorded_by: int | None = None
