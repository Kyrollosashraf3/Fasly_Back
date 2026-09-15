# جدول الخدام teacher — بيانات خدام الفصل (الأساتذة):
# اسم الخادم وتليفونه — بيخدم في فصل كام — ودوره.
# One document per servant in the "teachers" collection.

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import ClassEnum

COLLECTION = "teachers"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TeacherCreate(BaseModel):
    """Payload to register a servant (entered/edited by أمين الفصل)."""

    teacher_name: str = Field(..., min_length=1)
    phone: str | None = None
    class_name: ClassEnum = Field(..., description="The class he serves")
    duty: str | None = Field(default=None, description="دوره — e.g. مدرس، مسئول مجموعة")
    note: str | None = None


class TeacherUpdate(BaseModel):
    """Partial payload to edit a servant — all fields optional."""

    teacher_name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    class_name: ClassEnum | None = None
    duty: str | None = None
    note: str | None = None


class TeacherResponse(TeacherCreate):
    """A servant as stored in Firestore — includes the document id."""

    id: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
