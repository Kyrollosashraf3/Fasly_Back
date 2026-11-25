from datetime import date as Date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import SubscriptionTypeEnum
from app.schemas.base import ORMResponse

ServantSubscriptionType = Literal["charge", "recover"]


class ServantTripSubscriptionCreate(BaseModel):
    teacher_id: int = Field(..., description="معرف الخادم")
    trip_id: int = Field(..., description="معرف رحلة الخدام")
    type: ServantSubscriptionType = "charge"
    value: int = Field(..., ge=0, description="المبلغ بالجنيه")
    note: str | None = None
    date: Date | None = None
    created_at: datetime | None = None


class ServantTripSubscriptionUpdate(BaseModel):
    type: ServantSubscriptionType | None = None
    value: int | None = Field(None, ge=0)
    note: str | None = None
    date: Date | None = None
    created_at: datetime | None = None


class ServantTripSubscriptionResponse(ORMResponse):
    id: int
    teacher_id: int
    teacher_name: str | None = None
    trip_id: int
    trip_name: str | None = None
    type: SubscriptionTypeEnum
    value: int
    created_at: datetime
    created_by: int | None = None
    created_by_name: str | None = None
    note: str | None = None


class ServantTripTotal(BaseModel):
    teacher_id: int
    teacher_name: str
    total_paid: int


class ServantTripSummary(BaseModel):
    teacher_id: int
    teacher_name: str
    trip_id: int
    trip_name: str
    trip_cost: int
    total_charged: int
    total_recovered: int
    total_paid: int
    remaining: int
    registered: bool = False
