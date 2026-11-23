"""حضور الأولاد في يوم الرحلة وتوزيعهم على الخدام.

صف واحد لكل (رحلة، ولد): ``attend_flag`` بيقول حضر ولا لا، و``teacher_id``
بيقول مين الخادم المسئول عنه في الرحلة دي. الفصل مش مخزن هنا - بناخده من
الرحلة نفسها (``trip.class_id``) بعد ما نتأكد إن الرحلة من كنيستنا وفصولنا.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, joinedload

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_boy_access,
    ensure_my_church,
    ensure_roles,
    get_or_404,
    my_class_ids,
    scope_church,
)
from app.features.boy.models.boy import Boy
from app.models.enums import RoleEnum
from app.features.teacher.models.teacher import Teacher
from app.features.trip.models.trip import Trip
from app.features.trip_attendance.models.trip_attendance import TripAttendance
from app.features.trip_attendance.schemas.trip_attendance import (
    TripAttendanceBulkCreate,
    TripAttendanceUpdate,
    TripSheetResponse,
    TripSheetRow,
)

#: الأمناء والخدام فقط اللي بيكتبوا في كشف الرحلة؛ الولد بيقرأ صفه فقط.
_WRITERS = (
    RoleEnum.SUPER_ADMIN,
    RoleEnum.ABONA,
    RoleEnum.GENERAL_ADMIN,
    RoleEnum.ADMIN,
    RoleEnum.TEACHER,
)


class TripAttendanceService(BaseService):
    """read : صاحب المنصة كل | أبونا كنيسته | أمين فصوله | خادم فصله | ولد صفه فقط
    write: الأمناء والخدام بنفس النطاق، والولد ممنوع تمامًا.
    """

    # --------------------------------------------------------------- queries
    def query(self) -> Query:
        """كل الصفوف اللي الدخول ده يقدر يشوفها (كنيسة أولاً، ثم فصل الرحلة)."""
        q = scope_church(
            self.db.query(TripAttendance), TripAttendance, self.user
        ).join(Trip, TripAttendance.trip_id == Trip.id)
        if self.user.role == RoleEnum.USER:
            return q.filter(TripAttendance.boy_id == self.user.boy_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None:
            q = q.filter(Trip.class_id.in_(mine))
        return q

    @staticmethod
    def _with_names(query: Query) -> Query:
        """Eager-load الولد والخادم والرحلة عشان أسماء الرد من غير استعلامات زيادة."""
        return query.options(
            joinedload(TripAttendance.boy),
            joinedload(TripAttendance.teacher),
            joinedload(TripAttendance.trip),
        )

    # ------------------------------------------------------------------ read
    def list(self, trip_id: int | None = None) -> list[TripAttendance]:
        q = self._with_names(self.query())
        if trip_id is not None:
            q = q.filter(TripAttendance.trip_id == trip_id)
        return q.order_by(TripAttendance.id.desc()).all()

    def get(self, row_id: int) -> TripAttendance:
        row = self._with_names(self.query()).filter(TripAttendance.id == row_id).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="سطر حضور الرحلة غير موجود.",
            )
        return row

    def sheet(self, trip_id: int) -> TripSheetResponse:
        """كشف الرحلة: كل أولاد فصل الرحلة + علامة الحضور + الخادم المسئول.

        بنعرض كل أولاد الفصل (زي ملخص الاشتراكات) حتى اللي لسه مفيش صف له،
        عشان الخادم يشوف الكشف كامل ويقدر يوزّع ويعلّم من شاشة واحدة.
        """
        trip = self._trip(trip_id)
        boys_query = self.db.query(Boy).filter(
            Boy.church_id == trip.church_id,
            Boy.class_id == trip.class_id,
        )
        if self.user.role == RoleEnum.USER:
            boys_query = boys_query.filter(Boy.id == self.user.boy_id)
        boys = boys_query.order_by(Boy.boy_name).all()

        rows = {
            row.boy_id: row
            for row in self.db.query(TripAttendance)
            .filter(TripAttendance.trip_id == trip_id)
            .all()
        }
        teacher_names = {
            servant.id: servant.teacher_name
            for servant in self.db.query(Teacher)
            .filter(Teacher.church_id == trip.church_id)
            .all()
        }

        sheet_rows: list[TripSheetRow] = []
        for boy in boys:
            row = rows.get(boy.id)
            teacher_id = row.teacher_id if row is not None else None
            sheet_rows.append(
                TripSheetRow(
                    boy_id=boy.id,
                    boy_name=boy.boy_name,
                    teacher_id=teacher_id,
                    teacher_name=teacher_names.get(teacher_id) if teacher_id else None,
                    attend_flag=row.attend_flag if row is not None else False,
                    phone=boy.phone,
                )
            )
        return TripSheetResponse(
            trip_id=trip.id,
            trip_name=trip.name,
            class_id=trip.class_id,
            total=len(sheet_rows),
            attended=sum(1 for item in sheet_rows if item.attend_flag),
            rows=sheet_rows,
        )

    # ----------------------------------------------------------------- write
    def save_attendance(
        self, trip_id: int, data: TripAttendanceBulkCreate
    ) -> list[TripAttendance]:
        """حفظ علامات الحضور لكل الأولاد في عملية واحدة (upsert لكل ولد)."""
        self._require_writer()
        trip = self._trip(trip_id)
        result = [
            self._save(
                trip,
                self._boy_for_trip(trip, item.boy_id).id,
                attend_flag=item.attend_flag,
            )
            for item in data.items
        ]
        commit(self.db, f"Trip attendance save trip={trip_id} rows={len(result)}")
        return result

    def assign(self, trip_id: int, teacher_id: int, boy_ids: list[int]) -> dict:
        """توزيع مجموعة أولاد على خادم واحد داخل الرحلة."""
        self._require_writer()
        trip = self._trip(trip_id)
        servant = get_or_404(self.db, Teacher, teacher_id, "Servant")
        self._ensure_teacher(trip, servant)  # الكنيسة أولاً، ثم فصل الرحلة

        assigned = 0
        for boy_id in dict.fromkeys(boy_ids):  # de-dupe, keep order
            boy = self._boy_for_trip(trip, boy_id)
            row = self._save(trip, boy.id)
            row.teacher_id = servant.id
            assigned += 1

        commit(
            self.db,
            f"Trip attendance assign trip={trip.id} servant={servant.id} boys={assigned}",
        )
        return {
            "trip_id": trip.id,
            "teacher_id": servant.id,
            "teacher_name": servant.teacher_name,
            "assigned": assigned,
        }

    def unassign(self, trip_id: int, boy_ids: list[int]) -> dict:
        """إلغاء توزيع أولاد داخل الرحلة (من غير مسح الصف أو علامة الحضور)."""
        self._require_writer()
        trip = self._trip(trip_id)
        removed = 0
        for boy_id in dict.fromkeys(boy_ids):
            row = (
                self.db.query(TripAttendance)
                .filter(
                    TripAttendance.trip_id == trip.id,
                    TripAttendance.boy_id == boy_id,
                    TripAttendance.church_id == trip.church_id,
                )
                .first()
            )
            if row is not None:
                row.teacher_id = None
                removed += 1
        commit(self.db, f"Trip attendance unassign trip={trip.id} rows={removed}")
        return {"trip_id": trip.id, "removed": removed}

    def update(self, row_id: int, data: TripAttendanceUpdate) -> TripAttendance:
        self._require_writer()
        row = self.get(row_id)
        if data.teacher_id is not None:
            trip = get_or_404(self.db, Trip, row.trip_id, "Trip")
            self._ensure_teacher(trip, get_or_404(self.db, Teacher, data.teacher_id, "Servant"))
        apply_update(row, data)
        commit(self.db, f"Trip attendance update id={row_id}")
        return row

    def delete(self, row_id: int) -> None:
        self._require_writer()
        row = self.get(row_id)
        self.db.delete(row)
        commit(self.db, f"Trip attendance delete id={row_id}")

    # -------------------------------------------------------------- internals
    def _require_writer(self) -> None:
        ensure_roles(self.user, *_WRITERS)

    def _trip(self, trip_id: int) -> Trip:
        trip = get_or_404(self.db, Trip, trip_id, "Trip")
        # الكنيسة أولاً: أي class_id من tenant تاني يُرفض هنا قبل أي حاجة.
        ensure_my_church(self.db, self.user, trip.church_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None and trip.class_id not in mine:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لديك صلاحية فقط على رحلات فصولك.",
            )
        return trip

    def _boy_for_trip(self, trip: Trip, boy_id: int) -> Boy:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_boy_access(self.db, self.user, boy)
        if boy.church_id != trip.church_id or boy.class_id != trip.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"الولد '{boy.boy_name}' ليس من فصل الرحلة.",
            )
        return boy

    def _ensure_teacher(self, trip: Trip, servant: Teacher) -> None:
        if servant.church_id != trip.church_id or servant.class_id != trip.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"الخادم '{servant.teacher_name}' ليس من فصل الرحلة.",
            )
        self.ensure_class(servant.class_id)

    def _save(
        self, trip: Trip, boy_id: int, *, attend_flag: bool | None = None
    ) -> TripAttendance:
        """إيجاد صف (الرحلة، الولد) أو إنشاؤه، وتحديث العلامة لو اتبعتت."""
        row = (
            self.db.query(TripAttendance)
            .filter(
                TripAttendance.trip_id == trip.id,
                TripAttendance.boy_id == boy_id,
            )
            .first()
        )
        if row is None:
            row = TripAttendance(
                church_id=self.church_for(class_id=trip.class_id),
                trip_id=trip.id,
                boy_id=boy_id,
                attend_flag=bool(attend_flag),
            )
            self.db.add(row)
        elif attend_flag is not None:
            row.attend_flag = bool(attend_flag)
        return row
