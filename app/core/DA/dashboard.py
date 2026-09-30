"""dashboard.py - Aggregated analytics for the Dashboard module.

Each source table is read once (scoped to the visible classes) and
aggregated in Python - data size is small (hundreds of boys/checks).
One endpoint serves the whole dashboard so the frontend needs a single
request.

Score (servant performance) = sum of trues per teacher-check:
    attend=='y' (1) + prepare_flag + liturgy_flag + follow_flag  (max 4/check)
"""

from datetime import date, timedelta

from app.config.logger import get_logger
from app.core.data.base import ClassScopedService
from app.core.data.common import ensure_record_class_access, get_or_404, is_past_friday
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.enums import AttendEnum, ClassEnum
from app.models.follow_up import FollowUp
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck

logger = get_logger(__name__)

ALL_CLASSES = [m.value for m in ClassEnum]

# First Friday of the church service year: fixed around 18 Sep
# (the Friday after Nayrouz feast).
SEASON_MONTH, SEASON_DAY = 9, 18

PRESENT = AttendEnum.YES


def _pct(present: int, total: int) -> float:
    return round(present * 100 / total, 1) if total else 0.0


def _class_value(value) -> str | None:
    return value.value if hasattr(value, "value") else value


def _is_present(record) -> bool:
    return record.attend == PRESENT


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

    The boy must have a record on the last friday itself; the count
    stops at the first absence going back.
    """
    if not history or last_date is None:
        return 0
    if history[-1].action_date != last_date:
        return 0
    n = 0
    for r in reversed(history):
        if _is_present(r):
            n += 1
        else:
            break
    return n


def _per_date(recs: list, last_n: int) -> list[dict]:
    """Present/absent/total per day for the last N recorded days (ascending)."""
    last_n = max(1, last_n)
    days = sorted({r.action_date for r in recs if r.action_date})
    out = []
    for d in days[-last_n:]:
        day = [r for r in recs if r.action_date == d]
        present = sum(1 for r in day if _is_present(r))
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
    """Dashboard analytics. Admin: any/all classes. Amin: own class only."""

    def _scope_classes(self, class_name) -> list[str]:
        resolved = self.resolve_class(class_name)
        if resolved is None:
            return list(ALL_CLASSES)
        return [_class_value(resolved)]

    def _read(self, model, classes: list[str]) -> list:
        """Rows filtered to the scope classes."""
        return self.db.query(model).filter(model.class_name.in_(classes)).all()

    # ---------------- main summary ----------------
    def summary(self, class_name=None, streak_n: int = 4, absent_n: int = 4,
                top_n: int = 5, trend_n: int = 8, teacher_trend_n: int = 8) -> dict:
        classes = self._scope_classes(class_name)

        boys = self._read(Boy, classes)
        attends = [a for a in self._read(Attend, classes) if is_past_friday(a.action_date)]
        checks = [r for r in self._read(TeacherCheck, classes) if is_past_friday(r.action_date)]
        boys_by_id = {b.id: b for b in boys}
        histories = self._histories(attends)

        dates = sorted({a.action_date for a in attends if a.action_date})
        last_date = dates[-1] if dates else None
        servant_list = self._servant_scores(checks)

        result = {
            "scope": {
                "classes": classes,
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
                "teachers": len(servant_list),
            },
            "boys_trend": _per_date(attends, trend_n),
            "teachers_trend": _per_date(checks, teacher_trend_n),
            "attendance": self._attendance_stats(attends, classes),
            "servants": servant_list,
            "top_servants": _top_with_ties(servant_list, top_n),
            "streaks": self._streaks(histories, boys_by_id, classes, last_date, streak_n),
            "last_friday": self._last_friday(attends, boys_by_id, classes, last_date),
            "frequent_absent": self._frequent_absent(
                histories, boys_by_id, classes, absent_n
            ),
        }
        logger.info(
            f"Dashboard summary classes={classes} attends={len(attends)} boys={len(boys)}"
        )
        return result

    @staticmethod
    def _histories(attends: list) -> dict:
        """Per-boy records sorted by date (ascending)."""
        histories: dict = {}
        for a in attends:
            histories.setdefault(a.boy_id, []).append(a)
        for h in histories.values():
            h.sort(key=lambda r: r.action_date)
        return histories

    @staticmethod
    def _attendance_stats(attends: list, classes: list[str]) -> dict:
        present = sum(1 for a in attends if _is_present(a))
        by_class = {}
        for c in classes:
            recs = [a for a in attends if _class_value(a.class_name) == c]
            p = sum(1 for r in recs if _is_present(r))
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
    def _boy_name(boys_by_id: dict, boy_id, history: list) -> str:
        boy = boys_by_id.get(boy_id)
        if boy is not None and boy.boy_name:
            return boy.boy_name
        if history and history[0].boy_name:
            return history[0].boy_name
        return "—"

    @staticmethod
    def _boy_class(boys_by_id: dict, boy_id, history: list):
        boy = boys_by_id.get(boy_id)
        if boy is not None and boy.class_name is not None:
            return _class_value(boy.class_name)
        if history and history[0].class_name is not None:
            return _class_value(history[0].class_name)
        return None

    def _streaks(self, histories, boys_by_id, classes, last_date, streak_n) -> dict:
        """Boys present N consecutive fridays up to the last recorded one."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            s = _trailing_streak(h, last_date)
            if s >= streak_n:
                c = self._boy_class(boys_by_id, boy_id, h)
                if c in groups:
                    groups[c].append(
                        {
                            "boy_id": boy_id,
                            "boy_name": self._boy_name(boys_by_id, boy_id, h),
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
                if a.action_date != last_date:
                    continue
                if _is_present(a):
                    present_n += 1
                else:
                    absent.append(
                        {
                            "boy_id": a.boy_id,
                            "boy_name": self._boy_name(boys_by_id, a.boy_id, [a]),
                            "class_name": _class_value(a.class_name),
                        }
                    )
            absent.sort(key=lambda x: x["boy_name"])
        by_class = {c: [] for c in classes}
        for row in absent:
            if row["class_name"] in by_class:
                by_class[row["class_name"]].append(row)
        return {
            "date": last_date.isoformat() if last_date else None,
            "present_count": present_n,
            "absent_count": len(absent),
            "absent": absent,
            "by_class": by_class,
        }

    def _frequent_absent(self, histories, boys_by_id, classes, absent_n) -> dict:
        """Boys absent on more than N fridays, grouped by class."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            n_abs = sum(1 for r in h if not _is_present(r))
            if n_abs > absent_n:
                c = self._boy_class(boys_by_id, boy_id, h)
                if c in groups:
                    groups[c].append(
                        {
                            "boy_id": boy_id,
                            "boy_name": self._boy_name(boys_by_id, boy_id, h),
                            "absent_count": n_abs,
                            "present_count": len(h) - n_abs,
                            "percent": _pct(len(h) - n_abs, len(h)),
                        }
                    )
        for lst in groups.values():
            lst.sort(key=lambda x: (-x["absent_count"], x["boy_name"]))
        return groups

    @staticmethod
    def _servant_scores(checks: list) -> list[dict]:
        """Per-servant true-counts, sorted by score desc then name."""
        servants: dict = {}
        for r in checks:
            s = servants.setdefault(
                r.teacher_id,
                {
                    "teacher_id": r.teacher_id,
                    "teacher_name": r.teacher_name or "—",
                    "class_name": _class_value(r.class_name),
                    "score": 0,
                    "checks": 0,
                    "attend": 0,
                    "prepare": 0,
                    "liturgy": 0,
                    "follow": 0,
                },
            )
            s["checks"] += 1
            if _is_present(r):
                s["attend"] += 1
                s["score"] += 1
            if r.prepare_flag:
                s["prepare"] += 1
                s["score"] += 1
            if r.liturgy_flag:
                s["liturgy"] += 1
                s["score"] += 1
            if r.follow_flag:
                s["follow"] += 1
                s["score"] += 1
        return sorted(servants.values(), key=lambda s: (-s["score"], s["teacher_name"]))

    # ---------------- boy drill-down ----------------
    def boy_profile(self, boy_id: int) -> dict:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_record_class_access(boy.class_name, self.current_user)

        recs = (
            self.db.query(Attend)
            .filter(Attend.boy_id == boy_id)
            .order_by(Attend.action_date)
            .all()
        )
        present = sum(1 for r in recs if _is_present(r))
        notes = [r.note for r in recs if r.note]
        if boy.note:
            notes.insert(0, f"boy master note: {boy.note}")
        return {
            "boy": {
                "id": boy.id,
                "boy_name": boy.boy_name,
                "gender": _class_value(boy.gender),
                "birth_date": boy.birth_date.isoformat() if boy.birth_date else None,
                "age": boy.age,
                "phone": boy.phone,
                "phone_2": boy.phone_2,
                "address": boy.address,
                "location": boy.location,
                "class_name": _class_value(boy.class_name),
                "note": boy.note,
                "issue_flag": boy.issue_flag,
            },
            "history": [
                {
                    "action_date": r.action_date.isoformat() if r.action_date else None,
                    "attend": _class_value(r.attend),
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
        by_date = {r.action_date: r for r in recs}
        fridays = [
            {
                "action_date": d.isoformat(),
                "attend": (
                    _class_value(by_date[d].attend) if d in by_date else AttendEnum.NO.value
                ),
                "note": by_date[d].note if d in by_date else None,
            }
            for d in _fridays_between(season_start, _last_friday_passed())
        ]
        present = sum(1 for f in fridays if f["attend"] == AttendEnum.YES.value)
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
            .order_by(FollowUp.action_date.desc())
            .all()
        )
        return [
            {
                "action_date": r.action_date.isoformat() if r.action_date else None,
                "teacher_name": r.teacher_name,
                "status": _class_value(r.status),
                "note": r.note,
            }
            for r in recs
        ]
