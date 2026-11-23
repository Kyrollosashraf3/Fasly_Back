"""Servants (الخدام) - directory, spreadsheet template / import / export."""

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.features.school_class.services import ClassService
from app.features.teacher.services import TeacherService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.sheet.routes import label_for, writable_class_names, xlsx_response
from app.features.teacher.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.get("", response_model=list[TeacherResponse])
def list_teachers(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherService(db, current_user).list(class_id=class_id)


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    data: TeacherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherService(db, current_user).create(data)


@router.get("/template")
def teachers_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A ready-to-upload sample sheet with the class dropdown already filled."""
    from app.core.EDA.templates import build_teachers_template

    content = build_teachers_template(writable_class_names(db, current_user))
    return xlsx_response(content, "teachers.xlsx")


@router.get("/export")
def teachers_export(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.EDA.templates import build_teachers_export

    servants = TeacherService(db, current_user).list(class_id=class_id)
    return xlsx_response(
        build_teachers_export(servants, label_for(db, current_user)), "teachers.xlsx"
    )


@router.post("/import")
def import_teachers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.EDA.importer import run_import
    from app.core.EDA.read_excel import read_teachers_workbook

    classes = ClassService(db, current_user).label_lookup()
    return run_import(
        file,
        reader=lambda data: read_teachers_workbook(data, classes=classes),
        service=TeacherService(db, current_user),
        name_key="teacher_name",
    )


@router.get("/me", response_model=TeacherResponse)
def my_record(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The logged-in servant's own directory row - name, birth date, آخر اعتراف..."""
    return TeacherService(db, current_user).get_self()


@router.patch("/me", response_model=TeacherResponse)
def update_my_record(
    data: TeacherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A servant updating his own data. His phone and his class are locked."""
    return TeacherService(db, current_user).self_update(data)


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherService(db, current_user).get(teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherResponse)
def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeacherService(db, current_user).update(teacher_id, data)


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TeacherService(db, current_user).delete(teacher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)