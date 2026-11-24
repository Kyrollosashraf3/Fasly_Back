"""Boys assigned to a team (أولاد الفريق)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_boy_access,
    ensure_manager,
    ensure_staff,
    get_or_404,
    my_class_ids,
    scope_church,
    scoped_team,
)
from app.features.boy.models.boy import Boy
from app.features.team.models.team import Team
from app.features.team.models.team_member import TeamMember
from app.features.team.schemas.team_member import (
    TeamMemberBulkCreate,
    TeamMemberCreate,
    TeamMemberUnassign,
    TeamMemberUpdate,
)


class TeamMemberService(BaseService):
    """read : staff inside the team's church/class scope
    write: any amin inside the same scope
    """

    def query(self) -> Query:
        ensure_staff(self.user)
        query = scope_church(
            self.db.query(TeamMember), TeamMember, self.user
        ).join(Team, TeamMember.team_id == Team.id)
        mine = my_class_ids(self.db, self.user)
        return query if mine is None else query.filter(Team.class_id.in_(mine))

    def list(self, team_id: int | None = None, boy_id: int | None = None) -> list[TeamMember]:
        query = self.query()
        if team_id is not None:
            self._team(team_id)  # 404 when the team is outside this scope
            query = query.filter(TeamMember.team_id == team_id)
        if boy_id is not None:
            query = query.filter(TeamMember.boy_id == boy_id)
        return query.order_by(TeamMember.id).all()

    def get(self, row_id: int) -> TeamMember:
        row = self.query().filter(TeamMember.id == row_id).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team member {row_id} not found.",
            )
        return row

    def create(self, data: TeamMemberCreate) -> TeamMember:
        ensure_manager(self.user)
        team = self._team(data.team_id)
        boy = self._boy(data.boy_id, team)
        row = TeamMember(
            team_id=team.id,
            boy_id=boy.id,
            church_id=self.church_for(class_id=team.class_id, person=boy),
        )
        self.db.add(row)
        commit(self.db, f"Team member add team={team.id} boy={boy.id}")
        return row

    def bulk(self, data: TeamMemberBulkCreate) -> dict:
        """Add the boys who are not in the team yet; duplicates are skipped."""
        ensure_manager(self.user)
        team = self._team(data.team_id)
        wanted = list(dict.fromkeys(data.boy_ids))
        added = 0
        for boy_id in wanted:
            boy = self._boy(boy_id, team)
            exists = (
                self.db.query(TeamMember.id)
                .filter(TeamMember.team_id == team.id, TeamMember.boy_id == boy.id)
                .first()
            )
            if exists is not None:
                continue
            self.db.add(
                TeamMember(
                    team_id=team.id,
                    boy_id=boy.id,
                    church_id=self.church_for(class_id=team.class_id, person=boy),
                )
            )
            added += 1
        commit(self.db, f"Team member bulk team={team.id} added={added}")
        return {
            "team_id": team.id,
            "requested": len(data.boy_ids),
            "added": added,
            "skipped": len(data.boy_ids) - added,
        }

    def update(self, row_id: int, data: TeamMemberUpdate) -> TeamMember:
        row = self.get(row_id)
        ensure_manager(self.user)
        team = self._team(data.team_id) if data.team_id is not None else self._team(row.team_id)
        boy_id = data.boy_id if data.boy_id is not None else row.boy_id
        boy = self._boy(boy_id, team)
        apply_update(row, data)
        row.team_id = team.id
        row.boy_id = boy.id
        row.church_id = team.church_id
        commit(self.db, f"Team member update id={row_id}")
        return row

    def unassign(self, data: TeamMemberUnassign) -> dict:
        """Remove boys from one team, or from every team in this scope."""
        ensure_manager(self.user)
        team = self._team(data.team_id) if data.team_id is not None else None
        removed = 0
        for boy_id in dict.fromkeys(data.boy_ids):
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            ensure_boy_access(self.db, self.user, boy)
            query = self.query().filter(TeamMember.boy_id == boy.id)
            if team is not None:
                query = query.filter(TeamMember.team_id == team.id)
            for row in query.all():
                self.db.delete(row)
                removed += 1
        commit(self.db, f"Team member unassign removed={removed}")
        return {"removed": removed}

    def delete(self, row_id: int) -> None:
        row = self.get(row_id)
        ensure_manager(self.user)
        self.db.delete(row)
        commit(self.db, f"Team member delete id={row_id}")

    # -------------------------------------------------------------- internals
    def _team(self, team_id: int) -> Team:
        scope = scoped_team(self.db, self.user, team_id)
        if scope is None:  # pragma: no cover - called only with a real id
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team {team_id} not found.",
            )
        return get_or_404(self.db, Team, scope.team_id, "Team")

    def _boy(self, boy_id: int, team: Team) -> Boy:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_boy_access(self.db, self.user, boy)
        if boy.church_id != team.church_id or boy.class_id != team.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Boy '{boy.boy_name}' is not in that team's church/class.",
            )
        return boy
