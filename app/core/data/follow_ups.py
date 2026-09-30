from datetime import date

from app.core.data.base import ClassScopedService
from app.models.boy import Boy
from app.models.follow_up import FollowUp
from app.models.teacher import Teacher
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate


class FollowUpService(ClassScopedService):
    def _resolve_teacher(self, teacher_id: int) -> Teacher:
        pass

    def _resolve_boy(self, boy_id: int) -> Boy:
        pass

    def create(self, data: FollowUpCreate) -> FollowUp:
        pass

    def get(self, record_id: int) -> FollowUp:
        pass

    def list(
        self,
        class_name=None,
        teacher_id: int | None = None,
        boy_id: int | None = None,
        action_date: date | None = None,
    ) -> list[FollowUp]:
        pass

    def update(self, record_id: int, data: FollowUpUpdate) -> FollowUp:
        pass

    def delete(self, record_id: int) -> None:
        pass
