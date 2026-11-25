"""Church-wide servant trip routes."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.features.servant_trip.schemas.servant_trip import (
    ServantTripCreate,
    ServantTripResponse,
    ServantTripUpdate,
)
from app.features.servant_trip.schemas.servant_trip_subscription import (
    ServantTripSubscriptionCreate,
    ServantTripSubscriptionResponse,
    ServantTripSubscriptionUpdate,
    ServantTripSummary,
    ServantTripTotal,
)
from app.features.servant_trip.services import (
    ServantTripService,
    ServantTripSubscriptionService,
)
from app.features.user.models.user import User

trips_router = APIRouter(prefix="/servant-trips", tags=["Servant trips"])
subscriptions_router = APIRouter(
    prefix="/servant-trip-subscriptions", tags=["Servant trip subscriptions"]
)


@trips_router.get("", response_model=list[ServantTripResponse])
def list_servant_trips(
    status_filter: str | None = Query("active", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripService(db, current_user).list(status_filter)


@trips_router.post(
    "", response_model=ServantTripResponse, status_code=status.HTTP_201_CREATED
)
def create_servant_trip(
    data: ServantTripCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripService(db, current_user).create(data)


@trips_router.get("/{trip_id}", response_model=ServantTripResponse)
def get_servant_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripService(db, current_user).get(trip_id)


@trips_router.patch("/{trip_id}", response_model=ServantTripResponse)
def update_servant_trip(
    trip_id: int,
    data: ServantTripUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripService(db, current_user).update(trip_id, data)


@trips_router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_servant_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ServantTripService(db, current_user).delete(trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@subscriptions_router.get(
    "", response_model=list[ServantTripSubscriptionResponse]
)
def list_servant_trip_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).list()


@subscriptions_router.get(
    "/trip/{trip_id}", response_model=list[ServantTripSubscriptionResponse]
)
def list_subscriptions_for_servant_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).get_for_trip(trip_id)


@subscriptions_router.get(
    "/trip/{trip_id}/summary", response_model=list[ServantTripSummary]
)
def servant_trip_summary(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).get_trip_summary(trip_id)


@subscriptions_router.get(
    "/trip/{trip_id}/servants", response_model=list[ServantTripTotal]
)
def servant_trip_totals(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).get_totals(trip_id)


@subscriptions_router.get(
    "/trip/{trip_id}/servant/{teacher_id}/summary",
    response_model=ServantTripSummary,
)
def servant_trip_servant_summary(
    trip_id: int,
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).get_servant_summary(
        trip_id, teacher_id
    )


@subscriptions_router.post(
    "",
    response_model=ServantTripSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_servant_trip_subscription(
    data: ServantTripSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).create(data)


@subscriptions_router.patch(
    "/{subscription_id}", response_model=ServantTripSubscriptionResponse
)
def update_servant_trip_subscription(
    subscription_id: int,
    data: ServantTripSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ServantTripSubscriptionService(db, current_user).update(
        subscription_id, data
    )


@subscriptions_router.delete(
    "/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_servant_trip_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ServantTripSubscriptionService(db, current_user).delete(subscription_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
