"""dashboard.py - Aggregated analytics for the Dashboard module.

Each source table is read once (scoped to what the login may see) and
aggregated in Python - data size is small (hundreds of boys/checks).
Two endpoints serve the whole dashboard: one summary and one boy drill-down.

Score (servant performance) = sum of trues per teacher-check:
    attend + prepare + liturgy + follow + teachers_meeting  (max 5/check)

Everything is grouped by ``class_id`` - a class name never enters an
aggregation, so historical rows keep counting for the class they were
recorded in even after boys are promoted.
"""

from datetime import date, timedelta

from fastapi import HTTPException

from app.config.logger import get_logger
from app.core.data.base import BaseService
from app.core.data.common import (
    ensure_boy_access,
    ensure_roles,
    get_or_404,
    is_past_friday,
    my_class_id,
    scope_boys,
    scope_checks,
    scope_follow_ups,
    scope_teachers,
)
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


def _per_date(recs: list, last_n: int, counters: dict) -> list[dict]:
    """One row per recorded day for the last N days (ascending).

    ``counters`` maps a field name to the predicate that counts it that day, so
    the boys' trend can carry both ``present`` and ``liturgy`` in one series.
    ``absent`` is derived from ``present`` when that key is present.
    """
    last_n = max(1, last_n)
    days = sorted({r.date for r in recs if r.date})
    out = []
    for d in days[-last_n:]:
        day = [r for r in recs if r.date == d]
        row = {"date": d.isoformat(), "total": len(day)}
        for key, fn in counters.items():
            row[key] = sum(1 for r in day if fn(r))
        if "present" in row:
            row["absent"] = len(day) - row["present"]
        out.append(row)
    return out


def _top_with_ties(ranked: list[dict], n: int) -> list[dict]:
    """First N of a score-sorted list, plus everyone tied with the Nth."""
    n = max(1, n)
    if len(ranked) <= n:
        return ranked
    cutoff = ranked[n - 1]["score"]
    return [s for s in ranked if s["score"] >= cutoff]


class DashboardService(BaseService):
    """Dashboard analytics. Read-only: the same scope the CRUD routes use.

    Everything below the ``---`` is pure arithmetic over rows already loaded
    (the dataset is hundreds of boys, not millions), so it never touches the
    database again.
    """

    # ----------------------------------------------------------------- scope
    def _scope_classes(self, class_id: int | None) -> list[int]:
        if class_id is not None:
            self.ensure_class(class_id)
            return [class_id]
        return [row.id for row in self._classes()]

    def _classes(self):
        """The class catalogue this login may see.

        A class amin is pinned to his own class; a super admin sees every class.
        The filter is on ``SchoolClass.id`` (its own PK) - there is no
        ``classes.class_id`` column.
        """
        query = self.db.query(SchoolClass)
        class_id = my_class_id(self.db, self.user)
        return query if class_id is None else query.filter(SchoolClass.id == class_id)

    def _class_labels(self) -> dict[int, str]:
        return {row.id: row.name for row in self._classes()}

    def _boys(self) -> list[Boy]:
        return self._boys_query().all()

    def _boys_query(self):
        return scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)

    def _attends(self) -> list[Attend]:
        query = scope_boys(
            self.db, self.db.query(Attend), Attend, self.user, Attend.boy_id
        )
        return [row for row in query.all() if is_past_friday(row.date)]

    def _checks(self) -> list[TeacherCheck]:
        """A boy's login never reaches the servant review sheet."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_checks(self.db, self.db.query(TeacherCheck), self.user)
        except HTTPException:
            return []
        return [row for row in query.all() if is_past_friday(row.date)]

    def _teachers(self) -> list[Teacher]:
        """Servants this login may see (a boy's login never gets here)."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_teachers(self.db, self.db.query(Teacher), self.user)
        except HTTPException:
            return []
        return query.all()

    def _teachers_by_id(self) -> dict[int, str]:
        return {t.id: t.teacher_name for t in self._teachers()}

    def _follow_ups(self) -> list[FollowUp]:
        """Follow-up contacts this login may see (a boy's login never gets here)."""
        if self.user.role == RoleEnum.USER:
            return []
        try:
            query = scope_follow_ups(self.db, self.db.query(FollowUp), self.user)
        except HTTPException:
            return []
        return query.all()

    # ---------------- main summary ----------------
    def summary(
        self,
        class_id: int | None = None,
        streak_n: int = 4,
        absent_n: int = 4,
        top_n: int = 5,
        trend_n: int = 8,
        teacher_trend_n: int = 8,
        period_days: int = 30,
    ) -> dict:
        classes = self._scope_classes(class_id)
        labels = self._class_labels()
        class_set = set(classes)

        # Narrow every source row to the classes in scope first, so the class
        # picker really drives the whole page: a super admin who selected one
        # class no longer sees counts summed over every class.
        boys = [b for b in self._boys() if b.class_id in class_set]
        attends = [a for a in self._attends() if a.class_id in class_set]
        checks = [c for c in self._checks() if c.class_id in class_set]
        teachers = [t for t in self._teachers() if t.class_id in class_set]
        follow_ups = [f for f in self._follow_ups() if f.class_id in class_set]

        boys_by_id = {b.id: b for b in boys}
        teachers_by_id = {t.id: t.teacher_name for t in teachers}
        histories = self._histories(attends)

        dates = sorted({a.date for a in attends if a.date})
        last_date = dates[-1] if dates else None
        servant_list = self._servant_scores(checks, teachers_by_id)

        period_days = max(1, period_days)
        period_start = date.today() - timedelta(days=period_days)

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
                "period_days": period_days,
                "period_start": period_start.isoformat(),
            },
            "counts": {
                "boys": len(boys),
                "fridays": len(dates),
                "teachers": len(teachers),
            },
            "boys_trend": _per_date(
                attends,
                trend_n,
                {"present": lambda r: r.present, "liturgy": lambda r: r.liturgy},
            ),
            "teachers_trend": _per_date(
                checks, teacher_trend_n, {"present": lambda r: r.attend}
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
            "follow": {
                "period_days": period_days,
                "period_start": period_start.isoformat(),
                "boys": self._follow_coverage(boys, follow_ups, classes, period_start, "boy"),
                "servants": self._follow_coverage(
                    teachers, follow_ups, classes, period_start, "teacher"
                ),
            },
            "confession": {
                "period_days": period_days,
                "period_start": period_start.isoformat(),
                "boys": self._late_confession(boys, classes, period_start, "boy"),
                "servants": self._late_confession(
                    teachers, classes, period_start, "teacher"
                ),
            },
        }
        logger.info(
            "Dashboard summary classes=%s attends=%d boys=%d teachers=%d",
            classes,
            len(attends),
            len(boys),
            len(teachers),
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
    def _empty_groups(classes: list[int]) -> dict:
        return {c: [] for c in classes}

    def _follow_coverage(
        self, people: list, follow_ups: list, classes: list[int], period_start, kind: str
    ) -> dict:
        """Who logged / received a follow-up inside the period, grouped by class.

        ``kind`` is ``"boy"`` (people are boys, keyed by ``boy_id``) or
        ``"teacher"`` (people are servants, keyed by ``teacher_id``).
        """
        person_fk = "boy_id" if kind == "boy" else "teacher_id"
        name_key = "boy_name" if kind == "boy" else "teacher_name"
        recent = [
            f
            for f in follow_ups
            if f.action_date and f.action_date >= period_start
        ]
        by_person: dict = {}
        for f in recent:
            by_person.setdefault(getattr(f, person_fk), []).append(f)

        done = self._empty_groups(classes)
        todo = self._empty_groups(classes)
        for p in people:
            rows = by_person.get(getattr(p, "id"), [])
            entry = {
                person_fk: p.id,
                name_key: getattr(p, name_key),
                "class_id": p.class_id,
            }
            if rows:
                entry["count"] = len(rows)
                entry["last"] = max(r.action_date for r in rows).isoformat()
                done.setdefault(p.class_id, []).append(entry)
            else:
                todo.setdefault(p.class_id, []).append(entry)

        for groups in (done, todo):
            for rows in groups.values():
                rows.sort(key=lambda x: x[name_key])
        return {
            "done": done,
            "todo": todo,
            "done_count": sum(len(v) for v in done.values()),
            "todo_count": sum(len(v) for v in todo.values()),
        }

    def _late_confession(
        self, people: list, classes: list[int], period_start, kind: str
    ) -> dict:
        """People whose last confession/visit is missing or older than the period."""
        person_fk = "boy_id" if kind == "boy" else "teacher_id"
        name_key = "boy_name" if kind == "boy" else "teacher_name"
        late = self._empty_groups(classes)
        ok = 0
        for p in people:
            last = p.last_visit_date
            if last is None or last < period_start:
                late.setdefault(p.class_id, []).append(
                    {
                        person_fk: p.id,
                        name_key: getattr(p, name_key),
                        "class_id": p.class_id,
                        "last_visit_date": _iso(last),
                        "days": (date.today() - last).days if last else None,
                    }
                )
            else:
                ok += 1
        for rows in late.values():
            rows.sort(
                key=lambda x: (x["last_visit_date"] is not None, x["last_visit_date"] or "")
            )
        return {
            "late": late,
            "late_count": sum(len(v) for v in late.values()),
            "ok_count": ok,
        }

    @staticmethod
    def _attendance_stats(attends: list, classes: list[int]) -> dict:
        present = sum(1 for a in attends if a.present)
        liturgy = sum(1 for a in attends if a.liturgy)
        by_class = {}
        for c in classes:
            recs = [a for a in attends if a.class_id == c]
            p = sum(1 for r in recs if r.present)
            l = sum(1 for r in recs if r.liturgy)
            by_class[c] = {
                "present": p,
                "absent": len(recs) - p,
                "total": len(recs),
                "percent": _pct(p, len(recs)),
                "liturgy": l,
                "liturgy_percent": _pct(l, len(recs)),
            }
        return {
            "present": present,
            "absent": len(attends) - present,
            "total": len(attends),
            "percent": _pct(present, len(attends)),
            "liturgy_present": liturgy,
            "liturgy_percent": _pct(liturgy, len(attends)),
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

    #: The five ticks the amin records per servant each Friday (max score 5).
    SERVANT_FLAGS = ("attend", "prepare", "liturgy", "follow", "teachers_meeting")

    @staticmethod
    def _servant_scores(checks: list, teachers_by_id: dict) -> list[dict]:
        """Per-servant true-counts, sorted by score desc then name.

        Score = attend + prepare + liturgy + follow + teachers_meeting (max 5).
        """
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
                    **{flag: 0 for flag in DashboardService.SERVANT_FLAGS},
                },
            )
            s["checks"] += 1
            for flag in DashboardService.SERVANT_FLAGS:
                if getattr(r, flag):
                    s[flag] += 1
                    s["score"] += 1
        return sorted(
            servants.values(), key=lambda s: (-s["score"], s["teacher_name"])
        )

    # ---------------- boy drill-down ----------------
    def boy_profile(self, boy_id: int) -> dict:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_boy_access(self.db, self.user, boy)

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
