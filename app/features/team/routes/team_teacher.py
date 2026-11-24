"""Servants in a team (خدم الفريق)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.features.team.schemas.team_teacher import (
    TeamTeacherBulkCreate,
    TeamTeacherCreate,
    TeamTeacherResponse,
    TeamTeacherUnassign,
    TeamTeacherUpdate,
)
from app.features.team.services.team_teacher import TeamTeacherService
from app.features.user.models.user import User

router = APIRouter(prefix="/team-teachers", tags=["Team teachers"])


@router.get("", response_model=list[TeamTeacherResponse])
def list_team_teachers(
    team_id: int | None = None,
    teacher_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).list(
        team_id=team_id, teacher_id=teacher_id
    )


@router.post("", response_model=TeamTeacherResponse, status_code=status.HTTP_201_CREATED)
def create_team_teacher(
    data: TeamTeacherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).create(data)


@router.post("/bulk")
def bulk_create_team_teachers(
    data: TeamTeacherBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).bulk(data)


@router.post("/unassign")
def unassign_team_teachers(
    data: TeamTeacherUnassign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).unassign(data)


@router.get("/{row_id}", response_model=TeamTeacherResponse)
def get_team_teacher(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).get(row_id)


@router.patch("/{row_id}", response_model=TeamTeacherResponse)
def update_team_teacher(
    row_id: int,
    data: TeamTeacherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamTeacherService(db, current_user).update(row_id, data)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_teacher(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TeamTeacherService(db, current_user).delete(row_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
