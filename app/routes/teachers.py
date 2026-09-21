from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.auth.deps import get_current_user
from app.core.data.teachers import TeacherService
from app.core.EDA.importer import run_import
from app.core.EDA.read_excel import read_teachers_workbook
from app.db.firebase import get_db
from app.models.enums import ClassEnum
from app.models.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.models.user import UserResponse

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    data: TeacherCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Register a new servant.

    Admin: any class. Amin: only own class (auto-stamped)."""
    return TeacherService(db, current_user).create(data)


@router.post("/import")
def import_teachers(
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Upload an .xlsx sheet and bulk-insert its rows into teachers.

    Sheet header must use the teachers column names:
    teacher_name | phone | class_name | duty | note
    (teacher_name + class_name required; empty rows skipped.)

    Admin: any class. Amin: only rows of his own class (others fail per-row).
    Returns {total_rows, created_count, failed_count, created, failed}.
    """
    return run_import(file, reader=read_teachers_workbook,
                      service=TeacherService(db, current_user), name_key="teacher_name")


@router.get("", response_model=list[TeacherResponse])
def list_teachers(
    class_name: ClassEnum | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List servants, optionally filtered by class.

    Admin: all (optional class filter). Amin: only own class."""
    return TeacherService(db, current_user).list(class_name)


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(
    teacher_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a servant by ID.

    Admin: any. Amin: own class only."""
    return TeacherService(db, current_user).get(teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherResponse)
def update_teacher(
    teacher_id: str,
    data: TeacherUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a servant.

    Admin: any. Amin: own class only."""
    return TeacherService(db, current_user).update(teacher_id, data)


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a servant. Admin: any. Amin: own class only."""
    TeacherService(db, current_user).delete(teacher_id)
