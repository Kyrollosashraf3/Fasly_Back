"""Trips - اشتراكات الفصول في الرحلات: إضافة، تعديل، حذف."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.trip.services import TripService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.trip.schemas.trip import TripCreate, TripResponse, TripUpdate

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.get("", response_model=list[TripResponse])
def list_trips(
    status_filter: str | None = Query('active', alias='status'),
    class_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripService(db, current_user).list(
        status=status_filter,
        class_id=class_id,
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    data: TripCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripService(db, current_user).create(data)


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripService(db, current_user).get(trip_id)


@router.patch("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: int,
    data: TripUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripService(db, current_user).update(trip_id, data)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TripService(db, current_user).delete(trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)