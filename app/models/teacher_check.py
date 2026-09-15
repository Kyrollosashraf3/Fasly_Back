# أمين الفصل follows his class servants every Friday:
# جهزت الدرس؟ حضرت اللتورجيا؟ عملت followup للمجموعة؟ جيت ولا لا؟
# Servant name comes from the teachers collection (denormalized at write time).
# One document per (teacher, friday) in the "teacher_checks" collection.

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import AttendEnum, ClassEnum

COLLECTION = "teacher_checks"


class TeacherCheckCreate(BaseModel):
    """Payload for the weekly check on one servant."""

    teacher_id: str = Field(..., min_length=1, description="Firestore document id of the servant (teachers collection)")
    teacher_name: str | None = Field(default=None, description="Filled from teachers at write time, not trusted from client")
    class_name: ClassEnum | None = Field(default=None, description="Denormalized for class+date queries")
    action_date: date = Field(default_factory=date.today)
    attend: AttendEnum = Field(..., description="Came on Friday or not")
    prepare_flag: bool = Field(default=False, description="جهز الدرس؟")
    liturgy_flag: bool = Field(default=False, description="حضر اللتورجيا؟")
    follow_flag: bool = Field(default=False, description="عمل followup للمجموعة؟")
    note: str | None = None
    recorded_by: str | None = Field(default=None, description="User id of the أمين who recorded the check")


class TeacherCheckUpdate(BaseModel):
    """Partial payload to edit a check — all fields optional."""

    teacher_id: str | None = Field(default=None, min_length=1)
    teacher_name: str | None = None
    class_name: ClassEnum | None = None
    action_date: date | None = None
    attend: AttendEnum | None = None
    prepare_flag: bool | None = None
    liturgy_flag: bool | None = None
    follow_flag: bool | None = None
    note: str | None = None
    recorded_by: str | None = None


class TeacherCheckResponse(TeacherCheckCreate):
    """A check as stored in Firestore — includes the document id."""

    id: str


class TeacherCheckItem(BaseModel):
    """One row in the bulk submit — one servant's answers."""

    teacher_id: str = Field(..., min_length=1)
    attend: AttendEnum
    prepare_flag: bool = False
    liturgy_flag: bool = False
    follow_flag: bool = False
    note: str | None = None


class TeacherCheckBulkCreate(BaseModel):
    """Payload for the Friday flow: all servants' checks in a single request."""

    class_name: ClassEnum
    action_date: date = Field(default_factory=date.today)
    recorded_by: str | None = None
    items: list[TeacherCheckItem] = Field(..., min_length=1)
