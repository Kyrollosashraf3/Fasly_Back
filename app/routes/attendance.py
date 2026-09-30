from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.schemas.attend import (
    AttendBulkCreate,
    AttendCreate,
    AttendResponse,
    AttendUpdate,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("", response_model=AttendResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    data: AttendCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.post("/bulk", response_model=list[AttendResponse], status_code=status.HTTP_201_CREATED)
def create_attendance_bulk(
    data: AttendBulkCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("", response_model=list[AttendResponse])
def list_attendance(
    class_id: int | None = None,
    action_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("/{record_id}", response_model=AttendResponse)
def get_attendance(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.patch("/{record_id}", response_model=AttendResponse)
def update_attendance(
    record_id: int,
    data: AttendUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass
