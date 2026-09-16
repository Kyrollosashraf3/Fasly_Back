from datetime import date
from typing import List

from fastapi import APIRouter, Depends, status

from app.core.auth.deps import get_current_user
from app.core.data.teacher_checks import TeacherCheckService
from app.db.firebase import get_db
from app.models.enums import ClassEnum
from app.models.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from app.models.user import UserResponse

router = APIRouter(prefix="/teacher-checks", tags=["Teacher Checks"])


@router.post("", response_model=TeacherCheckResponse, status_code=status.HTTP_201_CREATED)
def create_teacher_check(
    data: TeacherCheckCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Record the weekly check on one servant (upsert on teacher + date).

    Admin: any class. Amin: only own class."""
    return TeacherCheckService(db, current_user).create(data)


@router.post("/bulk", response_model=List[TeacherCheckResponse], status_code=status.HTTP_201_CREATED)
def create_teacher_check_bulk(
    data: TeacherCheckBulkCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Friday flow: all servants' checks in one request.

    Admin: any class. Amin: only own class."""
    return TeacherCheckService(db, current_user).create_bulk(data)


@router.get("", response_model=List[TeacherCheckResponse])
def list_teacher_checks(
    class_name: ClassEnum | None = None,
    action_date: date | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List checks, optionally filtered by class and/or date.

    Admin: all. Amin: only own class."""
    return TeacherCheckService(db, current_user).list(class_name, action_date)


@router.get("/{record_id}", response_model=TeacherCheckResponse)
def get_teacher_check(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a check by ID.

    Admin: any. Amin: own class only."""
    return TeacherCheckService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=TeacherCheckResponse)
def update_teacher_check(
    record_id: str,
    data: TeacherCheckUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a check.

    Admin: any. Amin: own class only."""
    return TeacherCheckService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher_check(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a check. Admin: any. Amin: own class only."""
    TeacherCheckService(db, current_user).delete(record_id)
