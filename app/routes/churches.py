"""Churches (الكنائس) - platform tenants.

A tenant user only ever sees his own church; creating and suspending tenants
is reserved for the platform owner (enforced in ``ChurchService``).
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import ChurchService
from app.db.database import get_db
from app.models.user import User
from app.schemas.church import ChurchCreate, ChurchResponse, ChurchUpdate

router = APIRouter(prefix="/churches", tags=["Churches"])


@router.get("", response_model=list[ChurchResponse])
def list_churches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ChurchService(db, current_user).list()


@router.post("", response_model=ChurchResponse, status_code=status.HTTP_201_CREATED)
def create_church(
    data: ChurchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ChurchService(db, current_user).create(data)


@router.get("/{church_id}", response_model=ChurchResponse)
def get_church(
    church_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ChurchService(db, current_user).get(church_id)


@router.patch("/{church_id}", response_model=ChurchResponse)
def update_church(
    church_id: int,
    data: ChurchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ChurchService(db, current_user).update(church_id, data)


@router.delete("/{church_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_church(
    church_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ChurchService(db, current_user).delete(church_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
