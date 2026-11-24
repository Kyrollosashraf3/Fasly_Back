"""Teams (الفرق) - the catalogue the other modules filter by."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_manager,
    ensure_staff,
    normalise_name,
    scope_classes,
)
from app.features.team.models.team import Team
from app.features.team.schemas.team import TeamCreate, TeamUpdate


class TeamService(BaseService):
    """read : every staff login, inside its church/class scope
    write: any amin (manager) inside the same scope
    """

    def query(self) -> Query:
        ensure_staff(self.user)
        return scope_classes(self.db, self.db.query(Team), Team, self.user)

    def list(self, class_id: int | None = None) -> list[Team]:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Team.class_id == class_id)
        return query.order_by(Team.team_name, Team.id).all()

    def get(self, team_id: int) -> Team:
        team = self.query().filter(Team.id == team_id).first()
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team {team_id} not found.",
            )
        return team

    def create(self, data: TeamCreate) -> Team:
        ensure_manager(self.user)
        self.ensure_class(data.class_id)
        church_id = self.church_for(
            getattr(data, "church_id", None), class_id=data.class_id
        )
        self._ensure_name_free(data.team_name, data.class_id, church_id)
        team = Team(
            team_name=data.team_name.strip(),
            class_id=data.class_id,
            church_id=church_id,
        )
        self.db.add(team)
        commit(self.db, f"Team create name={data.team_name} class={data.class_id}")
        return team

    def update(self, team_id: int, data: TeamUpdate) -> Team:
        team = self.get(team_id)
        ensure_manager(self.user)

        new_class_id = data.class_id if data.class_id is not None else team.class_id
        requested_church_id = getattr(data, "church_id", None)
        if new_class_id != team.class_id:
            self.ensure_class(new_class_id)
        new_church_id = (
            self.church_for(requested_church_id, class_id=new_class_id)
            if requested_church_id is not None or new_class_id != team.class_id
            else team.church_id
        )
        if new_class_id != team.class_id or new_church_id != team.church_id:
            if team.members or team.teachers:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Move the team's boys and servants out first.",
                )

        new_name = data.team_name if data.team_name is not None else team.team_name
        self._ensure_name_free(
            new_name, new_class_id, new_church_id, exclude_id=team.id
        )
        apply_update(team, data, skip=("church_id",), strip=("team_name",))
        team.class_id = new_class_id
        team.church_id = new_church_id
        commit(self.db, f"Team update id={team_id}")
        return team

    def delete(self, team_id: int) -> None:
        team = self.get(team_id)
        ensure_manager(self.user)
        self.db.delete(team)
        commit(self.db, f"Team delete id={team_id}")

    def _ensure_name_free(
        self,
        team_name: str,
        class_id: int,
        church_id: int,
        *,
        exclude_id: int | None = None,
    ) -> None:
        """Names are unique inside one church + class, ignoring case/whitespace."""
        wanted = normalise_name(team_name)
        query = self.db.query(Team).filter(
            Team.church_id == church_id,
            Team.class_id == class_id,
        )
        if exclude_id is not None:
            query = query.filter(Team.id != exclude_id)
        for row in query.all():
            if normalise_name(row.team_name) == wanted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Team: '{team_name}' already exists in that class.",
                )
