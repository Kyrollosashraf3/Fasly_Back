from datetime import date

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.teacher_follow_up.services import TeacherFollowUpService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.teacher_follow_up.schemas.teacher_follow_up import (
    TeacherFollowUpCreate,
    TeacherFollowUpResponse,
    TeacherFollowUpUpdate,
)

router = APIRouter(prefix="/teacher-follow-ups", tags=["Teacher Follow Ups"])


@router.get("", response_model=list[TeacherFollowUpResponse])
def list_teacher_follow_ups(
    class_id: int | None = None,
    teacher_id: int | None = None,
    action_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherFollowUpService(db, current_user).list(
        class_id=class_id,
        teacher_id=teacher_id,
        action_date=action_date,
    )


@router.post(
    "", response_model=TeacherFollowUpResponse, status_code=status.HTTP_201_CREATED
)
def create_teacher_follow_up(
    data: TeacherFollowUpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherFollowUpService(db, current_user).create(data)


@router.get("/{record_id}", response_model=TeacherFollowUpResponse)
def get_teacher_follow_up(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherFollowUpService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=TeacherFollowUpResponse)
def update_teacher_follow_up(
    record_id: int,
    data: TeacherFollowUpUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherFollowUpService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher_follow_up(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TeacherFollowUpService(db, current_user).delete(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
