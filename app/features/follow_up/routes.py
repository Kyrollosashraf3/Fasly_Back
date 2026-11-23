"""Follow-up log - one row per contact a servant logs with one boy."""

from datetime import date

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.follow_up.services import FollowUpService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.follow_up.schemas.follow_up import FollowUpCreate, FollowUpResponse, FollowUpUpdate

router = APIRouter(prefix="/follow-ups", tags=["Follow Ups"])


@router.get("", response_model=list[FollowUpResponse])
def list_follow_ups(
    class_id: int | None = None,
    teacher_id: int | None = None,
    boy_id: int | None = None,
    action_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FollowUpService(db, current_user).list(
        class_id=class_id,
        teacher_id=teacher_id,
        boy_id=boy_id,
        action_date=action_date,
    )


@router.post("", response_model=FollowUpResponse, status_code=status.HTTP_201_CREATED)
def create_follow_up(
    data: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FollowUpService(db, current_user).create(data)


@router.get("/{record_id}", response_model=FollowUpResponse)
def get_follow_up(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FollowUpService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=FollowUpResponse)
def update_follow_up(
    record_id: int,
    data: FollowUpUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FollowUpService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_follow_up(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    FollowUpService(db, current_user).delete(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)