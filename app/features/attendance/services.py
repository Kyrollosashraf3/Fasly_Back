"""Friday attendance sheet - one row per (boy, date)."""
from __future__ import annotations

from datetime import date

from app.core.data.base import WeeklySheetService
from app.core.data.common import (
    STAFF,
    commit,
    ensure_boy_access,
    ensure_roles,
    scope_boys,
    scoped_team,
)
from app.features.attendance.models.attend import Attend
from app.features.boy.models.boy import Boy
from app.features.attendance.schemas.attend import AttendBulkCreate, AttendCreate, AttendUpdate


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

    def list(
        self,
        class_id: int | None = None,
        action_date: date | None = None,
        team_id: int | None = None,
    ) -> list:
        """Same sheet as the base service, with an optional team filter."""
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Attend.class_id == class_id)
        if action_date is not None:
            query = query.filter(Attend.date == action_date)
        team = scoped_team(self.db, self.user, team_id)
        if team is not None:
            query = query.filter(Attend.boy_id.in_(team.boy_ids))
        return query.order_by(Attend.date.desc(), Attend.id.desc()).all()

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
