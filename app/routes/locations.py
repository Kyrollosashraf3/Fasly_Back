"""House locations and the home-visit map (خريطة افتقاد المنازل)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import BoyLocationService, TeacherLocationService, VisitMapService
from app.db.database import get_db
from app.models.user import User
from app.schemas.location import (
    BoyLocationResponse,
    LocationRecord,
    MapRouteResponse,
    MapPersonTypeEnum,
    MapScopeEnum,
    TeacherLocationRecord,
    TeacherLocationResponse,
)

router = APIRouter(prefix="/locations", tags=["Locations & Visit Map"])


@router.get("/map", response_model=MapRouteResponse)
def visit_map(
    latitude: float | None = Query(None, ge=-90, le=90, description="موقع الخادم الآن"),
    longitude: float | None = Query(None, ge=-180, le=180),
    scope: MapScopeEnum = Query(MapScopeEnum.CLASS, description="group | class | all"),
    teacher_id: int | None = Query(None, description="لمجموعة خادم معين (للأمين)"),
    class_id: int | None = Query(None, description="تضييق أكثر على فصل واحد"),
    name: str | None = Query(None, max_length=100, description="بحث باسم الولد"),
    zone: str | None = Query(None, max_length=255, description="تصفية بالمنطقة"),
    address: str | None = Query(None, max_length=255, description="بحث تقريبي بالعنوان"),
    person_type: MapPersonTypeEnum = Query(
        MapPersonTypeEnum.BOYS, description="boys | teachers"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Filtered houses in scope + a nearest-first route from the caller's position."""
    return VisitMapService(db, current_user).route(
        latitude=latitude,
        longitude=longitude,
        scope=scope,
        teacher_id=teacher_id,
        class_id=class_id,
        name=name,
        zone=zone,
        address=address,
        person_type=person_type,
    )


@router.post(
    "/boys/me",
    response_model=BoyLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_my_location(
    data: LocationRecord,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The boy himself saves his own house location (future login flow)."""
    return BoyLocationService(db, current_user).record(None, data)


@router.post(
    "/boys/{boy_id}",
    response_model=BoyLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_boy_location(
    boy_id: int,
    data: LocationRecord,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Anyone allowed to see this boy saves a point while standing at his house."""
    return BoyLocationService(db, current_user).record(boy_id, data)


@router.post(
    "/teachers/{teacher_id}",
    response_model=TeacherLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_teacher_location(
    teacher_id: int,
    data: TeacherLocationRecord,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherLocationService(db, current_user).record(teacher_id, data)


@router.get("/boys/{boy_id}/current", response_model=BoyLocationResponse | None)
def current_boy_location(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The pin currently drawn for this boy, or ``null`` if never recorded."""
    return BoyLocationService(db, current_user).current(boy_id)
