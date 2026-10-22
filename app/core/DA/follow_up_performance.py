"""follow_up_performance.py - Aggregated analytics for the "أداء الافتقاد"
(Follow-up Performance) module.

Follow-up is the servant's weekly contact with the boys of his group. This
module answers four questions for a chosen period (last week / last month /
the church service year):

    * what share of the boys were reached at all (نسبة الافتقاد)?
    * which boys were followed and which are still pending?
    * how is each servant doing - did he log his group's follow-ups?
    * a ranked list of boys, each with a glimpse of his follow-up history.

``follow_ups.class_id`` is a *historical snapshot*, so a boy counts for the
class he was recorded in even after a promotion. ``groups`` is the only
servant <-> boy link, and it gives every boy his responsible servant.

Each source table is read once, scoped to what the login may see, and the
aggregation is pure arithmetic over the loaded rows (hundreds of boys).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException

from app.core.DA.dashboard import _season_start
from app.core.data.base import BaseService
from app.core.data.common import (
    my_class_id,
    scope_boys,
    scope_checks,
    scope_follow_ups,
    scope_teachers,
)
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.group import Group
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck

#: The period windows the module offers (mirrors the query pattern).
PERIODS = ("week", "month", "season", "all")

#: The five ticks the amin records per servant each Friday (max score 5).
SERVANT_FLAGS = ("attend", "prepare", "liturgy", "follow", "teachers_meeting")

#: Below this average score (out of 5) a servant is flagged for follow-up.
WEAK_SCORE = 3.0


def _pct(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total else 0.0


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


class FollowUpPerformanceService(BaseService):
    """Follow-up analytics. Read-only: the same scope the CRUD routes use.

    A class amin reads his own class, a super admin every class, and a servant
    only his own group and the follow-ups he logged himself.
    """

    # ----------------------------------------------------------------- scope
    def _classes(self):
        """The class catalogue this login may see (a class amin: his own)."""
        query = self.db.query(SchoolClass)
        class_id = my_class_id(self.db, self.user)
        return query if class_id is None else query.filter(SchoolClass.id == class_id)

    def _scope_classes(self, class_id: int | None) -> list[int]:
        if class_id is not None:
            self.ensure_class(class_id)
            return [class_id]
        return [row.id for row in self._classes()]

    def _class_labels(self) -> dict[int, str]:
        return {row.id: row.name for row in self._classes()}

    @staticmethod
    def _period_range(period: str) -> tuple[date | None, date | None]:
        """Turn the period selection into a ``(from, to)`` window.

        * ``week``   -> the last 7 days
        * ``month``  -> the last 30 days
        * ``season`` -> the church service year start until today
        * ``all``    -> no bounds (every recorded day)
        """
        today = date.today()
        if period == "week":
            return today - timedelta(days=7), today
        if period == "month":
            return today - timedelta(days=30), today
        if period == "season":
            return _season_start(), today
        return None, None

    def _servants(self, class_set: set[int], teacher_id: int | None) -> list[Teacher]:
        """Servants in scope (a servant: only himself)."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_teachers(self.db, self.db.query(Teacher), self.user)
        except HTTPException:
            return []
        servants = [t for t in query.all() if t.class_id in class_set]
        if teacher_id is not None:
            servants = [t for t in servants if t.id == teacher_id]
        return servants

    def _boys(
        self, class_set: set[int], teacher_id: int | None, boy_id: int | None
    ) -> list[Boy]:
        """Boys in scope - narrowed to one servant's group / one boy."""
        query = scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)
        boys = [b for b in query.all() if b.class_id in class_set]
        if teacher_id is not None:
            group_boy_ids = self._group_boy_ids(teacher_id)
            boys = [b for b in boys if b.id in group_boy_ids]
        if boy_id is not None:
            boys = [b for b in boys if b.id == boy_id]
        return boys

    def _group_map(self, class_set: set[int]) -> dict[int, int]:
        """``boy_id -> responsible teacher_id`` for the classes in scope."""
        rows = (
            self.db.query(Group.boy_id, Group.teacher_id)
            .join(Teacher, Group.teacher_id == Teacher.id)
            .filter(Teacher.class_id.in_(class_set))
            .all()
        )
        return {boy_id: teacher_id for boy_id, teacher_id in rows}

    def _group_boy_ids(self, teacher_id: int) -> set[int]:
        return {
            row[0]
            for row in self.db.query(Group.boy_id).filter(
                Group.teacher_id == teacher_id
            )
        }

    def _follow_ups(
        self,
        class_set: set[int],
        period_from: date | None,
        period_to: date | None,
        teacher_id: int | None,
    ) -> list[FollowUp]:
        """Follow-up rows in scope, inside the period (a boy never gets here)."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_follow_ups(self.db, self.db.query(FollowUp), self.user)
        except HTTPException:
            return []
        rows = []
        for f in query.all():
            if f.class_id not in class_set or f.action_date is None:
                continue
            if period_from is not None and f.action_date < period_from:
                continue
            if period_to is not None and f.action_date > period_to:
                continue
            if teacher_id is not None and f.teacher_id != teacher_id:
                continue
            rows.append(f)
        return rows

    def _checks(
        self,
        class_set: set[int],
        period_from: date | None,
        period_to: date | None,
        teacher_id: int | None,
    ) -> list[TeacherCheck]:
        """Servant review rows in scope, inside the period (a boy never gets here)."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_checks(self.db, self.db.query(TeacherCheck), self.user)
        except HTTPException:
            return []
        rows = []
        for r in query.all():
            if r.class_id not in class_set or r.date is None:
                continue
            if period_from is not None and r.date < period_from:
                continue
            if period_to is not None and r.date > period_to:
                continue
            if teacher_id is not None and r.teacher_id != teacher_id:
                continue
            rows.append(r)
        return rows

    def performance(
        self,
        class_id: int | None = None,
        period: str = "month",
        teacher_id: int | None = None,
        boy_id: int | None = None,
    ) -> dict:
        if period not in PERIODS:
            period = "month"

        classes = self._scope_classes(class_id)
        class_set = set(classes)
        labels = self._class_labels()
        period_from, period_to = self._period_range(period)

        # A servant only ever sees his own group and the follow-ups he logged.
        if self.user.role == RoleEnum.TEACHER:
            teacher_id = self.user.teacher_id

        boys = self._boys(class_set, teacher_id, boy_id)
        boys_by_id = {b.id: b for b in boys}
        servants = self._servants(class_set, teacher_id)
        servant_names = {t.id: t.teacher_name for t in servants}
        group_map = self._group_map(class_set)
        follow_ups = self._follow_ups(class_set, period_from, period_to, teacher_id)
        checks = self._checks(class_set, period_from, period_to, teacher_id)

        by_boy: dict[int, list[FollowUp]] = {}
        for f in follow_ups:
            by_boy.setdefault(f.boy_id, []).append(f)

        ranking = self._ranking(boys, by_boy, group_map, servant_names, labels)
        followed = sum(1 for row in ranking if row["followed"])
        totals = {
            "boys": len(boys),
            "followed": followed,
            "not_followed": len(boys) - followed,
            "followups": len(follow_ups),
            "percent": _pct(followed, len(boys)),
            "avg": round(len(follow_ups) / len(boys), 1) if boys else 0.0,
        }

        servant_rows = self._servants_report(
            servants, boys_by_id, group_map, by_boy, follow_ups, labels
        )
        needs_attention = self._needs_attention(servants, checks, labels)
        totals["servants"] = len(servant_rows)
        totals["servants_active"] = sum(1 for s in servant_rows if s["active"])
        totals["servants_inactive"] = totals["servants"] - totals["servants_active"]
        totals["needs_attention"] = len(needs_attention)

        return {
            "scope": {
                "classes": classes,
                "class_labels": labels,
                "single_class": len(classes) == 1,
                "period": period,
                "period_from": _iso(period_from),
                "period_to": _iso(period_to),
                "teacher_id": teacher_id,
                "teacher_name": servant_names.get(teacher_id) if teacher_id else None,
                "boy_id": boy_id,
                "boy_name": boys_by_id[boy_id].boy_name if boy_id in boys_by_id else None,
            },
            "totals": totals,
            "by_class": self._by_class(classes, boys, by_boy, follow_ups, labels),
            "servants": servant_rows,
            "needs_attention": needs_attention,
            "ranking": ranking,
        }

    # ------------------------------------------------------- needs attention
    @staticmethod
    def _needs_attention(
        servants: list[Teacher],
        checks: list[TeacherCheck],
        labels: dict[int, str],
    ) -> list[dict]:
        """Servants to follow up with: weak reviews - or no review - in the period.

        A servant's score is the sum of his five ticks per review (max 5). The
        rows carry the contacts, so an amin can call or message him right away.
        """
        agg: dict[int, dict] = {}
        for r in checks:
            row = agg.setdefault(r.teacher_id, {"score": 0, "checks": 0, "last": None})
            row["checks"] += 1
            row["score"] += sum(1 for flag in SERVANT_FLAGS if getattr(r, flag))
            if row["last"] is None or r.date > row["last"]:
                row["last"] = r.date

        rows = []
        for t in servants:
            row = agg.get(t.id)
            if row is None:
                rows.append(
                    {
                        "teacher_id": t.id,
                        "teacher_name": t.teacher_name,
                        "class_id": t.class_id,
                        "class_name": labels.get(t.class_id, ""),
                        "phone": t.phone,
                        "phone_2": t.phone_2,
                        "checks": 0,
                        "score": 0,
                        "avg": 0.0,
                        "last": None,
                        "reason": "no_checks",
                    }
                )
                continue
            avg = round(row["score"] / row["checks"], 2) if row["checks"] else 0.0
            if avg >= WEAK_SCORE:
                continue
            rows.append(
                {
                    "teacher_id": t.id,
                    "teacher_name": t.teacher_name,
                    "class_id": t.class_id,
                    "class_name": labels.get(t.class_id, ""),
                    "phone": t.phone,
                    "phone_2": t.phone_2,
                    "checks": row["checks"],
                    "score": row["score"],
                    "avg": avg,
                    "last": _iso(row["last"]),
                    "reason": "low_score",
                }
            )
        rows.sort(
            key=lambda x: (x["reason"] != "low_score", x["avg"], x["teacher_name"])
        )
        return rows[:10]

    # -------------------------------------------------------------- rollups
    @staticmethod
    def _ranking(
        boys: list[Boy],
        by_boy: dict[int, list[FollowUp]],
        group_map: dict[int, int],
        servant_names: dict[int, str],
        labels: dict[int, str],
    ) -> list[dict]:
        """One row per boy: his responsible servant, count and a short history."""
        rows = []
        for b in boys:
            follows = by_boy.get(b.id, [])
            ordered = sorted(follows, key=lambda r: (r.action_date, r.id), reverse=True)
            last = ordered[0] if ordered else None
            owner_id = group_map.get(b.id)
            rows.append(
                {
                    "boy_id": b.id,
                    "boy_name": b.boy_name,
                    "class_id": b.class_id,
                    "class_name": labels.get(b.class_id, ""),
                    "servant_id": owner_id,
                    "servant_name": servant_names.get(owner_id) if owner_id else None,
                    "count": len(follows),
                    "followed": bool(follows),
                    "first_date": _iso(
                        min((r.action_date for r in follows), default=None)
                    ),
                    "last_date": _iso(last.action_date) if last else None,
                    "last_status": last.status.value if last and last.status else None,
                    "last_note": last.note if last else None,
                    "last_by_id": last.teacher_id if last else None,
                    "last_by_name": servant_names.get(last.teacher_id, "—")
                    if last
                    else None,
                    "history": [
                        {
                            "date": _iso(r.action_date),
                            "status": r.status.value if r.status else None,
                            "teacher_id": r.teacher_id,
                            "teacher_name": servant_names.get(r.teacher_id, "—"),
                            "note": r.note,
                        }
                        for r in ordered[:6]
                    ],
                }
            )
        rows.sort(key=lambda x: (-x["count"], x["boy_name"]))
        return rows

    @staticmethod
    def _servants_report(
        servants: list[Teacher],
        boys_by_id: dict[int, Boy],
        group_map: dict[int, int],
        by_boy: dict[int, list[FollowUp]],
        follow_ups: list[FollowUp],
        labels: dict[int, str],
    ) -> list[dict]:
        """Per-servant: his group coverage and how many follow-ups he logged."""
        logged_by: dict[int, list[FollowUp]] = {}
        for f in follow_ups:
            logged_by.setdefault(f.teacher_id, []).append(f)

        rows = []
        for t in servants:
            group_ids = {
                boy_id
                for boy_id, teacher_id in group_map.items()
                if teacher_id == t.id and boy_id in boys_by_id
            }
            covered = sum(1 for boy_id in group_ids if by_boy.get(boy_id))
            logged = logged_by.get(t.id, [])
            last = max((f.action_date for f in logged), default=None)
            rows.append(
                {
                    "teacher_id": t.id,
                    "teacher_name": t.teacher_name,
                    "class_id": t.class_id,
                    "class_name": labels.get(t.class_id, ""),
                    "phone": t.phone,
                    "phone_2": t.phone_2,
                    "group_size": len(group_ids),
                    "covered": covered,
                    "not_covered": len(group_ids) - covered,
                    "percent": _pct(covered, len(group_ids)),
                    "logged": len(logged),
                    "last": _iso(last),
                    "active": bool(logged),
                }
            )
        rows.sort(key=lambda s: (-s["percent"], s["teacher_name"]))
        return rows

    @staticmethod
    def _by_class(
        classes: list[int],
        boys: list[Boy],
        by_boy: dict[int, list[FollowUp]],
        follow_ups: list[FollowUp],
        labels: dict[int, str],
    ) -> list[dict]:
        rows = []
        for c in classes:
            class_boys = [b for b in boys if b.class_id == c]
            followed = sum(1 for b in class_boys if by_boy.get(b.id))
            rows.append(
                {
                    "class_id": c,
                    "class_name": labels.get(c, ""),
                    "boys": len(class_boys),
                    "followed": followed,
                    "not_followed": len(class_boys) - followed,
                    "followups": sum(1 for f in follow_ups if f.class_id == c),
                    "percent": _pct(followed, len(class_boys)),
                }
            )
        return rows
