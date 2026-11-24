"""Follow-up groups: which boys each servant is responsible for.

``groups`` is the only servant <-> boy link in the schema, and it holds no
``class_id`` - the class is reachable through either side.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_

from app.core.data.base import BaseService
from app.core.data.common import (
    commit,
    ensure_boy_access,
    ensure_manager,
    get_or_404,
    my_class_ids,
    normalise_name,
    scope_boys,
    scope_church,
    scope_teachers,
    scoped_team,
)
from app.features.attendance.models.attend import Attend
from app.features.boy.models.boy import Boy
from app.models.enums import RoleEnum
from app.features.follow_up.models.follow_up import FollowUp
from app.features.group.models.group import Group
from app.features.teacher.models.teacher import Teacher


class GroupsService(BaseService):
    """read : super_admin all | any amin his classes | teacher his own group
    write: super_admin all | any amin his classes
    """

    # --------------------------------------------------------------- queries
    def visible_servants(self):
        """Servants whose roster this login may see."""
        return scope_teachers(self.db, self.db.query(Teacher), self.user)

    def visible_boys(self):
        """Boys this login may file under a servant."""
        if self.user.role == RoleEnum.TEACHER:
            return self.db.query(Boy).filter(
                Boy.id.in_(self._group_boy_ids())
            )
        return scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)

    def visible_rows(self):
        """Group rows this login may see."""
        if self.user.role == RoleEnum.TEACHER:
            return (
                scope_church(self.db.query(Group), Group, self.user)
                .join(Teacher, Group.teacher_id == Teacher.id)
                .filter(Group.teacher_id == self.user.teacher_id)
            )
        mine = self._class_ids()
        query = scope_church(
            self.db.query(Group), Group, self.user
        ).join(Teacher, Group.teacher_id == Teacher.id)
        return query if mine is None else query.filter(Teacher.class_id.in_(mine))

    # ------------------------------------------------------------------ read
    def list(
        self,
        class_id: int | None = None,
        teacher_id: int | None = None,
        team_id: int | None = None,
    ) -> dict:
        """Servants with their boy rosters, plus the boys nobody has yet."""
        team = scoped_team(self.db, self.user, team_id)

        servants_query = self.visible_servants()
        if class_id is not None:
            self.ensure_class(class_id)
            servants_query = servants_query.filter(Teacher.class_id == class_id)
        if teacher_id is not None:
            servants_query = servants_query.filter(Teacher.id == teacher_id)

        boys_query = self.visible_boys()
        if class_id is not None:
            boys_query = boys_query.filter(Boy.class_id == class_id)
        if team is not None:
            boys_query = boys_query.filter(Boy.id.in_(team.boy_ids))
        boys_by_id = {boy.id: boy for boy in boys_query.all()}

        rows_query = self.visible_rows()
        if class_id is not None:
            rows_query = rows_query.filter(Teacher.class_id == class_id)
        if teacher_id is not None:
            rows_query = rows_query.filter(Group.teacher_id == teacher_id)
        if team is not None:
            rows_query = rows_query.filter(
                or_(
                    Group.boy_id.in_(team.boy_ids),
                    Group.teacher_id.in_(team.teacher_ids),
                )
            )

        members: dict[int, list[dict]] = {}
        for row in rows_query.all():
            boy = boys_by_id.get(row.boy_id)  # a servant's own roster
            if boy is not None:
                members.setdefault(row.teacher_id, []).append(_boy_row(boy))

        if team is not None:
            # Keep the boys' current servants even when they are not in the
            # team, plus any servant explicitly assigned to it.
            relevant_ids = list(set(members) | set(team.teacher_ids))
            servants_query = servants_query.filter(Teacher.id.in_(relevant_ids))
        servants = servants_query.order_by(Teacher.teacher_name).all()

        groups = [
            {
                "teacher_id": servant.id,
                "teacher_name": servant.teacher_name,
                "phone": servant.phone,
                "class_id": servant.class_id,
                "note": servant.note,
                "boys_count": len(members.get(servant.id, [])),
                "boys": members.get(servant.id, []),
            }
            for servant in servants
        ]
        grouped = {row["boy_id"] for rows in members.values() for row in rows}
        unassigned = [
            _boy_row(boy) for boy in boys_by_id.values() if boy.id not in grouped
        ]
        return {
            "groups": groups,
            "unassigned": unassigned,
            "unassigned_count": len(unassigned),
        }

    def list_with_stats(
        self,
        class_id: int | None = None,
        teacher_id: int | None = None,
        team_id: int | None = None,
    ) -> dict:
        """:meth:`list` plus the two columns the roster sheet prints - each
        boy's attendance % and his last follow-up. Computed for the whole sheet
        in two bulk queries, never row by row."""
        payload = self.list(
            class_id=class_id, teacher_id=teacher_id, team_id=team_id
        )
        boy_ids = [row["boy_id"] for g in payload["groups"] for row in g["boys"]]
        stats = _attendance_stats(self.db, boy_ids)
        lasts = _last_followups(self.db, boy_ids)
        for group in payload["groups"]:
            for row in group["boys"]:
                row.update(
                    stats.get(
                        row["boy_id"], {"present": 0, "absent": 0, "percent": None}
                    )
                )
                row["last_followup"] = lasts.get(row["boy_id"])
        return payload

    # ----------------------------------------------------------------- write
    def assign(self, teacher_id: int, boy_ids: list[int]) -> dict:
        """Put boys under a servant - a boy belongs to exactly one group, so
        the previous row is dropped before the new one is added."""
        ensure_manager(self.user)
        servant = get_or_404(self.db, Teacher, teacher_id, "Servant")
        self.ensure_class(servant.class_id)

        assigned = 0
        for boy_id in dict.fromkeys(boy_ids):  # de-dupe, keep order
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            ensure_boy_access(self.db, self.user, boy)
            if boy.class_id != servant.class_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Boy '{boy.boy_name}' is not in the servant's class.",
                )
            self._unfile(boy.id)
            self.db.add(
                Group(
                    teacher_id=servant.id,
                    boy_id=boy.id,
                    church_id=self.church_for(
                        class_id=boy.class_id, person=boy
                    ),
                )
            )
            assigned += 1

        commit(self.db, f"Group assign servant={servant.id} boys={assigned}")
        return {
            "teacher_id": servant.id,
            "teacher_name": servant.teacher_name,
            "assigned": assigned,
        }

    def unassign(self, boy_ids: list[int]) -> dict:
        ensure_manager(self.user)
        removed = 0
        for boy_id in dict.fromkeys(boy_ids):
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            ensure_boy_access(self.db, self.user, boy)
            removed += self._unfile(boy.id)
        commit(self.db, f"Group unassign boys={removed}")
        return {"removed": removed}

    def import_rows(self, rows: list[dict]) -> dict:
        """Apply a parsed assignment sheet (``teacher_name|boy_name|class_id``).

        Rows are bucketed per servant first so each servant gets one
        ``assign`` call; a row that cannot be resolved is reported, not fatal.
        """
        ensure_manager(self.user)
        buckets: dict[int, list[int]] = {}
        names: dict[int, str] = {}
        failed: list[dict] = []

        for row in rows:
            try:
                servant = self._find_servant(row["teacher_name"], row["class_id"])
                boy = self._find_boy(row["boy_name"], row["class_id"])
                if boy.class_id != servant.class_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Boy '{boy.boy_name}' and servant "
                            f"'{servant.teacher_name}' are not in the same class."
                        ),
                    )
                bucket = buckets.setdefault(servant.id, [])
                if boy.id not in bucket:
                    bucket.append(boy.id)
                    names[servant.id] = servant.teacher_name
            except HTTPException as exc:
                failed.append({**row, "error": exc.detail})

        created = []
        for servant_id, boy_ids in buckets.items():
            try:
                created.append(self.assign(servant_id, boy_ids))
            except HTTPException as exc:
                failed.append(
                    {
                        "teacher_name": names.get(servant_id),
                        "boy_name": None,
                        "error": exc.detail,
                    }
                )
        return {"created": created, "failed": failed}

    # -------------------------------------------------------------- internals
    def _class_ids(self) -> list[int] | None:
        return my_class_ids(self.db, self.user)

    def _group_boy_ids(self) -> list[int]:
        return [
            row[0]
            for row in self.db.query(Group.boy_id).filter(
                Group.teacher_id == self.user.teacher_id
            )
        ]

    def _unfile(self, boy_id: int) -> int:
        return self.db.query(Group).filter(Group.boy_id == boy_id).delete(
            synchronize_session=False
        )

    def _find_servant(self, name: str, class_id: int) -> Teacher:
        wanted = normalise_name(name)
        for servant in (
            self.visible_servants()
            .filter(Teacher.class_id == class_id)
            .order_by(Teacher.teacher_name)
            .all()
        ):
            if normalise_name(servant.teacher_name) == wanted:
                return servant
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servant '{name}' not found in that class.",
        )

    def _find_boy(self, name: str, class_id: int) -> Boy:
        wanted = normalise_name(name)
        for boy in (
            self.visible_boys()
            .filter(Boy.class_id == class_id)
            .order_by(Boy.boy_name)
            .all()
        ):
            if normalise_name(boy.boy_name) == wanted:
                return boy
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boy '{name}' not found in that class.",
        )


def _boy_row(boy: Boy) -> dict:
    """The boy fields the group screen shows."""
    return {
        "boy_id": boy.id,
        "boy_name": boy.boy_name,
        "phone": boy.phone,
        "phone_2": boy.phone_2,
        "address": boy.address,
        "issue_flag": boy.issue_flag,
        "note": boy.note,
    }


def _attendance_stats(db, boy_ids: list[int]) -> dict[int, dict]:
    """present / absent / percent per boy, in one grouped query."""
    if not boy_ids:
        return {}
    rows = (
        db.query(
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


def _last_followups(db, boy_ids: list[int]) -> dict[int, dict]:
    """The most recent follow-up per boy, newest row first."""
    if not boy_ids:
        return {}
    rows = (
        db.query(FollowUp)
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
