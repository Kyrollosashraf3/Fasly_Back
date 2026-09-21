"""dashboard.py - Aggregated analytics for the Dashboard module.

All computations read the raw collections once and aggregate in Python
(data size is small: hundreds of boys/checks). One endpoint serves the
whole dashboard so the frontend needs a single request.

Score (servant performance) = sum of trues per teacher-check:
    attend=='y' (1) + prepare_flag + liturgy_flag + follow_flag  (max 4/check)
"""

from datetime import date, timedelta

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import (
    ensure_record_class_access,
    enum_value,
    get_doc_or_404,
    is_past_friday,
    where_eq,
)
from app.models.enums import ClassEnum

logger = get_logger(__name__)

ATTENDS = settings.COLLECTION_ATTEND
BOYS = settings.COLLECTION_BOY
CHECKS = settings.COLLECTION_TEACHER_CHECK
FOLLOWUPS = settings.COLLECTION_FOLLOWUP

ALL_CLASSES = [m.value for m in ClassEnum]

# First Friday of the church service year: fixed around 18 Sep
# (the Friday after Nayrouz feast).
SEASON_MONTH, SEASON_DAY = 9, 18


def _pct(present: int, total: int) -> float:
    return round(present * 100 / total, 1) if total else 0.0


_is_past_friday = is_past_friday  # shared Friday rule (see core.data.common)


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


def _fridays_between(start: date, end: date) -> list[str]:
    """Every Friday from start to end (inclusive) as ISO strings."""
    out = []
    d = start
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def _trailing_streak(history: list[dict], last_date: str | None) -> int:
    """Consecutive 'y' counting BACKWARD from the last recorded friday.

    The boy must have a record on the last friday itself; the count
    stops at the first absence going back.
    """
    if not history or last_date is None:
        return 0
    if str(history[-1].get("action_date")) != last_date:
        return 0
    n = 0
    for r in reversed(history):
        if r.get("attend") == "y":
            n += 1
        else:
            break
    return n


