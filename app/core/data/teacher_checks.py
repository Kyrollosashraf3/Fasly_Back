"""Weekly review the amin runs over his class's servants."""

from app.core.data.base import PersonCheckService
from app.models.enums import RoleEnum
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck
from app.schemas.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckUpdate,
)


class TeacherCheckService(PersonCheckService):
    """One row per (servant, date) - ``class_id`` is stamped as a snapshot.

    read : super_admin all | admin his class | teacher himself
    write: super_admin all | admin his class (the amin is the one who asks)
    """

    model = TeacherCheck
    person_model = Teacher
    person_fk = "teacher_id"
    person_attr = "teacher"
    person_label = "Servant"
    label = "Teacher check"

    def _records_query(self):
        # a boy account must never reach this table at all
        self.scope.require_roles(
            RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER
        )
        query = super()._records_query()
        if self.scope.role == RoleEnum.TEACHER:
            query = query.filter(
                TeacherCheck.teacher_id == self.scope.teacher_id
            )
        return query

    def _ensure_visible(self, teacher: Teacher) -> None:
        self.scope.require_roles(
            RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER
        )
        self.scope.ensure_teacher_visible(teacher)

    def _ensure_writable(self, teacher: Teacher) -> None:
        self.scope.require_manager()
        self.scope.ensure_class(teacher.class_id)

    # route-facing signatures
    def create(self, data: TeacherCheckCreate):
        return super().create(data)

    def create_bulk(self, data: TeacherCheckBulkCreate) -> list:
        return super().create_bulk(data)

    def update(self, record_id: int, data: TeacherCheckUpdate):
        return super().update(record_id, data)
