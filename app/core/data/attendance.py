"""Friday attendance sheet."""

from app.core.data.base import PersonCheckService
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.schemas.attend import AttendBulkCreate, AttendCreate, AttendUpdate


class AttendanceService(PersonCheckService):
    """One row per (boy, date) - ``class_id`` is stamped as a snapshot.

    read : super_admin all | admin his class | teacher his group's boys | user himself
    write: super_admin all | admin his class | teacher his group's boys
    """

    model = Attend
    person_model = Boy
    person_fk = "boy_id"
    person_attr = "boy"
    person_label = "Boy"
    label = "Attendance"

    def _records_query(self):
        return self.scope.restrict_boys(
            super()._records_query(), Attend, Attend.boy_id
        )

    def _ensure_visible(self, boy: Boy) -> None:
        self.scope.ensure_boy_visible(boy)

    def _ensure_writable(self, boy: Boy) -> None:
        self.scope.require_roles(
            RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER
        )
        self.scope.ensure_boy_visible(boy)

    # route-facing signatures (kept explicit for readability / type hints)
    def create(self, data: AttendCreate):
        return super().create(data)

    def create_bulk(self, data: AttendBulkCreate) -> list:
        return super().create_bulk(data)

    def update(self, record_id: int, data: AttendUpdate):
        return super().update(record_id, data)
