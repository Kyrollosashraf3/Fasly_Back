from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import BoyService, ClassService, TeacherService
from app.db.database import get_db
from app.routes._excel import class_labels, label_for, writable_class_names, xlsx_response
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
    # lazy: openpyxl/csv only load when someone actually uploads
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


@router.get("", response_model=list[BoyResponse])
def list_boys(
    class_id: int | None = None,
    issue_flag: bool | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return BoyService(db, current_user).list(class_id=class_id, issue_flag=issue_flag)


@router.get("/template")
def boys_template(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """A ready-to-upload sample sheet (``class_name`` already filled)."""
    from app.core.EDA.templates import build_boys_template

    labels = class_labels(db, current_user)
    teachers_by_class: dict[str, list[str]] = {}
    for teacher in TeacherService(db, current_user).list():
        teachers_by_class.setdefault(labels.get(teacher.class_id, ""), []).append(
            teacher.teacher_name
        )
    content = build_boys_template(
        writable_class_names(db, current_user), teachers_by_class
    )
    return xlsx_response(content, "boys.xlsx")


@router.get("/export")
def boys_export(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Round-trip export: exactly the columns ``/boys/import`` accepts."""
    from app.core.EDA.templates import build_boys_export

    label = label_for(db, current_user)
    boys = BoyService(db, current_user).list(class_id=class_id)
    return xlsx_response(build_boys_export(boys, label), "boys.xlsx")


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
