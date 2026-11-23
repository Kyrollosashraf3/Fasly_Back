"""Manager follow-up records for servants, isolated from boy follow-ups."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_manager,
    ensure_teacher_access,
    get_or_404,
    my_class_ids,
    scope_church,
)
from app.models.enums import RoleEnum
from app.features.teacher.models.teacher import Teacher
from app.features.teacher_follow_up.models.teacher_follow_up import TeacherFollowUp
from app.features.teacher_follow_up.schemas.teacher_follow_up import TeacherFollowUpCreate, TeacherFollowUpUpdate


class TeacherFollowUpService(BaseService):
    """Logs and history for servant visits.

    Class snapshots constrain class and stage amin records. أبونا sees the
    church's full history, including servants who are not assigned to a class.
    """

    def query(self) -> Query:
        ensure_manager(self.user)
        query = scope_church(
            self.db.query(TeacherFollowUp), TeacherFollowUp, self.user
        )
        if self.user.role in (RoleEnum.SUPER_ADMIN, RoleEnum.ABONA):
            return query
        class_ids = my_class_ids(self.db, self.user) or []
        return query.filter(TeacherFollowUp.class_id.in_(class_ids))

    def list(
        self,
        *,
        class_id: int | None = None,
        teacher_id: int | None = None,
        action_date: date | None = None,
    ) -> list[TeacherFollowUp]:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(TeacherFollowUp.class_id == class_id)
        if teacher_id is not None:
            self._resolve_teacher(teacher_id)
            query = query.filter(TeacherFollowUp.teacher_id == teacher_id)
        if action_date is not None:
            query = query.filter(TeacherFollowUp.action_date == action_date)
        return query.order_by(
            TeacherFollowUp.action_date.desc(), TeacherFollowUp.id.desc()
        ).all()

    def get(self, record_id: int) -> TeacherFollowUp:
        record = self.query().filter(TeacherFollowUp.id == record_id).first()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher follow-up {record_id} not found.",
            )
        return record

    def create(self, data: TeacherFollowUpCreate) -> TeacherFollowUp:
        ensure_manager(self.user)
        teacher = self._resolve_teacher(data.teacher_id)
        record = TeacherFollowUp(
            church_id=self.church_for(class_id=teacher.class_id, person=teacher),
            teacher_id=teacher.id,
            class_id=teacher.class_id,
            action_date=data.action_date or date.today(),
            status=data.status,
            note=data.note,
            recorded_by=self.user_id,
        )
        self.db.add(record)
        commit(self.db, f"Teacher follow-up create teacher={teacher.id}")
        return record

    def update(
        self, record_id: int, data: TeacherFollowUpUpdate
    ) -> TeacherFollowUp:
        record = self.get(record_id)
        apply_update(record, data, skip=("church_id", "teacher_id", "class_id"))
        commit(self.db, f"Teacher follow-up update id={record_id}")
        return record

    def delete(self, record_id: int) -> None:
        record = self.get(record_id)
        self.db.delete(record)
        commit(self.db, f"Teacher follow-up delete id={record_id}")

    def _resolve_teacher(self, teacher_id: int) -> Teacher:
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_teacher_access(self.db, self.user, teacher)
        return teacher
