from datetime import date as Date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import SubscriptionTypeEnum
from app.schemas.base import ORMResponse

SubscriptionType = Literal["charge", "recover"]


class SubscriptionCreate(BaseModel):
    """تسجيل حركة مالية لولد في رحلة."""
    boy_id: int = Field(..., description="معرف الولد")
    trip_id: int = Field(..., description="معرف الرحلة")
    type: SubscriptionType = Field(
        "charge", description="charge = مصروف، recover = استرداد"
    )
    value: int = Field(..., ge=0, description="المبلغ بالجنيه")
    note: str | None = Field(
        None, description="ملاحظة تُسجل مع الدفعة (مثال: سبب الاسترداد، ملاحظة من الخادم)"
    )

    date: Date | None = Field(
        None,
        description="التاريخ اللي تم تسجيل الدفعة عليه (YYYY-MM-DD)"
    )

    created_at: datetime | None = Field(
        None, description="تاريخ ووقت التسجيل - إذا لم يُرسل يعتمد الآن"
    )


class SubscriptionUpdate(BaseModel):
    """تعديل جزئي لحركة مالية."""
    type: SubscriptionType | None = None
    value: int | None = Field(None, ge=0)
    note: str | None = Field(
        None, description="ملاحظة تُسجل مع الدفعة"
    )

    date: Date | None = Field(
        None, description="التاريخ اللي تم تسجيل الدفعة عليه (YYYY-MM-DD)"
    )

    created_at: datetime | None = None


class SubscriptionResponse(ORMResponse):
    id: int
    boy_id: int
    trip_id: int
    type: SubscriptionTypeEnum
    value: int
    created_at: datetime
    created_by: int | None = None
    created_by_name: str | None = None
    boy_name: str | None = None
    trip_name: str | None = None
    note: str | None = None


class BoyTripTotal(BaseModel):
    """مجموع ما دفعه ولد في رحلة معينة (مصروف ناقص استرداد)."""
    boy_id: int
    boy_name: str
    total_paid: int = Field(
        description="مجموع المصروفات ناقص مجموع الاستردادات بالجنيه"
    )


class BoyTripSummary(BaseModel):
    """ملخص دفعات ولد في رحلة: مصروف، استرداد، مدفوع، وباقي من تكلفة الرحلة."""
    boy_id: int
    boy_name: str
    trip_id: int
    trip_name: str
    trip_cost: int = Field(description="تكلفة الاشتراك في الرحلة للجنيه الواحد")
    total_charged: int = Field(description="مجموع المصروفات (charge)")
    total_recovered: int = Field(description="مجموع الاستردادات (recover)")
    total_paid: int = Field(description="إجمالي ما دفعه فعلياً (مصروف ناقص استرداد)")
    remaining: int = Field(description="الباقي على الولد من تكلفة الرحلة")
