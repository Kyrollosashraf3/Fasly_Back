"""dashboard.py - Aggregated analytics for the Dashboard module.

All computations read the raw collections once and aggregate in Python
(data size is small: hundreds of boys/checks). One endpoint serves the
whole dashboard so the frontend needs a single request.

Score (servant performance) = sum of trues per teacher-check:
    attend=='y' (1) + prepare_flag + liturgy_flag + follow_flag  (max 4/check)
"""

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import ensure_record_class_access, enum_value, where_eq
from app.models.enums import ClassEnum

logger = get_logger(__name__)

ATTENDS = settings.COLLECTION_ATTEND
BOYS = settings.COLLECTION_BOY
CHECKS = settings.COLLECTION_TEACHER_CHECK

ALL_CLASSES = [m.value for m in ClassEnum]


def _pct(present: int, total: int) -> float:
    return round(present * 100 / total, 1) if total else 0.0


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
    def summary(self, class_name=None, streak_n: int = 4, absent_n: int = 4) -> dict:
        classes = self._scope_classes(class_name)
        single = len(classes) == 1

        boys = self._read(BOYS, classes)
        attends = self._read(ATTENDS, classes)
        checks = self._read(CHECKS, classes)

        boys_by_id = {b["_id"]: b for b in boys}

        # ---- 1) attendance rate ----
        present = sum(1 for a in attends if a.get("attend") == "y")
        total = len(attends)
        by_class: dict[str, dict] = {}
        for c in classes:
            recs = [a for a in attends if a.get("class_name") == c]
            p = sum(1 for a in recs if a.get("attend") == "y")
            by_class[c] = {"present": p, "absent": len(recs) - p,
                           "total": len(recs), "percent": _pct(p, len(recs))}

        # ---- per-boy histories (sorted by date) ----
        histories: dict[str, list[dict]] = {}
        for a in attends:
            histories.setdefault(a.get("boy_id", ""), []).append(a)
        for h in histories.values():
            h.sort(key=lambda r: str(r.get("action_date") or ""))

        def max_streak(h: list[dict]) -> int:
            best = cur = 0
            for r in h:
                if r.get("attend") == "y":
                    cur += 1
                    best = max(best, cur)
                else:
                    cur = 0
            return best

        # ---- 4) n consecutive presences ----
        streaks: dict[str, list[dict]] = {c: [] for c in classes}
        for boy_id, h in histories.items():
            s = max_streak(h)
            if s >= streak_n:
                b = boys_by_id.get(boy_id, {})
                c = b.get("class_name") or (h[0].get("class_name") if h else None)
                if c in streaks:
                    streaks[c].append({
                        "boy_id": boy_id,
                        "boy_name": b.get("boy_name") or h[0].get("boy_name") or "؟",
                        "streak": s,
                    })
        for lst in streaks.values():
            lst.sort(key=lambda x: (-x["streak"], x["boy_name"]))

        # ---- 5) absent last recorded friday ----
        dates = sorted({str(a.get("action_date") or "") for a in attends if a.get("action_date")})
        last_date = dates[-1] if dates else None
        last_absent: list[dict] = []
        last_present_n = 0
        if last_date:
            for a in attends:
                if str(a.get("action_date")) != last_date:
                    continue
                if a.get("attend") == "y":
                    last_present_n += 1
                else:
                    b = boys_by_id.get(a.get("boy_id", ""), {})
                    last_absent.append({
                        "boy_id": a.get("boy_id"),
                        "boy_name": b.get("boy_name") or a.get("boy_name") or "؟",
                        "class_name": a.get("class_name"),
                    })
            last_absent.sort(key=lambda x: x["boy_name"])
        last_by_class: dict[str, list[dict]] = {c: [] for c in classes}
        for row in last_absent:
            if row["class_name"] in last_by_class:
                last_by_class[row["class_name"]].append(row)

        # ---- 6) absent more than n fridays ----
        absent_groups: dict[str, list[dict]] = {c: [] for c in classes}
        for boy_id, h in histories.items():
            n_abs = sum(1 for r in h if r.get("attend") != "y")
            if n_abs > absent_n:
                n_pre = len(h) - n_abs
                b = boys_by_id.get(boy_id, {})
                c = b.get("class_name") or (h[0].get("class_name") if h else None)
                if c in absent_groups:
                    absent_groups[c].append({
                        "boy_id": boy_id,
                        "boy_name": b.get("boy_name") or h[0].get("boy_name") or "؟",
                        "absent_count": n_abs,
                        "present_count": n_pre,
                        "percent": _pct(n_pre, len(h)),
                    })
        for lst in absent_groups.values():
            lst.sort(key=lambda x: (-x["absent_count"], x["boy_name"]))

        # ---- 2+3) servant performance ----
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
        servant_list = sorted(servants.values(),
                              key=lambda s: (-s["score"], s["teacher_name"]))

        result = {
            "scope": {"classes": classes, "single_class": single,
                      "streak_n": streak_n, "absent_n": absent_n},
            "counts": {"boys": len(boys), "fridays": len(dates),
                       "teachers": len(servants)},
            "attendance": {"present": present, "absent": total - present,
                           "total": total, "percent": _pct(present, total),
                           "by_class": by_class},
            "servants": servant_list,
            "top_servants": servant_list[:5],
            "streaks": streaks,
            "last_friday": {"date": last_date, "present_count": last_present_n,
                            "absent_count": len(last_absent),
                            "absent": last_absent, "by_class": last_by_class},
            "frequent_absent": absent_groups,
        }
        logger.info(f"Dashboard summary classes={classes} attends={total} boys={len(boys)}")
        return result

    # ---------------- boy drill-down ----------------
    def boy_profile(self, boy_id: str) -> dict:
        doc = self.db.collection(BOYS).document(boy_id).get()
        if not doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Boy not found.")
        boy = doc.to_dict() or {}
        ensure_record_class_access(boy.get("class_name"), self.current_user)

        recs = [d.to_dict() or {}
                for d in where_eq(self.db.collection(ATTENDS), "boy_id", boy_id).stream()]
        recs.sort(key=lambda r: str(r.get("action_date") or ""))
        present = sum(1 for r in recs if r.get("attend") == "y")
        history = [{"action_date": r.get("action_date"),
                    "attend": r.get("attend"),
                    "note": r.get("note")} for r in recs]
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
            "history": history,
            "present": present, "absent": len(recs) - present,
            "total": len(recs), "percent": _pct(present, len(recs)),
            "notes": notes,
        }
