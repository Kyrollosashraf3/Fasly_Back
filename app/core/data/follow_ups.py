from datetime import date

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import (
    append_boy_note,
    date_to_str,
    ensure_record_class_access,
    enum_value,
    parse_date,
    where_eq,
)
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUpCreate, FollowUpResponse, FollowUpUpdate

logger = get_logger(__name__)

COLLECTION = settings.COLLECTION_FOLLOWUP
TEACHERS_COLLECTION = settings.COLLECTION_TEACHER
BOYS_COLLECTION = settings.COLLECTION_BOY


def _doc_to_response(doc_id: str, data: dict) -> FollowUpResponse:
    return FollowUpResponse(
        id=doc_id,
        teacher_id=data.get("teacher_id", ""),
        teacher_name=data.get("teacher_name"),
        boy_id=data.get("boy_id", ""),
        boy_name=data.get("boy_name"),
        class_name=data.get("class_name"),
        action_date=parse_date(data.get("action_date")),
        status=data.get("status"),
        note=data.get("note"),
    )


class FollowUpService(ClassScopedService):
    """Weekly follow-up log: one document per (teacher, boy, week).

    Admin: any class. Amin: only own class (resolved from the boy).
    """

    def _col(self):
        return self.db.collection(COLLECTION)

    def _resolve_teacher(self, teacher_id: str) -> dict:
        doc = self.db.collection(TEACHERS_COLLECTION).document(teacher_id).get()
        if not doc.exists:
            logger.warning(f"FollowUp rejected: teacher id={teacher_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher id={teacher_id} not found.",
            )
        return doc.to_dict()

    def _resolve_boy(self, boy_id: str) -> dict:
        doc = self.db.collection(BOYS_COLLECTION).document(boy_id).get()
        if not doc.exists:
            logger.warning(f"FollowUp rejected: boy id={boy_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Boy id={boy_id} not found.",
            )
        data = doc.to_dict()
        ensure_record_class_access(data.get("class_name"), self.current_user)
        return data

    def create(self, data: FollowUpCreate) -> FollowUpResponse:
        teacher = self._resolve_teacher(data.teacher_id)
        boy = self._resolve_boy(data.boy_id)
        action_date = date_to_str(data.action_date or date.today())
        _, doc_ref = self._col().add(
            {
                "teacher_id": data.teacher_id,
                "teacher_name": teacher.get("teacher_name"),
                "boy_id": data.boy_id,
                "boy_name": boy.get("boy_name"),
                "class_name": boy.get("class_name"),
                "action_date": action_date,
                "status": enum_value(data.status),
                "note": data.note,
                "recorded_by": self.user_id,
            }
        )
        logger.info(
            f"FollowUp created id={doc_ref.id} teacher={data.teacher_id} "
            f"boy={data.boy_id} status={data.status}"
        )
        append_boy_note(self.db, data.boy_id, data.note,
                        tag=f"{action_date} - افتقاد ({teacher.get('teacher_name') or ''})".strip())
        return self.get(doc_ref.id)

    def get(self, record_id: str) -> FollowUpResponse:
        doc = self._col().document(record_id).get()
        if not doc.exists:
            logger.warning(f"FollowUp lookup failed: id={record_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Follow up not found."
            )
        record = _doc_to_response(doc.id, doc.to_dict())
        ensure_record_class_access(record.class_name, self.current_user)
        logger.debug(f"FollowUp fetched id={record_id}")
        return record

    def list(
        self,
        class_name=None,
        teacher_id: str | None = None,
        boy_id: str | None = None,
        action_date: date | None = None,
    ) -> list[FollowUpResponse]:
        query = self._col()
        if self.current_user.role == RoleEnum.ADMIN:
            if class_name:
                query = where_eq(query, "class_name", enum_value(class_name))
        else:
            query = where_eq(query, "class_name", enum_value(self.current_user.class_name))
        if teacher_id:
            query = where_eq(query, "teacher_id", teacher_id)
        if boy_id:
            query = where_eq(query, "boy_id", boy_id)
        if action_date:
            query = where_eq(query, "action_date", date_to_str(action_date))
        result = [_doc_to_response(d.id, d.to_dict()) for d in query.stream()]
        logger.debug(f"Listed follow-ups count={len(result)} class={class_name!r}")
        return result

    def update(self, record_id: str, data: FollowUpUpdate) -> FollowUpResponse:
        rec = self.get(record_id)
        updates = data.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] is not None:
            updates["status"] = enum_value(updates["status"])
        if "action_date" in updates and updates["action_date"] is not None:
            updates["action_date"] = date_to_str(updates["action_date"])
        if "class_name" in updates and updates["class_name"] is not None:
            updates["class_name"] = enum_value(updates["class_name"])
        if updates:
            self._col().document(record_id).update(updates)
        logger.info(f"FollowUp updated id={record_id} fields={sorted(updates)} by {self.current_user.mail}")
        if updates.get("note"):
            append_boy_note(self.db, rec.boy_id, updates["note"],
                            tag=f"{rec.action_date or ''} - افتقاد".strip())
        return self.get(record_id)

    def delete(self, record_id: str) -> None:
        self.get(record_id)
        self._col().document(record_id).delete()
        logger.info(f"FollowUp deleted id={record_id} by {self.current_user.mail}")
