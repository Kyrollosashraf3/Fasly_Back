"""Boys (الأولاد) - directory, spreadsheet template / import / export."""

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.DA.check import NameCheckService
from app.core.data import BoyService, ClassService, TeacherService
from app.db.database import get_db
from app.models.user import User
from app.routes.sheets import (
    class_labels,
    label_for,
    writable_class_names,
    xlsx_response,
)
from app.schemas.boy import BoyCreate, BoyResponse, BoyUpdate

router = APIRouter(prefix="/boys", tags=["Boys"])


@router.get("", response_model=list[BoyResponse])
def list_boys(
    class_id: int | None = None,
    issue_flag: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BoyService(db, current_user).list(class_id=class_id, issue_flag=issue_flag)


@router.post("", response_model=BoyResponse, status_code=status.HTTP_201_CREATED)
def create_boy(
    data: BoyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BoyService(db, current_user).create(data)


@router.get("/duplicate-names")
def duplicate_boy_names(
    threshold: int = Query(default=80, ge=50, le=100),
    scope: str = Query(default="all", pattern="^(same_class|diff_class|all)$"),
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Boys whose names look alike - the same child entered twice, once with a
    different spelling or under another class.

    ``threshold`` is the minimum similarity in percent, ``scope`` chooses which
    pairs count: one class, two different classes, or both."""
    return NameCheckService(db, current_user).duplicates(
        threshold=threshold, scope=scope, class_id=class_id
    )


@router.get("/template")
def boys_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A ready-to-upload sample sheet with the class dropdown already filled."""
    # lazy: openpyxl only loads when someone asks for a file
    from app.core.EDA.templates import build_boys_template

    labels = class_labels(db, current_user)
    servants_by_class: dict[str, list[str]] = {}
    for servant in TeacherService(db, current_user).list():
        servants_by_class.setdefault(labels.get(servant.class_id, ""), []).append(
            servant.teacher_name
        )
    content = build_boys_template(
        writable_class_names(db, current_user), servants_by_class
    )
    return xlsx_response(content, "boys.xlsx")


@router.get("/export")
def boys_export(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Round-trip export: exactly the columns ``/boys/import`` accepts."""
    from app.core.EDA.templates import build_boys_export

    boys = BoyService(db, current_user).list(class_id=class_id)
    return xlsx_response(
        build_boys_export(boys, label_for(db, current_user)), "boys.xlsx"
    )


@router.post("/import")
def import_boys(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk create / refresh boys from a sheet (``class_name`` + ``boy_name``)."""
    from app.core.EDA.importer import run_import
    from app.core.EDA.read_excel import read_boys_workbook, teacher_lookup

    classes = ClassService(db, current_user).label_lookup()
    servants = teacher_lookup(TeacherService(db, current_user).list())
    return run_import(
        file,
        reader=lambda data: read_boys_workbook(
            data, classes=classes, teachers=servants
        ),
        service=BoyService(db, current_user),
        name_key="boy_name",
    )


@router.get("/{boy_id}", response_model=BoyResponse)
def get_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BoyService(db, current_user).get(boy_id)


@router.patch("/{boy_id}", response_model=BoyResponse)
def update_boy(
    boy_id: int,
    data: BoyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BoyService(db, current_user).update(boy_id, data)


@router.delete("/{boy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boy(
    boy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    BoyService(db, current_user).delete(boy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)