from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import ClassService, TeacherService
from app.db.database import get_db
from app.routes._excel import label_for, writable_class_names, xlsx_response
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.schemas.user import UserResponse

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    data: TeacherCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherService(db, current_user).create(data)


@router.post("/import")
def import_teachers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    # lazy: openpyxl/csv only load when someone actually uploads
    from app.core.EDA.importer import run_import
    from app.core.EDA.read_excel import read_teachers_workbook

    classes = ClassService(db, current_user).label_lookup()
    return run_import(
        file,
        reader=lambda data: read_teachers_workbook(data, classes=classes),
        service=TeacherService(db, current_user),
        name_key="teacher_name",
    )


@router.get("", response_model=list[TeacherResponse])
def list_teachers(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherService(db, current_user).list(class_id=class_id)


@router.get("/template")
def teachers_template(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """A ready-to-upload sample sheet (``class_name`` already filled)."""
    from app.core.EDA.templates import build_teachers_template

    content = build_teachers_template(writable_class_names(db, current_user))
    return xlsx_response(content, "teachers.xlsx")


@router.get("/export")
def teachers_export(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    from app.core.EDA.templates import build_teachers_export

    label = label_for(db, current_user)
    teachers = TeacherService(db, current_user).list(class_id=class_id)
    return xlsx_response(build_teachers_export(teachers, label), "teachers.xlsx")


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherService(db, current_user).get(teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherResponse)
def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return TeacherService(db, current_user).update(teacher_id, data)


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    TeacherService(db, current_user).delete(teacher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
