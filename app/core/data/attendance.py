"""Friday attendance sheet - one row per (boy, date)."""
from __future__ import annotations


from app.core.data.base import WeeklySheetService
from app.core.data.common import ensure_boy_access, ensure_roles, scope_boys
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.schemas.attend import AttendBulkCreate, AttendCreate, AttendUpdate


class AttendanceService(WeeklySheetService):
    """``class_id`` on every row is a snapshot of the boy's class on ``date``,
    so promoting boys later never rewrites history.

    read : super_admin all | admin his class | teacher his class | boy himself
    write: super_admin all | admin his class | teacher his class
    """

    model = Attend
    person = Boy
    person_fk = "boy_id"
    person_attr = "boy"
    person_label = "Boy"
    label = "Attendance"

    def query(self):
        return scope_boys(
            self.db, self.db.query(Attend), Attend, self.user, Attend.boy_id
        )

    def can_read(self, boy: Boy) -> None:
        ensure_boy_access(self.db, self.user, boy)

    def can_write(self, boy: Boy) -> None:
        ensure_roles(self.user, RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER)
        ensure_boy_access(self.db, self.user, boy)

    # route-facing signatures, kept explicit for the type hints
    def create(self, data: AttendCreate) -> Attend:
        return super().create(data)

    def create_bulk(self, data: AttendBulkCreate) -> list[Attend]:
        return super().create_bulk(data)

    def update(self, record_id: int, data: AttendUpdate) -> Attend:
        return super().update(record_id, data)
