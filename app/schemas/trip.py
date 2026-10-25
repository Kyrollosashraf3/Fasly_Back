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

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or value
        return value


class TripResponse(ORMResponse):
    id: int
    name: str
    cost: int
    class_id: int
    created_at: date