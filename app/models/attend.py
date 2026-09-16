# Flow: frontend fetches boys of one class -> servant checks who attended today
# -> ONE bulk request saves them all. One document per (boy, friday) in "attendance".
# class_name is denormalized so we can query "class 5 attendance on date X" with no join.

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import AttendEnum, ClassEnum

COLLECTION = "attendance"


class AttendCreate(BaseModel):
    """Payload to record one boy's attendance on a Friday."""

    boy_id: str = Field(..., min_length=1, description="Firestore document id of the boy")
    boy_name: str | None = Field(default=None, description="Denormalized for listing without a join")
    class_name: ClassEnum | None = Field(default=None, description="Denormalized from the boy for class+date queries")
    action_date: date = Field(default_factory=date.today)
    attend: AttendEnum
    note: str | None = None
    recorded_by: str | None = Field(default=None, description="User id of the servant who took attendance")
    recorded_by_name: str | None = Field(default=None, description="Denormalized for listing without a join")


class AttendUpdate(BaseModel):
    """Partial payload to edit an attendance record — all fields optional."""

    boy_id: str | None = Field(default=None, min_length=1)
    boy_name: str | None = None
    class_name: ClassEnum | None = None
    action_date: date | None = None
    attend: AttendEnum | None = None
    note: str | None = None
    recorded_by: str | None = None
    recorded_by_name: str | None = None


class AttendResponse(AttendCreate):
    """An attendance record as stored in Firestore — includes the document id."""

    id: str


class AttendItem(BaseModel):
    """One row in the bulk submit — explicit Y/N for every boy shown on screen."""

    boy_id: str = Field(..., min_length=1)
    attend: AttendEnum
    note: str | None = None


class AttendBulkCreate(BaseModel):
    """Payload for the Friday flow: whole class attendance in a single request."""

    class_name: ClassEnum
    action_date: date = Field(default_factory=date.today)
    recorded_by: str | None = None
    items: list[AttendItem] = Field(..., min_length=1)
