from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse


class TripCreate(BaseModel):
    """رحلة جديدة: اسم، قيمة اشتراك، فصل، وتاريخ التسجيل."""

    name: str = Field(
        ...,
        max_length=200,
        description="اسم الرحلة",
        examples=["رحلة دير القديس"],
    )
    cost: int = Field(
        ...,
        ge=0,
        description="قيمة الاشتراك بالجنيه لكل ولد",
        examples=[50],
    )
    class_id: int = Field(
        ..., description="الفصل الذي تنتمي له الرحلة (مفتاح خارجي لجدول الفصول)"
    )
    created_at: date | None = Field(
        None,
        description="تاريخ التسجيل - إذا لم يُرسل يعتمد تاريخ اليوم",
    )
    status: str | None = Field(
        'active',
        description="حالة الرحلة: active أو inactive",
    )

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: object) -> object:
        if value is None:
            return 'active'
        v = str(value).strip().lower()
        if v not in ('active', 'inactive'):
            return 'active'
        return v

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or value
        return value


class TripUpdate(BaseModel):
    """تعديل جزئي للرحلة - كل الحقول اختيارية."""

    name: str | None = Field(None, max_length=200)
    cost: int | None = Field(None, ge=0)
    class_id: int | None = None
    created_at: date | None = None
    status: str | None = Field(None, description="active أو inactive")

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
        v = str(value).strip().lower()
        if v not in ('active', 'inactive'):
            return value
        return v


class TripResponse(ORMResponse):
    id: int
    name: str
    cost: int
    class_id: int
    created_at: date
    status: str