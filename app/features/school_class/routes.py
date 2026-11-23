"""Classes (الفصول) - the catalogue every scope resolves to."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import ClassService
from app.db.database import get_db
from app.models.user import User
from app.schemas.school_class import (
    SchoolClassCreate,
    SchoolClassResponse,
    SchoolClassUpdate,
)

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.get("", response_model=list[SchoolClassResponse])
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ClassService(db, current_user).list()


@router.post("", response_model=SchoolClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    data: SchoolClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ClassService(db, current_user).create(data)


@router.get("/{class_id}", response_model=SchoolClassResponse)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ClassService(db, current_user).get(class_id)


@router.patch("/{class_id}", response_model=SchoolClassResponse)
def update_class(
    class_id: int,
    data: SchoolClassUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ClassService(db, current_user).update(class_id, data)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ClassService(db, current_user).delete(class_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)