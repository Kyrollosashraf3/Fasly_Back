"""Request / response bodies for saving house points and the visit map.

The server never guesses a phone's GPS: the client reads it with
``navigator.geolocation`` and sends ``latitude``/``longitude``. Boy coordinates
are stored on ``boys`` and servant coordinates on ``teachers``. The follow-up
type is the existing ``FollowEnum`` and belongs to ``follow_ups.status`` - if
the client sends ``status`` while saving a boy's point, the service writes
that follow-up row too.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.enums import (
    FOLLOW_STATUS_LABELS,
    FollowEnum,
    GenderEnum,
)


class LocationRecord(BaseModel):
    """Body of ``POST /locations/boys/{boy_id}`` (and ``.../boys/me``)."""

    latitude: float = Field(..., ge=-90, le=90, description="خط العرض من GPS")
    longitude: float = Field(..., ge=-180, le=180, description="خط الطول من GPS")
    status: FollowEnum | None = Field(
        None,
        description=(
            "نوع الافتقاد (من FollowEnum: call/visit/whatsapp/no_answer/other). "
            "إن أُرسل يُنشأ سطر في follow_ups بنفس النوع؛ وإن تُرك فارغاً "
            "يُحدَّث الموقع فقط."
        ),
    )
    note: str | None = Field(None, max_length=1000, description="ملاحظة للافتقاد")


class BoyLocationResponse(BaseModel):
    """Result of saving a point - the boy's current coordinates."""

    boy_id: int
    boy_name: str | None = None
    latitude: float
    longitude: float
    updated_at: datetime | None = None
    follow_up_id: int | None = None


class TeacherLocationResponse(BaseModel):
    teacher_id: int
    teacher_name: str
    latitude: float
    longitude: float
    updated_at: datetime | None = None


class TeacherLocationRecord(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class MapScopeEnum(str, Enum):
    """The two filters the UI asked for, plus an explicit "all my classes"."""

    GROUP = "group"    # مجموعتي فقط (خدم واحد)
    CLASS = "class"    # الفصل كله
    ALL = "all"        # كل الفصول المسموحة (نفس نطاق class للأمين العادي)


class FollowUpPrefill(BaseModel):
    """Body ready to POST to ``POST /follow-ups`` when (+) is tapped.

    The frontend can spread this object straight into its request; only
    ``status`` / ``note`` may be edited in the panel first.
    """

    teacher_id: int | None
    boy_id: int
    status: FollowEnum = FollowEnum.VISIT
    action_date: date
    note: str = ""


class MapPersonTypeEnum(str, Enum):
    BOYS = "boys"
    TEACHERS = "teachers"


class MapHouse(BaseModel):
    """One person on the visit map - whether they have coordinates or not."""

    person_type: MapPersonTypeEnum = MapPersonTypeEnum.BOYS
    person_id: int | None = None
    person_name: str | None = None
    boy_id: int | None = None
    boy_name: str | None = None
    gender: GenderEnum | None = None
    class_id: int | None = None
    class_name: str = ""
    teacher_id: int | None = None
    teacher_name: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    has_coordinates: bool = False
    zone: str | None = None
    address: str | None = None

    phone: str | None = None
    phone_2: str | None = None
    whatsapp_url: str | None = None   # https://wa.me/20...
    call_url: str | None = None       # tel:+20...

    last_follow_up_date: date | None = None
    last_follow_up_status: FollowEnum | None = None
    follow_up_count: int = 0

    prefill: FollowUpPrefill | None = None
    can_record_location: bool = True
    can_follow_up: bool = True


class MapOrigin(BaseModel):
    """The "مني" point the route starts from."""

    latitude: float
    longitude: float
    source: str = Field(description="client = من جهاز المستخدم | first_house = أول بيت")


class MapLeg(BaseModel):
    """One drawn segment between two consecutive stops."""

    order: int
    from_boy_id: int | None = None   # null = from "مني" (the client's position)
    from_person_id: int | None = None
    from_latitude: float
    from_longitude: float
    to_boy_id: int | None = None
    to_person_id: int | None = None
    to_latitude: float
    to_longitude: float
    distance_m: int
    distance_km: float
    walk_minutes: int


class MapSummary(BaseModel):
    total_boys: int
    total_people: int
    located: int
    unlocated: int
    visited_today: int
    coverage_percent: float


class MapRouteResponse(BaseModel):
    """Everything the map screen needs in one call."""

    scope: MapScopeEnum
    scope_label: str
    person_type: MapPersonTypeEnum = MapPersonTypeEnum.BOYS
    teacher_id: int | None = None
    class_ids: list[int] | None = None   # null = كل الفصول (super admin)
    origin: MapOrigin | None = None
    houses: list[MapHouse]               # مرتبة: الأقرب فالأقرب
    unlocated: list[MapHouse]            # لازم يسجّلوا لوكيشن أولاً
    legs: list[MapLeg]
    polyline: list[list[float]]          # [[lat, lng], ...] يبدأ من origin
    ordered_boy_ids: list[int] = Field(default_factory=list)
    ordered_person_ids: list[int] = Field(default_factory=list)
    total_distance_m: int
    total_distance_km: float
    total_walk_minutes: int
    summary: MapSummary
    follow_up_status_options: list[dict[str, str]]
    generated_at: datetime


def option_list(labels: dict) -> list[dict[str, str]]:
    """Turn an enum-label mapping into the ``[{value, label}]`` a <select> wants."""
    return [{"value": key.value, "label": label} for key, label in labels.items()]


FOLLOW_UP_STATUS_OPTIONS = option_list(FOLLOW_STATUS_LABELS)
