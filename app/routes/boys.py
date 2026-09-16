from typing import List

from fastapi import APIRouter, Depends, status

from app.core.auth.deps import get_current_user
from app.core.data.boys import BoyService
from app.db.firebase import get_db
from app.models.boy import BoyCreate, BoyResponse, BoyUpdate
from app.models.enums import ClassEnum
from app.models.user import UserResponse

router = APIRouter(prefix="/boys", tags=["Boys"])


@router.post("", response_model=BoyResponse, status_code=status.HTTP_201_CREATED)
def create_boy(
    data: BoyCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Register a new boy.

    Admin: any class. Amin: only own class (auto-stamped)."""
    return BoyService(db, current_user).create(data)


@router.get("", response_model=List[BoyResponse])
def list_boys(
    class_name: ClassEnum | None = None,
    issue_flag: bool | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List boys, optionally filtered by class and/or issue flag.

    Admin: all (optional class filter). Amin: only own class."""
    return BoyService(db, current_user).list(class_name, issue_flag)


@router.get("/{boy_id}", response_model=BoyResponse)
def get_boy(
    boy_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a boy by ID.

    Admin: any. Amin: own class only."""
    return BoyService(db, current_user).get(boy_id)


@router.patch("/{boy_id}", response_model=BoyResponse)
def update_boy(
    boy_id: str,
    data: BoyUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a boy.

    Admin: any. Amin: own class only."""
    return BoyService(db, current_user).update(boy_id, data)


@router.delete("/{boy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boy(
    boy_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a boy. Admin: any. Amin: own class only."""
    BoyService(db, current_user).delete(boy_id)
