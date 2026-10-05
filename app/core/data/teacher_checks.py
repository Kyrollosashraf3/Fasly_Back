"""Friday review the amin runs over the servants of his class."""
from __future__ import annotations

from app.core.data.base import WeeklySheetService
from app.core.data.common import ensure_teacher_access, scope_checks
from app.models.enums import RoleEnum
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckUpdate,
)


class TeacherCheckService(WeeklySheetService):
    """``class_id`` on every row is a snapshot of the servant's class on ``date``.

    read : super_admin all | admin his class | teacher himself  (a boy: 403)
    write: super_admin all | admin his class
    """


    model = TeacherCheck
    person = Teacher
    person_fk = "teacher_id"
    person_attr = "teacher"
    person_label = "Servant"
    label = "Teacher check"

    def query(self):
        return scope_checks(self.db, self.db.query(TeacherCheck), self.user)

    def can_read(self, teacher: Teacher) -> None:
        ensure_teacher_access(self.db, self.user, teacher)

    def can_write(self, teacher: Teacher) -> None:
        self.ensure_manager()
        self.ensure_class(teacher.class_id)

    # route-facing signatures, kept explicit for the type hints
    def create(self, data: TeacherCheckCreate) -> TeacherCheck:
        return super().create(data)

    def create_bulk(self, data: TeacherCheckBulkCreate) -> list[TeacherCheck]:
        return super().create_bulk(data)

    def update(self, record_id: int, data: TeacherCheckUpdate) -> TeacherCheck:
        return super().update(record_id, data)
