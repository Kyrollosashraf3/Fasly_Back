"""كشف حضور الرحلة: من حضر من الأولاد، ومين الخادم المسئول عن كل مجموعة."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.trip_attendance.services import TripAttendanceService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.trip_attendance.schemas.trip_attendance import (
    TripAttendanceAssign,
    TripAttendanceBulkCreate,
    TripAttendanceResponse,
    TripAttendanceUnassign,
    TripAttendanceUpdate,
    TripSheetResponse,
)

router = APIRouter(prefix="/trip-attendance", tags=["Trip attendance"])


@router.get("", response_model=list[TripAttendanceResponse])
def list_trip_attendance(
    trip_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """كل الصفوف ضمن نطاق الدخول، مع إمكانية التصفية على رحلة واحدة."""
    return TripAttendanceService(db, current_user).list(trip_id=trip_id)


@router.get("/sheet/{trip_id}", response_model=TripSheetResponse)
def trip_sheet(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """كشف الرحلة: كل أولاد الفصل + حضورهم + الخادم المسئول عن كل واحد."""
    return TripAttendanceService(db, current_user).sheet(trip_id)


@router.get("/{row_id}", response_model=TripAttendanceResponse)
def get_trip_attendance(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripAttendanceService(db, current_user).get(row_id)


@router.post("/{trip_id}/attendance", response_model=list[TripAttendanceResponse])
def save_trip_attendance(
    trip_id: int,
    data: TripAttendanceBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حفظ كشف الحضور لرحلة كاملة في عملية واحدة (تحديث أو إنشاء لكل ولد)."""
    return TripAttendanceService(db, current_user).save_attendance(trip_id, data)


@router.post("/{trip_id}/assign")
def assign_trip_group(
    trip_id: int,
    data: TripAttendanceAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """توزيع مجموعة أولاد على خادم واحد داخل الرحلة."""
    return TripAttendanceService(db, current_user).assign(
        trip_id, data.teacher_id, data.boy_ids
    )


@router.post("/{trip_id}/unassign")
def unassign_trip_group(
    trip_id: int,
    data: TripAttendanceUnassign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripAttendanceService(db, current_user).unassign(trip_id, data.boy_ids)


@router.patch("/{row_id}", response_model=TripAttendanceResponse)
def update_trip_attendance(
    row_id: int,
    data: TripAttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TripAttendanceService(db, current_user).update(row_id, data)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_attendance(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TripAttendanceService(db, current_user).delete(row_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
