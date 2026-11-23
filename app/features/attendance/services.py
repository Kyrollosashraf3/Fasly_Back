"""Friday attendance sheet - one row per (boy, date)."""
from __future__ import annotations


from app.core.data.base import WeeklySheetService
from app.core.data.common import (
    STAFF,
    commit,
    ensure_boy_access,
    ensure_roles,
    scope_boys,
)
from app.models.attend import Attend
from app.models.boy import Boy
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
        ensure_roles(self.user, *STAFF)
        ensure_boy_access(self.db, self.user, boy)

    # route-facing signatures, kept explicit for the type hints
    def create(self, data: AttendCreate) -> Attend:
        return super().create(data)

    def create_bulk(self, data: AttendBulkCreate) -> list[Attend]:
        return super().create_bulk(data)

    def update(self, record_id: int, data: AttendUpdate) -> Attend:
        return super().update(record_id, data)

    def delete(self, record_id: int) -> None:
        """Remove one saved row.

        The sheet only ever holds «حاضر» rows, so unticking a boy means his row
        goes away — an absent boy keeps no record at all. That is a correction
        the servant who records attendance must be able to make, so delete is
        open to every writer of the class (unlike the base's amin-only delete).
        """
        record = self.get(record_id)
        self.can_write(getattr(record, self.person_attr))
        self.db.delete(record)
        commit(self.db, f"{self.label} delete id={record_id}")
