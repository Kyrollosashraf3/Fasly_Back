from datetime import date
from typing import List

from fastapi import APIRouter, Depends, status

from app.core.auth.deps import get_current_user
from app.core.data.follow_ups import FollowUpService
from app.db.firebase import get_db
from app.models.enums import ClassEnum
from app.models.follow_up import FollowUpCreate, FollowUpResponse, FollowUpUpdate
from app.models.user import UserResponse

router = APIRouter(prefix="/follow-ups", tags=["Follow Ups"])


@router.post("", response_model=FollowUpResponse, status_code=status.HTTP_201_CREATED)
def create_follow_up(
    data: FollowUpCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Log a weekly follow-up call from a servant to a boy.

    Admin: any class. Amin: only own class (resolved from the boy)."""
    return FollowUpService(db, current_user).create(data)


@router.get("", response_model=List[FollowUpResponse])
def list_follow_ups(
    class_name: ClassEnum | None = None,
    teacher_id: str | None = None,
    boy_id: str | None = None,
    action_date: date | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List follow-ups, optionally filtered by class / servant / boy / date.

    Admin: all. Amin: only own class."""
    return FollowUpService(db, current_user).list(class_name, teacher_id, boy_id, action_date)


@router.get("/{record_id}", response_model=FollowUpResponse)
def get_follow_up(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a follow-up by ID.

    Admin: any. Amin: own class only."""
    return FollowUpService(db, current_user).get(record_id)


@router.patch("/{record_id}", response_model=FollowUpResponse)
def update_follow_up(
    record_id: str,
    data: FollowUpUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a follow-up.

    Admin: any. Amin: own class only."""
    return FollowUpService(db, current_user).update(record_id, data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_follow_up(
    record_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a follow-up. Admin: any. Amin: own class only."""
    FollowUpService(db, current_user).delete(record_id)
