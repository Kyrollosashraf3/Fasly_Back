"""Boys in a team (أولاد الفريق)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.features.team.schemas.team_member import (
    TeamMemberBulkCreate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberUnassign,
    TeamMemberUpdate,
)
from app.features.team.services.team_member import TeamMemberService
from app.features.user.models.user import User

router = APIRouter(prefix="/team-members", tags=["Team members"])


@router.get("", response_model=list[TeamMemberResponse])
def list_team_members(
    team_id: int | None = None,
    boy_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).list(team_id=team_id, boy_id=boy_id)


@router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
def create_team_member(
    data: TeamMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).create(data)


@router.post("/bulk")
def bulk_create_team_members(
    data: TeamMemberBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).bulk(data)


@router.post("/unassign")
def unassign_team_members(
    data: TeamMemberUnassign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).unassign(data)


@router.get("/{row_id}", response_model=TeamMemberResponse)
def get_team_member(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).get(row_id)


@router.patch("/{row_id}", response_model=TeamMemberResponse)
def update_team_member(
    row_id: int,
    data: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamMemberService(db, current_user).update(row_id, data)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TeamMemberService(db, current_user).delete(row_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
