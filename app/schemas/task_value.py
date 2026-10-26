from datetime import date as DateType, datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class TaskValueCreate(BaseModel):
    """تسجيل تسميع ولد لمسابقة: مين سمّعله بيتسجل من الحساب نفسه."""

    task_id: int = Field(..., description="معرف المسابقة")
    boy_id: int = Field(..., description="معرف الولد")
    action_date: DateType | None = Field(
        None, description="تاريخ التسميع - إذا لم يُرسل يعتمد تاريخ اليوم"
    )
    received: bool = Field(
        False, description="هل استلم الولد الطايو بتاعته عند التسميع"
    )


class TaskValueUpdate(BaseModel):
    """تعديل جزئي لتسميع - التاريخ وحالة الاستلام فقط."""

    action_date: DateType | None = None
    received: bool | None = None


class TaskValueDuesItem(BaseModel):
    """سطر من صفحة المستحقات: الولد ومستحقاته مسلّمة ولا لسة."""

    id: int
    received: bool


class TaskValueDuesBulk(BaseModel):
    """حفظ كل العلامات اللي اتغيّرت في المستحقات مرة واحدة."""

    items: list[TaskValueDuesItem] = Field(..., min_length=1)


class TaskValueResponse(ORMResponse):
    id: int
    class_id: int
    task_id: int
    task_name: str | None = None
    task_value: int
    boy_id: int
    boy_name: str | None = None
    action_date: DateType
    received: bool
    created_by: int | None = None
    created_by_name: str | None = None
    created_at: datetime
