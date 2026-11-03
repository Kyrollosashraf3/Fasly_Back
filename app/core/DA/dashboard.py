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


def _completed_sessions(attends: list, class_ids: set | None = None) -> set[date]:
    """Set of Friday dates where at least one attendance row exists.

    A session is considered "completed" when at least one boy's attendance was
    recorded for that date (optionally filtered to ``class_ids``). Only completed
    sessions count for absence: a Friday with no records was simply not taken yet.
    """
    dates: set[date] = set()
    for a in attends:
        if a.date is None:
            continue
        if class_ids is not None and a.class_id not in class_ids:
            continue
        dates.add(a.date)
    return dates


def _trailing_streak(
    history: list, last_date: date | None, session_dates: set[date] | None = None
) -> int:
    """Consecutive presences counting BACKWARD from the last completed session.

    A boy is counted as absent on a completed session where he has no record.
    The streak stops at the first absence (explicit or implicit).
    """
    if not history or last_date is None:
        return 0

    if session_dates is None:
        # Legacy: only look at recorded rows
        if history[-1].date != last_date:
            return 0
        n = 0
        for r in reversed(history):
            if r.present:
                n += 1
            else:
                break
        return n

    # Build a presence map from recorded rows
    by_date: dict[date, bool] = {r.date: r.present for r in history}
    # Walk completed sessions backwards, anchored at the most recent session
    # completed for this boy's own class (not a global Friday).
    ordered = sorted(session_dates, reverse=True)
    if not ordered:
        return 0
    n = 0
    for d in ordered:
        present = by_date.get(d, False)  # missing record = absent
        if present:
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

    @staticmethod
    def _date_range(date_mode: str) -> tuple[date | None, date | None]:
        """Turn the date filter selection into a ``(from, to)`` window.

        * ``last_friday`` -> that single day (the latest Friday on/before today)
        * ``season``      -> the church service year start until today
        * ``all``         -> no bounds (every recorded day)
        """
        if date_mode == "last_friday":
            day = _last_friday_passed()
            return day, day
        if date_mode == "season":
            return _season_start(), date.today()
        return None, None

    @staticmethod
    def _streak_window(streak_from, streak_to) -> tuple | None:
        """The explicit Friday range the "المواظبون" list is measured over.

        ``None`` keeps the trailing-streak behaviour. A half range is treated as
        that single Friday, and a reversed pair is a client mistake.
        """
        if streak_from is None and streak_to is None:
            return None
        lo = streak_from or streak_to
        hi = streak_to or streak_from
        if lo > hi:
            raise HTTPException(
                status_code=422, detail="streak_from must be on or before streak_to"
            )
        return lo, hi

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
        date_mode: str = "all",
        streak_from=None,
        streak_to=None,
    ) -> dict:
        classes = self._scope_classes(class_id)
        labels = self._class_labels()
        class_set = set(classes)

        # The date filter drives the WHOLE page: a specific Friday, the whole
        # period or the church year so far (see ``_date_range``).
        date_from, date_to = self._date_range(date_mode)

        def in_range(value) -> bool:
            if value is None:
                return False
            if date_from is not None and value < date_from:
                return False
            if date_to is not None and value > date_to:
                return False
            return True

        # Narrow every source row to the classes in scope first, so the class
        # picker really drives the whole page: a super admin who selected one
        # class no longer sees counts summed over every class.
        boys = [b for b in self._boys() if b.class_id in class_set]
        scoped_attends = [a for a in self._attends() if a.class_id in class_set]
        attends = [a for a in scoped_attends if in_range(a.date)]
        checks = [
            c for c in self._checks() if c.class_id in class_set and in_range(c.date)
        ]
        teachers = [t for t in self._teachers() if t.class_id in class_set]
        follow_ups = [
            f
            for f in self._follow_ups()
            if f.class_id in class_set and in_range(f.action_date)
        ]

        boys_by_id = {b.id: b for b in boys}
        teachers_by_id = {t.id: t.teacher_name for t in teachers}
        histories = self._histories(attends)

        # The streak list can be measured over its own Friday range, so it keeps
        # working even when the page filter is narrowed to a single Friday.
        window = self._streak_window(streak_from, streak_to)
        streak_rows = scoped_attends if window is not None else attends
        streak_sessions = self._class_sessions(streak_rows, classes, window)
        streak_histories = (
            histories if window is None else self._histories(streak_rows)
        )

        dates = sorted({a.date for a in attends if a.date})
        last_date = dates[-1] if dates else None
        servant_list = self._servant_scores(checks, teachers_by_id)

        period_days = max(1, period_days)
        period_start = date_from or (date.today() - timedelta(days=period_days))

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
                "date_mode": date_mode,
                "date_from": _iso(date_from),
                "date_to": _iso(date_to),
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
            "attendance": self._attendance_stats(attends, classes, boys),
            "servants": servant_list,
            "top_servants": _top_with_ties(servant_list, top_n),
            "streaks": self._streaks(
                streak_histories, boys_by_id, classes, streak_n, streak_sessions, window
            ),
            "streak_window": {
                "from": _iso(window[0]) if window else None,
                "to": _iso(window[1]) if window else None,
                "by_class": {
                    c: len(sessions) for c, sessions in streak_sessions.items()
                },
            },
            "streak_options": [
                d.isoformat()
                for d in sorted(
                    {a.date for a in scoped_attends if a.date}, reverse=True
                )
            ],
            "last_friday": self._last_friday(
                attends, boys_by_id, boys, classes, last_date
            ),
            "frequent_absent": self._frequent_absent(
                histories, boys_by_id, boys, classes, absent_n, attends
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
    def _class_sessions(rows: list, classes: list[int], window=None) -> dict:
        """Completed Fridays per class, optionally narrowed to a Friday range."""
        out: dict[int, set] = {}
        for c in classes:
            dates = _completed_sessions(rows, {c})
            if window is not None:
                lo, hi = window
                dates = {d for d in dates if lo <= d <= hi}
            out[c] = dates
        return out

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

    def _attendance_stats(self, attends: list, classes: list[int], boys: list) -> dict:
        """Overall and per-class attendance stats with session-aware absence.

        Missing record on a completed session = absent. Sessions with no records
        are ignored.
        """
        boys_by_class: dict[int, list] = {}
        for b in boys:
            boys_by_class.setdefault(b.class_id, []).append(b)

        session_dates_by_class: dict[int, set[date]] = {}
        for a in attends:
            if a.date:
                session_dates_by_class.setdefault(a.class_id, set()).add(a.date)

        present_total = 0
        liturgy_total = 0
        total_total = 0
        absent_total = 0
        by_class = {}
        for c in classes:
            class_boys = boys_by_class.get(c, [])
            sessions = session_dates_by_class.get(c, set())
            n_sessions = len(sessions)
            # Build a lookup: (boy_id, date) -> record
            recs_map: dict[tuple, object] = {}
            for a in attends:
                if a.class_id == c:
                    recs_map[(a.boy_id, a.date)] = a

            p = 0
            l = 0
            total = len(class_boys) * n_sessions
            for b in class_boys:
                for d in sessions:
                    rec = recs_map.get((b.id, d))
                    if rec and rec.present:
                        p += 1
                    if rec and rec.liturgy:
                        l += 1
            absent = total - p
            by_class[c] = {
                "present": p,
                "absent": absent,
                "total": total,
                "percent": _pct(p, total),
                "liturgy": l,
                "liturgy_percent": _pct(l, total),
                "sessions": n_sessions,
            }
            present_total += p
            liturgy_total += l
            total_total += total
            absent_total += absent
        return {
            "present": present_total,
            "absent": absent_total,
            "total": total_total,
            "percent": _pct(present_total, total_total),
            "liturgy_present": liturgy_total,
            "liturgy_percent": _pct(liturgy_total, total_total),
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

    def _streaks(
        self, histories, boys_by_id, classes, streak_n, class_sessions, window=None
    ) -> dict:
        """The «المواظبون على الحضور» list, either a trailing streak or a range.

        Without ``window``: boys present N consecutive fridays up to their
        class's last session. With one (an explicit ``from`` / ``to`` pair):
        boys present on EVERY session of that range, so a single absence inside
        the chosen period drops them.

        ``class_sessions`` is the per-class set of Fridays that counts (see
        ``_class_sessions``): a Friday another class recorded is not a session
        for this class, so it must neither count nor break anything.
        """
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            c = self._boy_class(boys_by_id, boy_id, h[0].class_id)
            if c not in groups:
                continue
            sessions = class_sessions.get(c, set())
            s = _trailing_streak(h, max(sessions) if sessions else None, sessions)
            wanted = len(sessions) if window is not None else streak_n
            if sessions and s >= wanted:
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

    def _last_friday(
        self, attends, boys_by_id, boys: list, classes, last_date
    ) -> dict:
        """Absentees of the last session completed for each boy's class.

        A session is completed per class: a Friday another class recorded is not
        a session for this class, so its boys are neither present nor absent.
        A boy with NO record on his class's last session counts as absent
        (Solution B: only-true recording, missing = absent on completed session).
        """
        class_set = set(classes)
        class_last: dict[int, date] = {}
        for a in attends:
            if a.date is None or a.class_id not in class_set:
                continue
            if a.class_id not in class_last or a.date > class_last[a.class_id]:
                class_last[a.class_id] = a.date

        recs = {(a.boy_id, a.date): a for a in attends}
        absent: list[dict] = []
        present_n = 0
        for b in boys:
            session = class_last.get(b.class_id)
            if session is None:
                # No completed session for this class yet - not "absent".
                continue
            rec = recs.get((b.id, session))
            if rec is not None and rec.present:
                present_n += 1
                continue
            absent.append(
                {
                    "boy_id": b.id,
                    "boy_name": b.boy_name or "—",
                    "class_id": b.class_id,
                    "date": _iso(session),
                }
            )
        absent.sort(key=lambda x: x["boy_name"])
        by_class = {c: [] for c in classes}
        for row in absent:
            if row["class_id"] in by_class:
                by_class[row["class_id"]].append(row)
        return {
            "date": _iso(max(class_last.values())) if class_last else None,
            "dates": {c: _iso(d) for c, d in class_last.items()},
            "present_count": present_n,
            "absent_count": len(absent),
            "absent": absent,
            "by_class": by_class,
        }

    def _frequent_absent(
        self, histories, boys_by_id, boys: list, classes, absent_n, all_attends: list
    ) -> dict:
        """Boys absent on more than N completed sessions, grouped by class.

        Missing record on a completed session = absent (Solution B).
        """
        groups = {c: [] for c in classes}
        # per-class session sets
        class_sessions: dict[int, set[date]] = {}
        for a in all_attends:
            if a.date:
                class_sessions.setdefault(a.class_id, set()).add(a.date)

        # build presence map: boy_id -> {date -> present}
        presence: dict[int, dict[date, bool]] = {}
        for a in all_attends:
            if a.date:
                presence.setdefault(a.boy_id, {})[a.date] = a.present

        for b in boys:
            c = b.class_id
            if c not in groups:
                continue
            sessions = class_sessions.get(c, set())
            n_sessions = len(sessions)
            if not n_sessions:
                continue
            boy_map = presence.get(b.id, {})
            n_present = sum(1 for d in sessions if boy_map.get(d, False))
            n_abs = n_sessions - n_present
            if n_abs > absent_n:
                groups[c].append(
                    {
                        "boy_id": b.id,
                        "boy_name": b.boy_name or "—",
                        "absent_count": n_abs,
                        "present_count": n_present,
                        "percent": _pct(n_present, n_sessions),
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

    # ---------------- birthdays ----------------
    @staticmethod
    def _birthday_occurrence(birth_date: date, year: int) -> date:
        try:
            return birth_date.replace(year=year)
        except ValueError:  # 29 Feb on a non-leap year
            return date(year, 2, 28)

    @classmethod
    def _birthday_offset(cls, birth_date: date, today: date) -> int:
        """Signed days from today to the nearest birthday occurrence."""
        offsets = [
            (cls._birthday_occurrence(birth_date, year) - today).days
            for year in (today.year - 1, today.year, today.year + 1)
        ]
        return min(offsets, key=abs)

    @classmethod
    def _in_birthday_window(
        cls, birth_date: date, window: str, today: date, month: int | None = None
    ) -> bool:
        """A chosen month replaces the quick window."""
        if month is not None:
            return birth_date.month == month
        if window == "month":
            return birth_date.month == today.month
        return abs(cls._birthday_offset(birth_date, today)) <= 7

    def birthdays(
        self,
        kind: str = "boys",
        window: str = "twoweeks",
        class_id: int | None = None,
        month: int | None = None,
    ) -> dict:
        """Upcoming birthdays for boys and/or servants, scoped to the login.

        A teacher only ever sees boys. Every row carries the contact phones,
        attendance %, mass % and - for a boy - his responsible servant.
        """
        from app.core.data.common import ensure_staff

        ensure_staff(self.user)

        classes = self._scope_classes(class_id)
        class_set = set(classes)
        labels = self._class_labels()
        today = date.today()

        want_boys = True
        want_teachers = kind in ("teachers", "all")
        if self.user.role == RoleEnum.TEACHER:
            # A servant only sees boys, whatever he asked for.
            want_teachers = False

        items: list[dict] = []

        if want_boys:
            attends_by_boy: dict[int, list] = {}
            for a in self._attends():
                if a.class_id in class_set:
                    attends_by_boy.setdefault(a.boy_id, []).append(a)
            for b in self._boys():
                if b.class_id not in class_set or b.birth_date is None:
                    continue
                if not self._in_birthday_window(b.birth_date, window, today, month):
                    continue
                recs = attends_by_boy.get(b.id, [])
                present = sum(1 for r in recs if r.present)
                liturgy = sum(1 for r in recs if r.liturgy)
                items.append(
                    {
                        "kind": "boy",
                        "id": b.id,
                        "name": b.boy_name,
                        "birth_date": _iso(b.birth_date),
                        "next_birthday": self._birthday_occurrence(
                            b.birth_date, today.year
                        ).isoformat(),
                        "days_until": self._birthday_offset(b.birth_date, today),
                        "age": b.age,
                        "phone": b.phone,
                        "phone_2": b.phone_2,
                        "class_id": b.class_id,
                        "class_name": labels.get(b.class_id),
                        "servant_name": b.teacher_name,
                        "attendance_percent": _pct(present, len(recs)),
                        "liturgy_percent": _pct(liturgy, len(recs)),
                    }
                )

        if want_teachers:
            checks_by_teacher: dict[int, list] = {}
            for c in self._checks():
                if c.class_id in class_set:
                    checks_by_teacher.setdefault(c.teacher_id, []).append(c)
            for t in self._teachers():
                if (
                    t.class_id is None
                    or t.class_id not in class_set
                    or t.birth_date is None
                ):
                    continue
                if not self._in_birthday_window(t.birth_date, window, today, month):
                    continue
                recs = checks_by_teacher.get(t.id, [])
                present = sum(1 for r in recs if r.attend)
                liturgy = sum(1 for r in recs if r.liturgy)
                items.append(
                    {
                        "kind": "teacher",
                        "id": t.id,
                        "name": t.teacher_name,
                        "birth_date": _iso(t.birth_date),
                        "next_birthday": self._birthday_occurrence(
                            t.birth_date, today.year
                        ).isoformat(),
                        "days_until": self._birthday_offset(t.birth_date, today),
                        "age": t.age,
                        "phone": t.phone,
                        "phone_2": t.phone_2,
                        "class_id": t.class_id,
                        "class_name": labels.get(t.class_id),
                        "servant_name": None,
                        "attendance_percent": _pct(present, len(recs)),
                        "liturgy_percent": _pct(liturgy, len(recs)),
                    }
                )

        # Inside a chosen month the servant walks the list by day, not by distance.
        if month is None:
            items.sort(key=lambda x: (x["days_until"], x["name"]))
        else:
            items.sort(key=lambda x: (int(x["birth_date"].split("-")[2]), x["name"]))
        return {
            "kind": kind,
            "window": window,
            "month": month,
            "today": today.isoformat(),
            "count": len(items),
            "items": items,
        }

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
        # Completed sessions come from every class this boy has records in, so a
        # promoted boy keeps the sessions taken while he was in his old class.
        # A session only counts for the class that actually recorded it.
        boy_class_ids = {r.class_id for r in recs if r.class_id is not None}
        boy_class_ids.add(boy.class_id)
        class_attends = (
            self.db.query(Attend)
            .filter(Attend.class_id.in_(boy_class_ids))
            .all()
        )
        session_dates = _completed_sessions(class_attends, boy_class_ids)
        by_date_rec = {r.date: r for r in recs}
        present_sessions = sum(
            1 for d in session_dates
            if by_date_rec.get(d) and by_date_rec[d].present
        )
        total_sessions = len(session_dates)

        notes = [r.note for r in recs if r.note]
        if boy.note:
            notes.insert(0, f"boy master note: {boy.note}")
        season = self._season_table(recs, session_dates)
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
                "latitude": boy.latitude,
                "longitude": boy.longitude,
                "class_id": boy.class_id,
                "note": boy.note,
                "issue_flag": boy.issue_flag,
            },
            "history": [
                {
                    "id": r.id,
                    "date": _iso(r.date),
                    "present": r.present,
                    "note": r.note,
                }
                for r in recs
            ],
            # session-aware totals: missing record on completed session = absent
            "present": present_sessions,
            "absent": total_sessions - present_sessions,
            "total": total_sessions,
            "percent": _pct(present_sessions, total_sessions),
            "notes": notes,
            "season": season,
            "session_dates": sorted(d.isoformat() for d in session_dates),
            "followups": self._boy_followups(boy_id),
        }

    @staticmethod
    def _season_table(
        recs: list, session_dates: set[date] | None = None
    ) -> dict:
        """Every Friday since season start -> present/absent.

        When ``session_dates`` is provided, only those Fridays are treated as
        completed sessions (missing record = absent). Fridays before the first
        recorded session and with no records are omitted from the grid so the
        frontend can render them as "not taken yet".

        Without ``session_dates`` every Friday since season start is shown,
        and missing record = absent (legacy / single-boy view already correct).
        """
        season_start = _season_start()
        by_date = {r.date: r for r in recs}
        all_season_fridays = _fridays_between(season_start, _last_friday_passed())
        fridays = []
        for d in all_season_fridays:
            # ``id`` rides along so the file can offer the two writes a Friday
            # accepts: delete the row (he was not there after all) or create one
            # for a session that was taken without him.
            record = by_date.get(d)
            if session_dates is not None and d not in session_dates:
                # Not a completed session — show as "pending", not absent
                fridays.append(
                    {
                        "id": record.id if record else None,
                        "date": d.isoformat(),
                        "present": None,  # None = session not taken yet
                        "note": record.note if record else None,
                    }
                )
            else:
                fridays.append(
                    {
                        "id": record.id if record else None,
                        "date": d.isoformat(),
                        "present": record.present if record else False,
                        "note": record.note if record else None,
                    }
                )
        completed = [f for f in fridays if f["present"] is not None]
        present = sum(1 for f in completed if f["present"])
        total_completed = len(completed)
        return {
            "start": season_start.isoformat(),
            "present": present,
            "total": total_completed,
            "percent": _pct(present, total_completed),
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
                "id": r.id,
                "action_date": _iso(r.action_date),
                "teacher_id": r.teacher_id,
                "status": r.status.value,
                "note": r.note,
            }
            for r in recs
        ]
