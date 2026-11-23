"""اشتراكات الأولاد في الرحلات: إضافة، تعديل، حذف، وإجمالي لكل ولد."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.subscription.services import SubscriptionService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.subscription.schemas.subscription import (
    BoyTripSummary,
    BoyTripTotal,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db, current_user).list()


@router.get("/trip/{trip_id}", response_model=list[SubscriptionResponse])
def list_subscriptions_for_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db, current_user).get_for_trip(trip_id)


@router.get(
    "/trip/{trip_id}/boys",
    response_model=list[BoyTripTotal],
    summary="مجموع ما دفعه كل ولد في الرحلة",
)
def trip_boy_totals(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """كل الولد في فصل الرحلة مع مجموع ما دفعه (مصروف ناقص استرداد)."""
    return SubscriptionService(db, current_user).get_boy_totals(trip_id)


@router.get(
    "/trip/{trip_id}/summary",
    response_model=list[BoyTripSummary],
    summary="ملخص كل أولاد الرحلة: دفوعهم والباقي عليهم",
)
def trip_summary(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """كل الأولاد في الرحلة مع total charged, recovered, paid, remaining."""
    return SubscriptionService(db, current_user).get_trip_summary(trip_id)


@router.get(
    "/trip/{trip_id}/boy/{boy_id}/summary",
    response_model=BoyTripSummary,
    summary="ملخص ولد واحد في رحلة واحدة: دفع كام وباقي كام",
)
def boy_trip_summary(
    trip_id: int,
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ولد واحد في رحلة واحدة: كم دفع وكم تبقى عليه."""
    return SubscriptionService(db, current_user).get_boy_trip_summary(trip_id, boy_id)


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db, current_user).create(data)


@router.patch("/{sub_id}", response_model=SubscriptionResponse)
def update_subscription(
    sub_id: int,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db, current_user).update(sub_id, data)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    SubscriptionService(db, current_user).delete(sub_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
