from datetime import date
from typing import List

from fastapi import APIRouter, Depends, status

from app.core.auth.deps import get_current_user
from app.core.data.attendance import AttendanceService
from app.db.firebase import get_db
from app.models.attend import (
    AttendBulkCreate,
    AttendCreate,
    AttendResponse,
    AttendUpdate,
)
from app.models.enums import ClassEnum
from app.models.user import UserResponse

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("", response_model=AttendResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    data: AttendCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Record one boy's attendance (upsert on boy + date).

    Admin: any class. Amin: only own class."""
    return AttendanceService(db, current_user).create(data)


@router.post("/bulk", response_model=List[AttendResponse], status_code=status.HTTP_201_CREATED)
def create_attendance_bulk(
    data: AttendBulkCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Friday flow: whole class attendance in one request.

    Admin: any class. Amin: only own class."""
    return AttendanceService(db, current_user).create_bulk(data)


@router.get("", response_model=List[AttendResponse])
def list_attendance(
    class_name: ClassEnum | None = None,
    action_date: date | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List attendance records, optionally filtered by class and/or date.

    Admin: all. Amin: only own class."""
    return AttendanceService(db, current_user).list(class_name, action_date)


@router.get("/{record_id}", response_model=AttendResponse)
def get_attendance(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get an attendance record by ID.

    Admin: any. Amin: own class only."""
    return AttendanceService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=AttendResponse)
def update_attendance(
    record_id: str,
    data: AttendUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update an attendance record.

    Admin: any. Amin: own class only."""
    return AttendanceService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete an attendance record. Admin: any. Amin: own class only."""
    AttendanceService(db, current_user).delete(record_id)
