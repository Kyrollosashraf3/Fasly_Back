"""Servants assigned to a team (خدم الفريق)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_manager,
    ensure_staff,
    ensure_teacher_access,
    get_or_404,
    my_class_ids,
    scope_church,
    scoped_team,
)
from app.features.team.models.team import Team
from app.features.team.models.team_teacher import TeamTeacher
from app.features.team.schemas.team_teacher import (
    TeamTeacherBulkCreate,
    TeamTeacherCreate,
    TeamTeacherUnassign,
    TeamTeacherUpdate,
)
from app.features.teacher.models.teacher import Teacher


class TeamTeacherService(BaseService):
    """read : staff inside the team's church/class scope
    write: any amin inside the same scope
    """

    def query(self) -> Query:
        ensure_staff(self.user)
        query = scope_church(
            self.db.query(TeamTeacher), TeamTeacher, self.user
        ).join(Team, TeamTeacher.team_id == Team.id)
        mine = my_class_ids(self.db, self.user)
        return query if mine is None else query.filter(Team.class_id.in_(mine))

    def list(
        self, team_id: int | None = None, teacher_id: int | None = None
    ) -> list[TeamTeacher]:
        query = self.query()
        if team_id is not None:
            self._team(team_id)
            query = query.filter(TeamTeacher.team_id == team_id)
        if teacher_id is not None:
            query = query.filter(TeamTeacher.teacher_id == teacher_id)
        return query.order_by(TeamTeacher.id).all()

    def get(self, row_id: int) -> TeamTeacher:
        row = self.query().filter(TeamTeacher.id == row_id).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team teacher {row_id} not found.",
            )
        return row

    def create(self, data: TeamTeacherCreate) -> TeamTeacher:
        ensure_manager(self.user)
        team = self._team(data.team_id)
        servant = self._teacher(data.teacher_id, team)
        row = TeamTeacher(
            team_id=team.id,
            teacher_id=servant.id,
            church_id=self.church_for(class_id=team.class_id, person=servant),
        )
        self.db.add(row)
        commit(self.db, f"Team teacher add team={team.id} teacher={servant.id}")
        return row

    def bulk(self, data: TeamTeacherBulkCreate) -> dict:
        ensure_manager(self.user)
        team = self._team(data.team_id)
        wanted = list(dict.fromkeys(data.teacher_ids))
        added = 0
        for teacher_id in wanted:
            servant = self._teacher(teacher_id, team)
            exists = (
                self.db.query(TeamTeacher.id)
                .filter(
                    TeamTeacher.team_id == team.id,
                    TeamTeacher.teacher_id == servant.id,
                )
                .first()
            )
            if exists is not None:
                continue
            self.db.add(
                TeamTeacher(
                    team_id=team.id,
                    teacher_id=servant.id,
                    church_id=self.church_for(class_id=team.class_id, person=servant),
                )
            )
            added += 1
        commit(self.db, f"Team teacher bulk team={team.id} added={added}")
        return {
            "team_id": team.id,
            "requested": len(data.teacher_ids),
            "added": added,
            "skipped": len(data.teacher_ids) - added,
        }

    def update(self, row_id: int, data: TeamTeacherUpdate) -> TeamTeacher:
        row = self.get(row_id)
        ensure_manager(self.user)
        team = (
            self._team(data.team_id)
            if data.team_id is not None
            else self._team(row.team_id)
        )
        teacher_id = data.teacher_id if data.teacher_id is not None else row.teacher_id
        servant = self._teacher(teacher_id, team)
        apply_update(row, data)
        row.team_id = team.id
        row.teacher_id = servant.id
        row.church_id = team.church_id
        commit(self.db, f"Team teacher update id={row_id}")
        return row

    def unassign(self, data: TeamTeacherUnassign) -> dict:
        ensure_manager(self.user)
        team = self._team(data.team_id) if data.team_id is not None else None
        removed = 0
        for teacher_id in dict.fromkeys(data.teacher_ids):
            servant = get_or_404(self.db, Teacher, teacher_id, "Servant")
            ensure_teacher_access(self.db, self.user, servant)
            query = self.query().filter(TeamTeacher.teacher_id == servant.id)
            if team is not None:
                query = query.filter(TeamTeacher.team_id == team.id)
            for row in query.all():
                self.db.delete(row)
                removed += 1
        commit(self.db, f"Team teacher unassign removed={removed}")
        return {"removed": removed}

    def delete(self, row_id: int) -> None:
        row = self.get(row_id)
        ensure_manager(self.user)
        self.db.delete(row)
        commit(self.db, f"Team teacher delete id={row_id}")

    # -------------------------------------------------------------- internals
    def _team(self, team_id: int) -> Team:
        scope = scoped_team(self.db, self.user, team_id)
        if scope is None:  # pragma: no cover - called only with a real id
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team {team_id} not found.",
            )
        return get_or_404(self.db, Team, scope.team_id, "Team")

    def _teacher(self, teacher_id: int, team: Team) -> Teacher:
        servant = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_teacher_access(self.db, self.user, servant)
        if servant.church_id != team.church_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Servant '{servant.teacher_name}' is not in that team's church.",
            )
        if servant.class_id is not None and servant.class_id != team.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Servant '{servant.teacher_name}' is not in that team's class.",
            )
        return servant
