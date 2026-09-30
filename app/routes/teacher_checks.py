from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/teacher-checks", tags=["Teacher Checks"])


@router.post("", response_model=TeacherCheckResponse, status_code=status.HTTP_201_CREATED)
def create_teacher_check(
    data: TeacherCheckCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.post("/bulk", response_model=list[TeacherCheckResponse], status_code=status.HTTP_201_CREATED)
def create_teacher_check_bulk(
    data: TeacherCheckBulkCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("", response_model=list[TeacherCheckResponse])
def list_teacher_checks(
    class_id: int | None = None,
    action_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("/{record_id}", response_model=TeacherCheckResponse)
def get_teacher_check(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.patch("/{record_id}", response_model=TeacherCheckResponse)
def update_teacher_check(
    record_id: int,
    data: TeacherCheckUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher_check(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass
