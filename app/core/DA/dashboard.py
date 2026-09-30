"""dashboard.py - Aggregated analytics for the Dashboard module.

Each source table is read once (scoped to what the login may see) and
aggregated in Python - data size is small (hundreds of boys/checks).
Two endpoints serve the whole dashboard: one summary and one boy drill-down.

Score (servant performance) = sum of trues per teacher-check:
    attend (1) + prepare + liturgy + follow  (max 4/check)

Everything is grouped by ``class_id`` - a class name never enters an
aggregation, so historical rows keep counting for the class they were
recorded in even after boys are promoted.
"""

from datetime import date, timedelta

from app.config.logger import get_logger
from app.core.data.base import ClassScopedService
from app.core.data.common import get_or_404, is_past_friday
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck

logger = get_logger(__name__)

# First Friday of the church service year: fixed around 18 Sep
# (the Friday after Nayrouz feast).
SEASON_MONTH, SEASON_DAY = 9, 18


def _pct(present: int, total: int) -> float:
    return round(present * 100 / total, 1) if total else 0.0


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _season_start() -> date:
    """First Friday of the church service year.

    Fixed around 18 Sep; if that day isn't a Friday take the next one.
    If this year's hasn't come yet, use last year's.
    """
    today = date.today()
    start = date(today.year, SEASON_MONTH, SEASON_DAY)
    if today < start:
        start = date(today.year - 1, SEASON_MONTH, SEASON_DAY)
    while start.weekday() != 4:  # advance to Friday
        start += timedelta(days=1)
    return start


def _last_friday_passed() -> date:
    """Most recent Friday on or before today."""
    d = date.today()
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def _fridays_between(start: date, end: date) -> list[date]:
    """Every Friday from start to end (inclusive)."""
    out = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def _trailing_streak(history: list, last_date: date | None) -> int:
    """Consecutive presences counting BACKWARD from the last recorded friday.

    The boy must have a record on the last friday itself; the count stops at
    the first absence going back.
    """
    if not history or last_date is None:
        return 0
    if history[-1].date != last_date:
        return 0
    n = 0
    for r in reversed(history):
        if r.present:
            n += 1
        else:
            break
    return n


def _per_date(recs: list, last_n: int, present_fn) -> list[dict]:
    """Present/absent/total per day for the last N recorded days (ascending)."""
    last_n = max(1, last_n)
    days = sorted({r.date for r in recs if r.date})
    out = []
    for d in days[-last_n:]:
        day = [r for r in recs if r.date == d]
        present = sum(1 for r in day if present_fn(r))
        out.append(
            {
                "date": d.isoformat(),
                "present": present,
                "absent": len(day) - present,
                "total": len(day),
            }
        )
    return out


def _top_with_ties(ranked: list[dict], n: int) -> list[dict]:
    """First N of a score-sorted list, plus everyone tied with the Nth."""
    n = max(1, n)
    if len(ranked) <= n:
        return ranked
    cutoff = ranked[n - 1]["score"]
    return [s for s in ranked if s["score"] >= cutoff]


