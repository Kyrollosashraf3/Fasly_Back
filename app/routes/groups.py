from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.schemas.group import GroupAssign, GroupUnassign
from app.schemas.user import UserResponse

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("/assign")
def assign_group(
    data: GroupAssign,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.post("/unassign")
def unassign_group(
    data: GroupUnassign,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.post("/import")
def import_groups(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("")
def list_groups(
    class_id: int | None = None,
    teacher_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("/export")
def export_groups(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass
