"""groups.py - Follow-up groups: assign boys to servants.

Each boy may belong to one servant's main follow-up group
(stored on the boy as follow_teacher_id + denormalized name).
Admin: any class. Amin: only own class.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

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

logger = get_logger(__name__)

BOYS = settings.COLLECTION_BOY
TEACHERS = settings.COLLECTION_TEACHER
ATTENDS = settings.COLLECTION_ATTEND
FOLLOWUPS = settings.COLLECTION_FOLLOWUP


def _pct(present: int, total: int) -> float:
    return round(present * 100 / total, 1) if total else 0.0


class GroupsService(ClassScopedService):
    """Assign boys to servants and read back grouped rosters with summaries."""

    def assign(self, teacher_id: str, boy_ids: list[str]) -> dict:
        """Put boy_ids into teacher_id's group (replaces their old group)."""
        teacher = get_doc_or_404(self.db.collection(TEACHERS), teacher_id, "Teacher")
        teacher_data = teacher.to_dict() or {}
        ensure_record_class_access(teacher_data.get("class_name"), self.current_user)
        teacher_class = teacher_data.get("class_name")

        assigned = 0
        for boy_id in dict.fromkeys(boy_ids):  # de-dupe, keep order
            boy = get_doc_or_404(self.db.collection(BOYS), boy_id, "Boy")
            boy_data = boy.to_dict() or {}
            ensure_record_class_access(boy_data.get("class_name"), self.current_user)
            if boy_data.get("class_name") != teacher_class:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Boy '{boy_data.get('boy_name')}' is not in the servant's class.",
                )
            boy.reference.update({
                "follow_teacher_id": teacher_id,
                "follow_teacher_name": teacher_data.get("teacher_name"),
                "updated_at": datetime.now(timezone.utc),
            })
            assigned += 1
        logger.info(f"Group assigned: teacher={teacher_id} boys={assigned} by {self.current_user.mail}")
        return {"teacher_id": teacher_id,
                "teacher_name": teacher_data.get("teacher_name"),
                "assigned": assigned}

    def unassign(self, boy_ids: list[str]) -> dict:
        """Remove boys from any group."""
        removed = 0
        for boy_id in dict.fromkeys(boy_ids):
            boy = get_doc_or_404(self.db.collection(BOYS), boy_id, "Boy")
            boy_data = boy.to_dict() or {}
            ensure_record_class_access(boy_data.get("class_name"), self.current_user)
            boy.reference.update({
                "follow_teacher_id": None,
                "follow_teacher_name": None,
                "updated_at": datetime.now(timezone.utc),
            })
            removed += 1
        return {"removed": removed}

    def _find_exact(self, collection: str, name_field: str, name: str,
                    class_name: str, label: str):
        """One doc matching (name, class) — errors if zero or ambiguous."""
        docs = list(where_eq(where_eq(self.db.collection(collection),
                                       name_field, name),
                              "class_name", class_name).stream())
        if not docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} '{name}' not found in class {class_name}.")
        if len(docs) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Multiple {label}s named '{name}' — make names unique first.")
        return docs[0]

    def assign_import(self, rows: list[dict]) -> dict:
        """Bulk assign from sheet rows {teacher_name, boy_name, class_name}.

        Names are resolved per row (must be unique within the class).
        Bad rows don't stop the rest.
        """
        assigned: list[dict] = []
        failed: list[dict] = []
        for r in rows:
            try:
                teacher = self._find_exact(TEACHERS, "teacher_name",
                                           r["teacher_name"], r["class_name"], "Teacher")
                teacher_data = teacher.to_dict() or {}
                ensure_record_class_access(teacher_data.get("class_name"), self.current_user)
                boy = self._find_exact(BOYS, "boy_name",
                                       r["boy_name"], r["class_name"], "Boy")
                boy_data = boy.to_dict() or {}
                ensure_record_class_access(boy_data.get("class_name"), self.current_user)
                boy.reference.update({
                    "follow_teacher_id": teacher.id,
                    "follow_teacher_name": teacher_data.get("teacher_name"),
                    "updated_at": datetime.now(timezone.utc),
                })
                assigned.append({"boy_name": r["boy_name"],
                                 "teacher_name": r["teacher_name"]})
            except HTTPException as exc:
                failed.append({"boy_name": r.get("boy_name"),
                               "teacher_name": r.get("teacher_name"),
                               "error": exc.detail})
        logger.info(f"Group import done: assigned={len(assigned)} failed={len(failed)}")
        return {"assigned": assigned, "failed": failed}

    def _scope_classes(self, class_name) -> list[str]:
        from app.models.enums import ClassEnum

        resolved = self.resolve_class(class_name)
        if resolved is None:
            return [m.value for m in ClassEnum]
        return [enum_value(resolved)]

    def _boys_in(self, classes: list[str]) -> list[dict]:
        col = self.db.collection(BOYS)
        query = where_eq(col, "class_name", classes[0]) if len(classes) == 1 else col
        return [dict(d.to_dict() or {}, _id=d.id)
                for d in query.stream()
                if (d.to_dict() or {}).get("class_name") in classes]

    def _teachers_in(self, classes: list[str]) -> list[dict]:
        col = self.db.collection(TEACHERS)
        query = where_eq(col, "class_name", classes[0]) if len(classes) == 1 else col
        docs = [dict(d.to_dict() or {}, _id=d.id)
                for d in query.stream()
                if (d.to_dict() or {}).get("class_name") in classes]
        docs.sort(key=lambda t: t.get("teacher_name") or "")
        return docs

    def _boy_summary(self, boy_id: str, attends_by_boy: dict, fu_by_boy: dict,
                     boy: dict) -> dict:
        recs = attends_by_boy.get(boy_id, [])
        present = sum(1 for r in recs if r.get("attend") == "y")
        fus = fu_by_boy.get(boy_id, [])
        last_fu = fus[0] if fus else None  # pre-sorted newest first
        return {
            "boy_id": boy_id,
            "boy_name": boy.get("boy_name"),
            "phone": boy.get("phone"),
            "phone_2": boy.get("phone_2"),
            "address": boy.get("address"),
            "issue_flag": boy.get("issue_flag", False),
            "present": present, "absent": len(recs) - present,
            "total": len(recs), "percent": _pct(present, len(recs)),
            "last_followup": ({
                "action_date": last_fu.get("action_date"),
                "teacher_name": last_fu.get("teacher_name"),
                "status": last_fu.get("status"),
                "note": last_fu.get("note"),
            } if last_fu else None),
            "followups_count": len(fus),
            "has_note": bool(boy.get("note")),
            "note": boy.get("note"),
        }

    def list_groups(self, class_name=None, teacher_id: str | None = None) -> dict:
        """Servants with their boy rosters + per-boy history summaries."""
        classes = self._scope_classes(class_name)
        teachers = self._teachers_in(classes)
        if teacher_id:
            teachers = [t for t in teachers if t["_id"] == teacher_id]
        boys = self._boys_in(classes)

        attends_by_boy: dict[str, list] = {}
        for d in self.db.collection(ATTENDS).stream():
            r = d.to_dict() or {}
            if r.get("class_name") in classes and is_past_friday(r.get("action_date")):
                attends_by_boy.setdefault(r.get("boy_id", ""), []).append(r)
        fu_by_boy: dict[str, list] = {}
        for d in self.db.collection(FOLLOWUPS).stream():
            r = d.to_dict() or {}
            if r.get("class_name") in classes:
                fu_by_boy.setdefault(r.get("boy_id", ""), []).append(r)
        for lst in fu_by_boy.values():
            lst.sort(key=lambda r: str(r.get("action_date") or ""), reverse=True)

        groups = []
        grouped_ids = set()
        for t in teachers:
            members = [b for b in boys if b.get("follow_teacher_id") == t["_id"]]
            members.sort(key=lambda b: b.get("boy_name") or "")
            for b in members:
                grouped_ids.add(b["_id"])
            groups.append({
                "teacher_id": t["_id"],
                "teacher_name": t.get("teacher_name"),
                "phone": t.get("phone"),
                "duty": t.get("duty"),
                "class_name": t.get("class_name"),
                "boys_count": len(members),
                "boys": [self._boy_summary(b["_id"], attends_by_boy, fu_by_boy, b)
                         for b in members],
            })
        unassigned = [self._boy_summary(b["_id"], attends_by_boy, fu_by_boy, b)
                      for b in sorted(boys, key=lambda b: b.get("boy_name") or "")
                      if b["_id"] not in grouped_ids]
        return {"classes": classes, "groups": groups, "unassigned": unassigned,
                "unassigned_count": len(unassigned)}
