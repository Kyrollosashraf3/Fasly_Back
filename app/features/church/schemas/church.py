from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse


def _clean_optional_text(value: object) -> object:
    """Collapse whitespace on optional free-text fields; keep None as None."""
    if isinstance(value, str):
        return " ".join(value.split()) or None
    return value


class ChurchCreate(BaseModel):
    """A new tenant of the platform - one church with its own data silo."""

    name: str = Field(..., min_length=1, max_length=200, description="Church name")
    region: str | None = Field(None, max_length=100, description="المنطقة / area")
    address: str | None = Field(None, description="Full postal address")
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    is_active: bool = True
    expiry_date: date | None = Field(
        None, description="Subscription expiry; NULL means no expiry"
    )

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            if not cleaned:
                raise ValueError("name must not be empty")
            return cleaned
        return value

    _clean_region = field_validator("region", mode="before")(_clean_optional_text)
    _clean_address = field_validator("address", mode="before")(_clean_optional_text)


class ChurchUpdate(BaseModel):
    """Partial update - all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=200)
    region: str | None = Field(None, max_length=100)
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    phone_2: str | None = Field(None, max_length=50)
    is_active: bool | None = None
    expiry_date: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            if not cleaned:
                raise ValueError("name must not be empty")
            return cleaned
        return value


class ChurchResponse(ORMResponse):
    id: int
    name: str
    region: str | None = None
    address: str | None = None
    phone: str | None = None
    phone_2: str | None = None
    is_active: bool
    expiry_date: date | None = None
    created_at: datetime
    # resolved from the Church.expired / Church.usable properties
    expired: bool = False
    usable: bool = False
