"""تسميعات المسابقات: تسجيل التسميع، وعلامات الاستلام في المستحقات."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import TaskValueService
from app.db.database import get_db
from app.models.user import User
from app.schemas.task_value import (
    TaskValueCreate,
    TaskValueDuesBulk,
    TaskValueResponse,
    TaskValueUpdate,
)

router = APIRouter(prefix="/task-values", tags=["Task values"])


@router.get("", response_model=list[TaskValueResponse])
def list_task_values(
    task_id: int | None = Query(None),
    received: bool | None = Query(None),
    class_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskValueService(db, current_user).list(
        task_id=task_id,
        received=received,
        class_id=class_id,
    )


@router.post(
    "",
    response_model=TaskValueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_value(
    data: TaskValueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskValueService(db, current_user).create(data)


# Declared before /{value_id} so "bulk" is never read as a record id.
@router.patch("/bulk", response_model=list[TaskValueResponse])
def save_task_value_dues(
    data: TaskValueDuesBulk,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حفظ صفحة المستحقات كلها في معاملة واحدة."""
    return TaskValueService(db, current_user).save_dues(data)


@router.get("/{value_id}", response_model=TaskValueResponse)
def get_task_value(
    value_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskValueService(db, current_user).get(value_id)


@router.patch("/{value_id}", response_model=TaskValueResponse)
def update_task_value(
    value_id: int,
    data: TaskValueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskValueService(db, current_user).update(value_id, data)


@router.delete("/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_value(
    value_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TaskValueService(db, current_user).delete(value_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
