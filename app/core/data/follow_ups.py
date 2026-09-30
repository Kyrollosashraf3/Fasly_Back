"""Weekly follow-up contact logged by a servant."""

from datetime import date

from fastapi import HTTPException, status

from app.core.data.base import ClassScopedService
from app.core.data.common import get_or_404
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.teacher import Teacher
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate


class FollowUpService(ClassScopedService):
    """One row per contact - ``class_id`` is the boy's class on ``action_date``.

    read : super_admin all | admin his class | teacher his own rows | user his own
    write: super_admin all | admin his class | teacher his own rows
    """

    def _records_query(self):
        role = self.scope.role
        if role == RoleEnum.USER:
            return self.db.query(FollowUp).filter(
                FollowUp.boy_id == self.scope.boy_id
            )
        if role == RoleEnum.TEACHER:
            return self.db.query(FollowUp).filter(
                FollowUp.teacher_id == self.scope.teacher_id
            )
        return self._scoped(FollowUp)  # admin / super_admin

    def _ensure_write(self, record: FollowUp) -> None:
        self.scope.require_roles(
            RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER
        )
        if self.scope.role == RoleEnum.TEACHER:
            if record.teacher_id != self.scope.teacher_id:
                self.scope.deny("You can only edit your own follow-ups.")
            return
        self.scope.ensure_class(record.class_id)  # admin

    # ------------------------------------------------------------------ read
    def _resolve_teacher(self, teacher_id: int) -> Teacher:
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        self.scope.ensure_teacher_visible(teacher)
        return teacher

    def _resolve_boy(self, boy_id: int) -> Boy:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        self.scope.ensure_boy_visible(boy)
        return boy

    def get(self, record_id: int) -> FollowUp:
        record = (
            self._records_query().filter(FollowUp.id == record_id).first()
        )
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
        query = self._records_query()
        if class_id is not None:
            self.scope.ensure_class(class_id)
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
        self.scope.require_roles(
            RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER
        )
        teacher = self._resolve_teacher(data.teacher_id)
        boy = self._resolve_boy(data.boy_id)
        if self.scope.role == RoleEnum.TEACHER and teacher.id != self.scope.teacher_id:
            self.scope.deny("You can only log follow-ups for yourself.")
        if teacher.class_id != boy.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Boy '{boy.boy_name}' is not in that servant's class.",
            )

        record = FollowUp(
            teacher_id=teacher.id,
            boy_id=boy.id,
            class_id=boy.class_id,  # snapshot taken now
            action_date=data.action_date or date.today(),
            status=data.status,
            note=data.note,
            recorded_by=self.current_user.id,
        )
        self.db.add(record)
        self._commit(f"FollowUp create boy={boy.id} teacher={teacher.id}")
        return record

    def update(self, record_id: int, data: FollowUpUpdate) -> FollowUp:
        record = self.get(record_id)
        self._ensure_write(record)
        for field in data.model_fields_set:
            setattr(record, field, getattr(data, field))
        self._commit(f"FollowUp update id={record_id}")
        return record

    def delete(self, record_id: int) -> None:
        record = self.get(record_id)
        self.scope.require_manager()
        self.scope.ensure_class(record.class_id)
        self.db.delete(record)
        self._commit(f"FollowUp delete id={record_id}")
