from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.schemas.boy import BoyCreate, BoyResponse, BoyUpdate
from app.schemas.user import UserResponse

router = APIRouter(prefix="/boys", tags=["Boys"])


@router.post("", response_model=BoyResponse, status_code=status.HTTP_201_CREATED)
def create_boy(
    data: BoyCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.post("/import")
def import_boys(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("", response_model=list[BoyResponse])
def list_boys(
    class_id: int | None = None,
    issue_flag: bool | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.get("/{boy_id}", response_model=BoyResponse)
def get_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.patch("/{boy_id}", response_model=BoyResponse)
def update_boy(
    boy_id: int,
    data: BoyUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass


@router.delete("/{boy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    pass