def _per_date(recs: list[dict], last_n: int) -> list[dict]:
    """Present/absent/total per day for the last N recorded days (ascending)."""
    last_n = max(1, last_n)
    days = sorted({str(r.get("action_date") or "") for r in recs if r.get("action_date")})
    out = []
    for d in days[-last_n:]:
        day = [r for r in recs if str(r.get("action_date")) == d]
        present = sum(1 for r in day if r.get("attend") == "y")
        out.append({"date": d, "present": present,
                    "absent": len(day) - present, "total": len(day)})
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
        return [enum_value(resolved)]

    def _read(self, collection: str, classes: list[str]) -> list[dict]:
        """Stream raw docs, filtered to scope classes (single query if one)."""
        col = self.db.collection(collection)
        query = where_eq(col, "class_name", classes[0]) if len(classes) == 1 else col
        out = []
        for d in query.stream():
            data = d.to_dict() or {}
            if data.get("class_name") in classes:
                data["_id"] = d.id
                out.append(data)
        return out

    # ---------------- main summary ----------------
    def summary(self, class_name=None, streak_n: int = 4, absent_n: int = 4,
                top_n: int = 5, trend_n: int = 8, teacher_trend_n: int = 8) -> dict:
        classes = self._scope_classes(class_name)

        boys = self._read(BOYS, classes)
        attends = [a for a in self._read(ATTENDS, classes)
                   if _is_past_friday(str(a.get("action_date") or ""))]
        checks = [r for r in self._read(CHECKS, classes)
                  if _is_past_friday(str(r.get("action_date") or ""))]
        boys_by_id = {b["_id"]: b for b in boys}
        histories = self._histories(attends)

        dates = sorted({str(a.get("action_date") or "") for a in attends if a.get("action_date")})
        last_date = dates[-1] if dates else None
        servant_list = self._servant_scores(checks)

        result = {
            "scope": {"classes": classes, "single_class": len(classes) == 1,
                      "streak_n": streak_n, "absent_n": absent_n,
                      "top_n": max(1, top_n),
                      "trend_n": max(1, trend_n),
                      "teacher_trend_n": max(1, teacher_trend_n)},
            "counts": {"boys": len(boys), "fridays": len(dates),
                       "teachers": len(servant_list)},
            "boys_trend": _per_date(attends, trend_n),
            "teachers_trend": _per_date(checks, teacher_trend_n),
            "attendance": self._attendance_stats(attends, classes),
            "servants": servant_list,
            "top_servants": _top_with_ties(servant_list, top_n),
            "streaks": self._streaks(histories, boys_by_id, classes, last_date, streak_n),
            "last_friday": self._last_friday(attends, boys_by_id, classes, last_date),
            "frequent_absent": self._frequent_absent(histories, boys_by_id, classes, absent_n),
        }
        logger.info(f"Dashboard summary classes={classes} attends={len(attends)} boys={len(boys)}")
        return result

    @staticmethod
    def _histories(attends: list[dict]) -> dict[str, list[dict]]:
        """Per-boy records sorted by date (ascending)."""
        histories: dict[str, list[dict]] = {}
        for a in attends:
            histories.setdefault(a.get("boy_id", ""), []).append(a)
        for h in histories.values():
            h.sort(key=lambda r: str(r.get("action_date") or ""))
        return histories

    @staticmethod
    def _attendance_stats(attends: list[dict], classes: list[str]) -> dict:
        present = sum(1 for a in attends if a.get("attend") == "y")
        by_class = {}
        for c in classes:
            recs = [a for a in attends if a.get("class_name") == c]
            p = sum(1 for r in recs if r.get("attend") == "y")
            by_class[c] = {"present": p, "absent": len(recs) - p,
                           "total": len(recs), "percent": _pct(p, len(recs))}
        return {"present": present, "absent": len(attends) - present,
                "total": len(attends), "percent": _pct(present, len(attends)),
                "by_class": by_class}

    @staticmethod
    def _boy_name(boys_by_id: dict, boy_id: str, history: list) -> str:
        return (boys_by_id.get(boy_id, {}).get("boy_name")
                or (history[0].get("boy_name") if history else None) or "؟")

    @staticmethod
    def _boy_class(boys_by_id: dict, boy_id: str, history: list):
        return (boys_by_id.get(boy_id, {}).get("class_name")
                or (history[0].get("class_name") if history else None))

    def _streaks(self, histories, boys_by_id, classes, last_date, streak_n) -> dict:
        """Boys present N consecutive fridays up to the last recorded one."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            s = _trailing_streak(h, last_date)
            if s >= streak_n:
                c = self._boy_class(boys_by_id, boy_id, h)
                if c in groups:
                    groups[c].append({"boy_id": boy_id,
                                      "boy_name": self._boy_name(boys_by_id, boy_id, h),
                                      "streak": s})
        for lst in groups.values():
            lst.sort(key=lambda x: (-x["streak"], x["boy_name"]))
        return groups

    def _last_friday(self, attends, boys_by_id, classes, last_date) -> dict:
        """Absentees of the last recorded friday, grouped by class."""
        absent, present_n = [], 0
        if last_date:
            for a in attends:
                if str(a.get("action_date")) != last_date:
                    continue
                if a.get("attend") == "y":
                    present_n += 1
                else:
                    absent.append({
                        "boy_id": a.get("boy_id"),
                        "boy_name": self._boy_name(boys_by_id, a.get("boy_id", ""), [a]),
                        "class_name": a.get("class_name"),
                    })
            absent.sort(key=lambda x: x["boy_name"])
        by_class = {c: [] for c in classes}
        for row in absent:
            if row["class_name"] in by_class:
                by_class[row["class_name"]].append(row)
        return {"date": last_date, "present_count": present_n,
                "absent_count": len(absent), "absent": absent, "by_class": by_class}

    def _frequent_absent(self, histories, boys_by_id, classes, absent_n) -> dict:
        """Boys absent on more than N fridays, grouped by class."""
        groups = {c: [] for c in classes}
        for boy_id, h in histories.items():
            n_abs = sum(1 for r in h if r.get("attend") != "y")
            if n_abs > absent_n:
                c = self._boy_class(boys_by_id, boy_id, h)
                if c in groups:
                    groups[c].append({
                        "boy_id": boy_id,
                        "boy_name": self._boy_name(boys_by_id, boy_id, h),
                        "absent_count": n_abs,
                        "present_count": len(h) - n_abs,
                        "percent": _pct(len(h) - n_abs, len(h)),
                    })
        for lst in groups.values():
            lst.sort(key=lambda x: (-x["absent_count"], x["boy_name"]))
        return groups

    @staticmethod
    def _servant_scores(checks: list[dict]) -> list[dict]:
        """Per-servant true-counts, sorted by score desc then name."""
        servants: dict[str, dict] = {}
        for r in checks:
            tid = r.get("teacher_id", "")
            s = servants.setdefault(tid, {
                "teacher_id": tid,
                "teacher_name": r.get("teacher_name") or "؟",
                "class_name": r.get("class_name"),
                "score": 0, "checks": 0,
                "attend": 0, "prepare": 0, "liturgy": 0, "follow": 0,
            })
            s["checks"] += 1
            if r.get("attend") == "y":
                s["attend"] += 1
                s["score"] += 1
            if r.get("prepare_flag"):
                s["prepare"] += 1
                s["score"] += 1
            if r.get("liturgy_flag"):
                s["liturgy"] += 1
                s["score"] += 1
            if r.get("follow_flag"):
                s["follow"] += 1
                s["score"] += 1
        return sorted(servants.values(), key=lambda s: (-s["score"], s["teacher_name"]))

    # ---------------- boy drill-down ----------------
    def boy_profile(self, boy_id: str) -> dict:
        doc = get_doc_or_404(self.db.collection(BOYS), boy_id, "Boy")
        boy = doc.to_dict() or {}
        ensure_record_class_access(boy.get("class_name"), self.current_user)

        recs = [d.to_dict() or {} for d in
                where_eq(self.db.collection(ATTENDS), "boy_id", boy_id).stream()]
        recs.sort(key=lambda r: str(r.get("action_date") or ""))
        present = sum(1 for r in recs if r.get("attend") == "y")
        notes = [r.get("note") for r in recs if r.get("note")]
        if boy.get("note"):
            notes.insert(0, f"ملاحظة الملف: {boy.get('note')}")
        return {
            "boy": {"id": boy_id, "boy_name": boy.get("boy_name"),
                    "gender": boy.get("gender"), "birth_date": boy.get("birth_date"),
                    "age": boy.get("age"), "phone": boy.get("phone"),
                    "phone_2": boy.get("phone_2"), "address": boy.get("address"),
                    "location": boy.get("location"),
                    "class_name": boy.get("class_name"),
                    "note": boy.get("note"), "issue_flag": boy.get("issue_flag", False)},
            "history": [{"action_date": r.get("action_date"), "attend": r.get("attend"),
                         "note": r.get("note")} for r in recs],
            "present": present, "absent": len(recs) - present,
            "total": len(recs), "percent": _pct(present, len(recs)),
            "notes": notes,
            "season": self._season_table(recs),
            "followups": self._boy_followups(boy_id),
        }

    @staticmethod
    def _season_table(recs: list[dict]) -> dict:
        """Every Friday since season start -> present/absent (missing = absent)."""
        season_start = _season_start()
        by_date = {str(r.get("action_date")): r for r in recs}
        fridays = [
            {"action_date": d,
             "attend": (by_date[d].get("attend") if d in by_date else "n"),
             "note": (by_date[d].get("note") if d in by_date else None)}
            for d in _fridays_between(season_start, _last_friday_passed())
        ]
        present = sum(1 for f in fridays if f["attend"] == "y")
        return {"start": season_start.isoformat(), "present": present,
                "total": len(fridays), "percent": _pct(present, len(fridays)),
                "fridays": fridays}

    def _boy_followups(self, boy_id: str) -> list[dict]:
        """Follow-up log for one boy, newest first."""
        recs = [d.to_dict() or {} for d in
                where_eq(self.db.collection(FOLLOWUPS), "boy_id", boy_id).stream()]
        recs.sort(key=lambda r: str(r.get("action_date") or ""), reverse=True)
        return [{"action_date": r.get("action_date"),
                 "teacher_name": r.get("teacher_name"),
                 "status": r.get("status"), "note": r.get("note")} for r in recs]
