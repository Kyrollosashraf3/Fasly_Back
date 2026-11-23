"""كشف حضور الرحلة: توزيع الأولاد على الخدام وتسجيل حضورهم يوم الرحلة."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class TripAttendanceItem(BaseModel):
    """سطر واحد في كشف حضور الرحلة."""

    boy_id: int = Field(..., description="معرف الولد")
    attend_flag: bool = Field(False, description="حضر في يوم الرحلة؟")


class TripAttendanceBulkCreate(BaseModel):
    """حفظ كشف الحضور لرحلة كاملة في عملية واحدة."""

    items: list[TripAttendanceItem] = Field(..., min_length=1)


class TripAttendanceAssign(BaseModel):
    """توزيع مجموعة أولاد على خادم واحد داخل الرحلة."""

    teacher_id: int = Field(..., description="معرف الخادم")
    boy_ids: list[int] = Field(..., min_length=1)


class TripAttendanceUnassign(BaseModel):
    """إلغاء توزيع أولاد داخل الرحلة."""

    boy_ids: list[int] = Field(..., min_length=1)


class TripAttendanceUpdate(BaseModel):
    """تعديل سطر واحد: علامة الحضور و/أو الخادم المسئول."""

    attend_flag: bool | None = None
    teacher_id: int | None = None


class TripAttendanceResponse(ORMResponse):
    id: int
    church_id: int
    trip_id: int
    boy_id: int
    teacher_id: int | None = None
    attend_flag: bool = False
    boy_name: str | None = None
    teacher_name: str | None = None
    trip_name: str | None = None
    created_at: datetime


class TripSheetRow(BaseModel):
    """ولد واحد في كشف الرحلة: حضوره والخادم المسئول عنه."""

    boy_id: int
    boy_name: str
    teacher_id: int | None = None
    teacher_name: str | None = None
    attend_flag: bool = False
    phone: str | None = None


class TripSheetResponse(BaseModel):
    """كشف رحلة كامل: كل أولاد فصل الرحلة + من حضر ومن وزّع لكل خادم."""

    trip_id: int
    trip_name: str
    class_id: int
    total: int
    attended: int
    rows: list[TripSheetRow]
