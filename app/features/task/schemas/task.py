from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMResponse


class TaskCreate(BaseModel):
    """مسابقة جديدة: اسمها، مكافأتها بالطايو، فصلها، وتاريخ تسجيلها."""

    task_name: str = Field(
        ...,
        max_length=200,
        description="اسم المسابقة",
        examples=["حفظ اصحاح 4 من انجيل مرقس"],
    )
    value: int = Field(
        ...,
        ge=0,
        description="المكافأة بالطايو لكل ولد يسمع المسابقة",
        examples=[50],
    )
    class_id: int = Field(
        ..., description="الفصل الذي تنتمي له المسابقة (مفتاح خارجي لجدول الفصول)"
    )
    created_at: date | None = Field(
        None,
        description="تاريخ التسجيل - إذا لم يُرسل يعتمد تاريخ اليوم",
    )
    status: str | None = Field(
        'active',
        description="حالة المسابقة: active أو inactive",
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

    @field_validator("task_name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or value
        return value


class TaskUpdate(BaseModel):
    """تعديل جزئي للمسابقة - كل الحقول اختيارية."""

    task_name: str | None = Field(None, max_length=200)
    value: int | None = Field(None, ge=0)
    class_id: int | None = None
    created_at: date | None = None
    status: str | None = Field(None, description="active أو inactive")

    @field_validator("task_name", mode="before")
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


class TaskResponse(ORMResponse):
    id: int
    task_name: str
    value: int
    class_id: int
    created_at: date
    status: str
