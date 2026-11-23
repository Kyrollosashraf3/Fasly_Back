"""GPS updates for a servant's home address."""

from app.core.data.base import BaseService
from app.core.data.common import (
    commit,
    ensure_manager,
    ensure_teacher_access,
    get_or_404,
)
from app.models.teacher import Teacher
from app.schemas.location import TeacherLocationRecord, TeacherLocationResponse


class TeacherLocationService(BaseService):
    def record(
        self, teacher_id: int, data: TeacherLocationRecord
    ) -> TeacherLocationResponse:
        ensure_manager(self.user)
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_teacher_access(self.db, self.user, teacher)
        teacher.latitude = data.latitude
        teacher.longitude = data.longitude
        self.db.flush()
        result = TeacherLocationResponse(
            teacher_id=teacher.id,
            teacher_name=teacher.teacher_name,
            latitude=teacher.latitude,
            longitude=teacher.longitude,
            updated_at=teacher.updated_at,
        )
        commit(self.db, f"Teacher location save teacher={teacher.id} by user={self.user_id}")
        return result
