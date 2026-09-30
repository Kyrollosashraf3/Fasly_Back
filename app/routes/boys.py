from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import BoyService, ClassService
from app.core.EDA.importer import run_import
from app.core.EDA.read_excel import read_boys_workbook
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
    return BoyService(db, current_user).create(data)


@router.post("/import")
def import_boys(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    classes = ClassService(db, current_user).label_lookup()
    return run_import(
        file,
        reader=lambda data: read_boys_workbook(data, classes=classes),
        service=BoyService(db, current_user),
        name_key="boy_name",
    )


@router.get("", response_model=list[BoyResponse])
def list_boys(
    class_id: int | None = None,
    issue_flag: bool | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return BoyService(db, current_user).list(class_id=class_id, issue_flag=issue_flag)


@router.get("/{boy_id}", response_model=BoyResponse)
def get_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return BoyService(db, current_user).get(boy_id)


@router.patch("/{boy_id}", response_model=BoyResponse)
def update_boy(
    boy_id: int,
    data: BoyUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return BoyService(db, current_user).update(boy_id, data)


@router.delete("/{boy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    BoyService(db, current_user).delete(boy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