class DashboardService(ClassScopedService):
    """Dashboard analytics. Read-only: the same scope the CRUD routes use."""

    # ----------------------------------------------------------------- scope
    def _scope_classes(self, class_id: int | None) -> list[int]:
        if class_id is not None:
            self.scope.ensure_class(class_id)
            return [class_id]
        query = self.scope.restrict_class(self.db.query(SchoolClass), SchoolClass)
        return [row.id for row in query.all()]

    def _class_labels(self) -> dict[int, str]:
        query = self.scope.restrict_class(self.db.query(SchoolClass), SchoolClass)
        return {row.id: row.name for row in query.all()}

    def _boys(self) -> list[Boy]:
        return self.scope.restrict_boys(self.db.query(Boy), Boy, Boy.id).all()

    def _attends(self) -> list[Attend]:
        query = self.scope.restrict_boys(self.db.query(Attend), Attend, Attend.boy_id)
        return [row for row in query.all() if is_past_friday(row.date)]

    def _checks(self) -> list[TeacherCheck]:
        """A boy's login never reaches the servant review sheet."""
        if self.scope.role == RoleEnum.USER:
            return []
        query = self.db.query(TeacherCheck)
        if self.scope.role == RoleEnum.TEACHER:
            query = query.filter(
                TeacherCheck.teacher_id == self.scope.teacher_id
            )
        else:
            query = self.scope.restrict_class(query, TeacherCheck)
        return [row for row in query.all() if is_past_friday(row.date)]

    def _teachers_by_id(self) -> dict[int, str]:
        if self.scope.role == RoleEnum.USER:
            return {}
        query = self.db.query(Teacher)
        if self.scope.role == RoleEnum.TEACHER:
            query = query.filter(Teacher.id == self.scope.teacher_id)
        else:
            query = self.scope.restrict_class(query, Teacher)
        return {row.id: row.teacher_name for row in query.all()}

    # ---------------- main summary ----------------
    def summary(
        self,
        class_id: int | None = None,
        streak_n: int = 4,
        absent_n: int = 4,
        top_n: int = 5,
        trend_n: int = 8,
        teacher_trend_n: int = 8,
    ) -> dict:
        classes = self._scope_classes(class_id)
        labels = self._class_labels()

        boys = self._boys()
        attends = self._attends()
        checks = self._checks()
        boys_by_id = {b.id: b for b in boys}
        teachers_by_id = self._teachers_by_id()
        histories = self._histories(attends)

        dates = sorted({a.date for a in attends if a.date})
        last_date = dates[-1] if dates else None
        servant_list = self._servant_scores(checks, teachers_by_id)

        result = {
            "scope": {
                "classes": classes,
                "class_labels": labels,
                "single_class": len(classes) == 1,
                "streak_n": streak_n,
                "absent_n": absent_n,
                "top_n": max(1, top_n),
                "trend_n": max(1, trend_n),
                "teacher_trend_n": max(1, teacher_trend_n),
            },
            "counts": {
                "boys": len(boys),
                "fridays": len(dates),
                "teachers": len(teachers_by_id),
            },
            "boys_trend": _per_date(attends, trend_n, lambda r: r.present),
            "teachers_trend": _per_date(
                checks, teacher_trend_n, lambda r: r.attend
            ),
            "attendance": self._attendance_stats(attends, classes),
            "servants": servant_list,
            "top_servants": _top_with_ties(servant_list, top_n),
            "streaks": self._streaks(
                histories, boys_by_id, classes, last_date, streak_n
            ),
            "last_friday": self._last_friday(
                attends, boys_by_id, classes, last_date
            ),
            "frequent_absent": self._frequent_absent(
                histories, boys_by_id, classes, absent_n
            ),
        }
        logger.info(
            "Dashboard summary classes=%s attends=%d boys=%d",
            classes,
            len(attends),
            len(boys),
        )
        return result

    @staticmethod
    def _histories(attends: list) -> dict:
        """Per-boy records sorted by date (ascending)."""
        histories: dict = {}
        for a in attends:
            histories.setdefault(a.boy_id, []).append(a)
        for h in histories.values():
            h.sort(key=lambda r: r.date)
        return histories

    @staticmethod
    def _attendance_stats(attends: list, classes: list[int]) -> dict:
        present = sum(1 for a in attends if a.present)
        by_class = {}
        for c in classes:
            recs = [a for a in attends if a.class_id == c]
            p = sum(1 for r in recs if r.present)
            by_class[c] = {
                "present": p,
                "absent": len(recs) - p,
                "total": len(recs),
                "percent": _pct(p, len(recs)),
            }
        return {
            "present": present,
            "absent": len(attends) - present,
            "total": len(attends),
            "percent": _pct(present, len(attends)),
            "by_class": by_class,
        }

    @staticmethod
    def _boy_name(boys_by_id: dict, boy_id) -> str:
        boy = boys_by_id.get(boy_id)
        return boy.boy_name if boy is not None and boy.boy_name else "—"

    def _boy_class(self, boys_by_id: dict, boy_id, fallback: int | None = None):
        boy = boys_by_id.get(boy_id)
        if boy is not None:
            return boy.class_id
        return fallback

    def _streaks(self, histories, boys_by_id, classes, last_date, streak_n) -> dict:
        """Boys present N consecutive fridays up to the last recorded one."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            s = _trailing_streak(h, last_date)
            if s >= streak_n:
                c = self._boy_class(boys_by_id, boy_id, h[0].class_id)
                if c in groups:
                    groups[c].append(
                        {
                            "boy_id": boy_id,
                            "boy_name": self._boy_name(boys_by_id, boy_id),
                            "streak": s,
                        }
                    )
        for lst in groups.values():
            lst.sort(key=lambda x: (-x["streak"], x["boy_name"]))
        return groups

    def _last_friday(self, attends, boys_by_id, classes, last_date) -> dict:
        """Absentees of the last recorded friday, grouped by class."""
        absent, present_n = [], 0
        if last_date:
            for a in attends:
                if a.date != last_date:
                    continue
                if a.present:
                    present_n += 1
                else:
                    absent.append(
                        {
                            "boy_id": a.boy_id,
                            "boy_name": self._boy_name(boys_by_id, a.boy_id),
                            "class_id": a.class_id,
                        }
                    )
            absent.sort(key=lambda x: x["boy_name"])
        by_class = {c: [] for c in classes}
        for row in absent:
            if row["class_id"] in by_class:
                by_class[row["class_id"]].append(row)
        return {
            "date": _iso(last_date),
            "present_count": present_n,
            "absent_count": len(absent),
            "absent": absent,
            "by_class": by_class,
        }

    def _frequent_absent(self, histories, boys_by_id, classes, absent_n) -> dict:
        """Boys absent on more than N fridays, grouped by class."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            n_abs = sum(1 for r in h if not r.present)
            if n_abs > absent_n:
                c = self._boy_class(boys_by_id, boy_id, h[0].class_id)
                if c in groups:
                    groups[c].append(
                        {
                            "boy_id": boy_id,
                            "boy_name": self._boy_name(boys_by_id, boy_id),
                            "absent_count": n_abs,
                            "present_count": len(h) - n_abs,
                            "percent": _pct(len(h) - n_abs, len(h)),
                        }
                    )
        for lst in groups.values():
            lst.sort(key=lambda x: (-x["absent_count"], x["boy_name"]))
        return groups

    @staticmethod
    def _servant_scores(checks: list, teachers_by_id: dict) -> list[dict]:
        """Per-servant true-counts, sorted by score desc then name."""
        servants: dict = {}
        for r in checks:
            s = servants.setdefault(
                r.teacher_id,
                {
                    "teacher_id": r.teacher_id,
                    "teacher_name": teachers_by_id.get(r.teacher_id, "—"),
                    "class_id": r.class_id,
                    "score": 0,
                    "checks": 0,
                    "attend": 0,
                    "prepare": 0,
                    "liturgy": 0,
                    "follow": 0,
                },
            )
            s["checks"] += 1
            for flag in ("attend", "prepare", "liturgy", "follow"):
                if getattr(r, flag):
                    s[flag] += 1
                    s["score"] += 1
        return sorted(
            servants.values(), key=lambda s: (-s["score"], s["teacher_name"])
        )

    # ---------------- boy drill-down ----------------
    def boy_profile(self, boy_id: int) -> dict:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        self.scope.ensure_boy_visible(boy)

        recs = (
            self.db.query(Attend)
            .filter(Attend.boy_id == boy_id)
            .order_by(Attend.date)
            .all()
        )
        present = sum(1 for r in recs if r.present)
        notes = [r.note for r in recs if r.note]
        if boy.note:
            notes.insert(0, f"boy master note: {boy.note}")
        return {
            "boy": {
                "id": boy.id,
                "boy_name": boy.boy_name,
                "gender": boy.gender.value,
                "birth_date": _iso(boy.birth_date),
                "age": boy.age,
                "phone": boy.phone,
                "phone_2": boy.phone_2,
                "zone": boy.zone,
                "address": boy.address,
                "location": boy.location,
                "class_id": boy.class_id,
                "note": boy.note,
                "issue_flag": boy.issue_flag,
            },
            "history": [
                {
                    "date": _iso(r.date),
                    "present": r.present,
                    "note": r.note,
                }
                for r in recs
            ],
            "present": present,
            "absent": len(recs) - present,
            "total": len(recs),
            "percent": _pct(present, len(recs)),
            "notes": notes,
            "season": self._season_table(recs),
            "followups": self._boy_followups(boy_id),
        }

    @staticmethod
    def _season_table(recs: list) -> dict:
        """Every Friday since season start -> present/absent (missing = absent)."""
        season_start = _season_start()
        by_date = {r.date: r for r in recs}
        fridays = [
            {
                "date": d.isoformat(),
                "present": by_date[d].present if d in by_date else False,
                "note": by_date[d].note if d in by_date else None,
            }
            for d in _fridays_between(season_start, _last_friday_passed())
        ]
        present = sum(1 for f in fridays if f["present"])
        return {
            "start": season_start.isoformat(),
            "present": present,
            "total": len(fridays),
            "percent": _pct(present, len(fridays)),
            "fridays": fridays,
        }

    def _boy_followups(self, boy_id: int) -> list[dict]:
        """Follow-up log for one boy, newest first."""
        recs = (
            self.db.query(FollowUp)
            .filter(FollowUp.boy_id == boy_id)
            .order_by(FollowUp.action_date.desc(), FollowUp.id.desc())
            .all()
        )
        return [
            {
                "action_date": _iso(r.action_date),
                "teacher_id": r.teacher_id,
                "status": r.status.value,
                "note": r.note,
            }
            for r in recs
        ]
