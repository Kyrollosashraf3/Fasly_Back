"""Follow-up groups: which boys each servant is responsible for."""

from fastapi import HTTPException, status
from sqlalchemy import case, func

from app.core.data.base import ClassScopedService
from app.core.data.common import get_or_404
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.group import Group
from app.models.teacher import Teacher


class GroupsService(ClassScopedService):
    """The ``groups`` table is the only link between a servant and his boys -
    there is no ``class_id`` here: it is reachable through both sides.

    read : super_admin all | admin his class | teacher his own group
    write: super_admin all | admin his class
    """

    # --------------------------------------------------------------- queries
    def _teachers_query(self):
        role = self.scope.role
        if role == RoleEnum.USER:
            self.scope.deny("You do not have permission to view groups.")
        if role == RoleEnum.TEACHER:
            return self.db.query(Teacher).filter(
                Teacher.id == self.scope.teacher_id
            )
        return self.scope.restrict_class(self.db.query(Teacher), Teacher)

    def _groups_query(self):
        role = self.scope.role
        if role == RoleEnum.USER:
            self.scope.deny("You do not have permission to view groups.")
        query = self.db.query(Group).join(
            Teacher, Group.teacher_id == Teacher.id
        )
        if role == RoleEnum.TEACHER:
            return query.filter(Group.teacher_id == self.scope.teacher_id)
        if not self.scope.is_super_admin:
            query = query.filter(Teacher.class_id == self.scope.class_id)
        return query

    # ---------------------------------------------------------------- write
    def assign(self, teacher_id: int, boy_ids: list[int]) -> dict:
        self.scope.require_manager()
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        self.scope.ensure_class(teacher.class_id)

        assigned = 0
        for boy_id in dict.fromkeys(boy_ids):  # de-dupe, keep order
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            self.scope.ensure_boy_visible(boy)
            if boy.class_id != teacher.class_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Boy '{boy.boy_name}' is not in the servant's class.",
                )
            # a boy belongs to exactly one group: drop the old one first
            self.db.query(Group).filter(Group.boy_id == boy.id).delete(
                synchronize_session=False
            )
            self.db.add(Group(teacher_id=teacher.id, boy_id=boy.id))
            assigned += 1

        self._commit(f"Group assign teacher={teacher_id} boys={assigned}")
        return {
            "teacher_id": teacher.id,
            "teacher_name": teacher.teacher_name,
            "assigned": assigned,
        }

    def unassign(self, boy_ids: list[int]) -> dict:
        self.scope.require_manager()
        removed = 0
        for boy_id in dict.fromkeys(boy_ids):
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            self.scope.ensure_boy_visible(boy)
            removed += self.db.query(Group).filter(Group.boy_id == boy.id).delete(
                synchronize_session=False
            )
        self._commit(f"Group unassign boys={removed}")
        return {"removed": removed}

    # ----------------------------------------------------------------- read
    @staticmethod
    def _boy_row(boy: Boy) -> dict:
        return {
            "boy_id": boy.id,
            "boy_name": boy.boy_name,
            "phone": boy.phone,
            "phone_2": boy.phone_2,
            "address": boy.address,
            "issue_flag": boy.issue_flag,
            "note": boy.note,
        }

    def list(self, class_id: int | None = None, teacher_id: int | None = None) -> dict:
        """Servants with their boy rosters, plus the boys nobody has yet."""
        teacher_query = self._teachers_query()
        if class_id is not None:
            self.scope.ensure_class(class_id)
            teacher_query = teacher_query.filter(Teacher.class_id == class_id)
        if teacher_id is not None:
            teacher_query = teacher_query.filter(Teacher.id == teacher_id)
        teachers = teacher_query.order_by(Teacher.teacher_name).all()

        if self.scope.role == RoleEnum.USER:
            boys_query = self.db.query(Boy).filter(Boy.id == self.scope.boy_id)
        elif self.scope.role == RoleEnum.TEACHER:
            boys_query = self.db.query(Boy).filter(
                Boy.id.in_(self.scope.group_boy_ids())
            )
        else:
            boys_query = self.scope.restrict_class(self.db.query(Boy), Boy)
        boys_by_id = {boy.id: boy for boy in boys_query.all()}

        group_query = self._groups_query()
        if class_id is not None:
            group_query = group_query.filter(Teacher.class_id == class_id)
        if teacher_id is not None:
            group_query = group_query.filter(Group.teacher_id == teacher_id)
        members: dict[int, list[dict]] = {}
        for row in group_query.all():
            boy = boys_by_id.get(row.boy_id)
            if boy is not None:
                members.setdefault(row.teacher_id, []).append(self._boy_row(boy))

        groups = [
            {
                "teacher_id": teacher.id,
                "teacher_name": teacher.teacher_name,
                "phone": teacher.phone,
                "class_id": teacher.class_id,
                "note": teacher.note,
                "boys_count": len(members.get(teacher.id, [])),
                "boys": members.get(teacher.id, []),
            }
            for teacher in teachers
        ]
        grouped_boy_ids = {
            row["boy_id"] for rows in members.values() for row in rows
        }
        unassigned = [
            self._boy_row(boy)
            for boy in boys_by_id.values()
            if boy.id not in grouped_boy_ids
        ]
        return {
            "groups": groups,
            "unassigned": unassigned,
            "unassigned_count": len(unassigned),
        }

    # ------------------------------------------------------------ spreadsheet
    @staticmethod
    def _matches(name: str, wanted: str) -> bool:
        return " ".join(name.split()).lower() == wanted

    def _find_teacher(self, name: str, class_id: int) -> Teacher:
        wanted = " ".join(str(name).split()).lower()
        for teacher in self._teachers_query().filter(
            Teacher.class_id == class_id
        ).all():
            if self._matches(teacher.teacher_name, wanted):
                return teacher
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servant '{name}' not found in that class.",
        )

    def _find_boy(self, name: str, class_id: int) -> Boy:
        wanted = " ".join(str(name).split()).lower()
        for boy in self.db.query(Boy).filter(Boy.class_id == class_id).all():
            if self._matches(boy.boy_name, wanted):
                return boy
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boy '{name}' not found in that class.",
        )

    def import_rows(self, rows: list[dict]) -> dict:
        """Apply a parsed assignment sheet (``teacher_name|boy_name|class_id``).

        Rows are bucketed per servant first so each servant gets one
        ``assign`` call; a row that cannot be resolved is reported, not fatal.
        """
        self.scope.require_manager()
        buckets: dict[int, list[int]] = {}
        labels: dict[int, str] = {}
        failed: list[dict] = []

        for row in rows:
            try:
                teacher = self._find_teacher(row["teacher_name"], row["class_id"])
                boy = self._find_boy(row["boy_name"], row["class_id"])
                if boy.class_id != teacher.class_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Boy '{boy.boy_name}' and servant "
                            f"'{teacher.teacher_name}' are not in the same class."
                        ),
                    )
                bucket = buckets.setdefault(teacher.id, [])
                if boy.id not in bucket:
                    bucket.append(boy.id)
                    labels[teacher.id] = teacher.teacher_name
            except HTTPException as exc:
                failed.append({**row, "error": exc.detail})

        created = []
        for teacher_id, boy_ids in buckets.items():
            try:
                created.append(self.assign(teacher_id, boy_ids))
            except HTTPException as exc:
                failed.append(
                    {
                        "teacher_name": labels.get(teacher_id),
                        "boy_name": None,
                        "error": exc.detail,
                    }
                )
        return {"created": created, "failed": failed}

    def export_rows(self, class_id: int | None = None) -> dict:
        """:meth:`list` plus the attendance / follow-up columns the workbook
        prints, computed for every boy of the sheet in two bulk queries."""
        payload = self.list(class_id=class_id)
        boy_ids = [b["boy_id"] for g in payload["groups"] for b in g["boys"]]
        stats = self._attendance_stats(boy_ids)
        lasts = self._last_followups(boy_ids)
        for group in payload["groups"]:
            for row in group["boys"]:
                row.update(stats.get(row["boy_id"], {"present": 0, "absent": 0, "percent": None}))
                row["last_followup"] = lasts.get(row["boy_id"])
        return payload

    def _attendance_stats(self, boy_ids: list[int]) -> dict[int, dict]:
        if not boy_ids:
            return {}
        rows = (
            self.db.query(
                Attend.boy_id,
                func.sum(case((Attend.present, 1), else_=0)).label("present"),
                func.count(Attend.id).label("total"),
            )
            .filter(Attend.boy_id.in_(boy_ids))
            .group_by(Attend.boy_id)
            .all()
        )
        stats: dict[int, dict] = {}
        for row in rows:
            present, total = int(row.present), int(row.total)
            stats[row.boy_id] = {
                "present": present,
                "absent": total - present,
                "percent": round(100 * present / total),
            }
        return stats

    def _last_followups(self, boy_ids: list[int]) -> dict[int, dict]:
        if not boy_ids:
            return {}
        rows = (
            self.db.query(FollowUp)
            .filter(FollowUp.boy_id.in_(boy_ids))
            .order_by(FollowUp.action_date.desc(), FollowUp.id.desc())
            .all()
        )
        lasts: dict[int, dict] = {}
        for row in rows:
            lasts.setdefault(
                row.boy_id,
                {"action_date": row.action_date, "status": row.status.value},
            )
        return lasts
