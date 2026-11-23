"""Follow-up: one row per contact a servant logs with one boy."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    STAFF,
    apply_update,
    commit,
    ensure_boy_access,
    ensure_roles,
    ensure_teacher_access,
    get_or_404,
    scope_follow_ups,
)
from app.features.boy.models.boy import Boy
from app.models.enums import RoleEnum
from app.features.follow_up.models.follow_up import FollowUp
from app.features.teacher.models.teacher import Teacher
from app.features.follow_up.schemas.follow_up import FollowUpCreate, FollowUpUpdate


class FollowUpService(BaseService):
    """``class_id`` is the boy's class on ``action_date`` - a snapshot, kept so
    history survives a promotion.

    read : super_admin all | admin his class | teacher his own rows | boy his own
    write: super_admin all | admin his class | teacher his own rows
    """


    def query(self) -> Query:
        return scope_follow_ups(self.db, self.db.query(FollowUp), self.user)

    # ------------------------------------------------------------------ read
    def get(self, record_id: int) -> FollowUp:
        record = self.query().filter(FollowUp.id == record_id).first()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Follow-up {record_id} not found.",
            )
        return record

    def list(
        self,
        class_id: int | None = None,
        teacher_id: int | None = None,
        boy_id: int | None = None,
        action_date: date | None = None,
    ) -> list[FollowUp]:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(FollowUp.class_id == class_id)
        if teacher_id is not None:
            query = query.filter(FollowUp.teacher_id == teacher_id)
        if boy_id is not None:
            query = query.filter(FollowUp.boy_id == boy_id)
        if action_date is not None:
            query = query.filter(FollowUp.action_date == action_date)
        return query.order_by(FollowUp.action_date.desc(), FollowUp.id.desc()).all()

    # ----------------------------------------------------------------- write
    def create(self, data: FollowUpCreate) -> FollowUp:
        ensure_roles(self.user, *STAFF)
        teacher = self._resolve_servant(data.teacher_id)
        boy = self._resolve_boy(data.boy_id)
        if self.user.role == RoleEnum.TEACHER and teacher.id != self.user.teacher_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only log follow-ups for yourself.",
            )
        if teacher.class_id != boy.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Boy '{boy.boy_name}' is not in that servant's class.",
            )

        record = FollowUp(
            teacher_id=teacher.id,
            boy_id=boy.id,
            church_id=self.church_for(class_id=boy.class_id, person=boy),
            class_id=boy.class_id,  # snapshot taken now
            action_date=data.action_date or date.today(),
            status=data.status,
            note=data.note,
            recorded_by=self.user_id,
        )
        self.db.add(record)
        commit(self.db, f"FollowUp create boy={boy.id} teacher={teacher.id}")
        return record

    def update(self, record_id: int, data: FollowUpUpdate) -> FollowUp:
        record = self.get(record_id)
        self._ensure_may_edit(record)
        apply_update(record, data, skip=("teacher_id", "boy_id", "class_id"))
        commit(self.db, f"FollowUp update id={record_id}")
        return record

    def delete(self, record_id: int) -> None:
        record = self.get(record_id)
        self.ensure_manager()
        self.db.delete(record)
        commit(self.db, f"FollowUp delete id={record_id}")

    # -------------------------------------------------------------- internals
    def _resolve_servant(self, teacher_id: int) -> Teacher:
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_teacher_access(self.db, self.user, teacher)
        return teacher

    def _resolve_boy(self, boy_id: int) -> Boy:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_boy_access(self.db, self.user, boy)
        return boy

    def _ensure_may_edit(self, record: FollowUp) -> None:
        ensure_roles(self.user, *STAFF)
        if self.user.role == RoleEnum.TEACHER and record.teacher_id != self.user.teacher_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own follow-ups.",
            )
