"""Teams (الفرق) - CRUD for the team catalogue."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.db.database import get_db
from app.features.team.schemas.team import TeamCreate, TeamResponse, TeamUpdate
from app.features.team.services.team import TeamService
from app.features.user.models.user import User

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamResponse])
def list_teams(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService(db, current_user).list(class_id=class_id)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService(db, current_user).create(data)


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService(db, current_user).get(team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    data: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService(db, current_user).update(team_id, data)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TeamService(db, current_user).delete(team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
