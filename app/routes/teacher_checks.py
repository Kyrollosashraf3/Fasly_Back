from datetime import date

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import TeacherCheckService
from app.db.database import get_db
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/teacher-checks", tags=["Teacher Checks"])


@router.post(
    "",
    response_model=TeacherCheckResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_teacher_check(
    data: TeacherCheckCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherCheckService(db, current_user).create(data)


@router.post(
    "/bulk",
    response_model=list[TeacherCheckResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_teacher_check_bulk(
    data: TeacherCheckBulkCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherCheckService(db, current_user).create_bulk(data)


@router.get("", response_model=list[TeacherCheckResponse])
def list_teacher_checks(
    class_id: int | None = None,
    action_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherCheckService(db, current_user).list(
        class_id=class_id, action_date=action_date
    )


@router.get("/{record_id}", response_model=TeacherCheckResponse)
def get_teacher_check(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherCheckService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=TeacherCheckResponse)
def update_teacher_check(
    record_id: int,
    data: TeacherCheckUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherCheckService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher_check(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    TeacherCheckService(db, current_user).delete(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
