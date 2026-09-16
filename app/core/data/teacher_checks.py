from datetime import date

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import (
    date_to_str,
    ensure_record_class_access,
    enum_value,
    parse_date,
    where_eq,
)
from app.models.enums import RoleEnum
from app.models.teacher_check import (
    TeacherCheckBulkCreate,
    TeacherCheckCreate,
    TeacherCheckResponse,
    TeacherCheckUpdate,
)

logger = get_logger(__name__)

COLLECTION = settings.COLLECTION_TEACHER_CHECK
TEACHERS_COLLECTION = settings.COLLECTION_TEACHER


def _doc_to_response(doc_id: str, data: dict) -> TeacherCheckResponse:
    return TeacherCheckResponse(
        id=doc_id,
        teacher_id=data.get("teacher_id", ""),
        teacher_name=data.get("teacher_name"),
        class_name=data.get("class_name"),
        action_date=parse_date(data.get("action_date")),
        attend=data.get("attend"),
        prepare_flag=data.get("prepare_flag", False),
        liturgy_flag=data.get("liturgy_flag", False),
        follow_flag=data.get("follow_flag", False),
        note=data.get("note"),
        recorded_by=data.get("recorded_by"),
        recorded_by_name=data.get("recorded_by_name"),
    )


class TeacherCheckService(ClassScopedService):
    """Weekly check on servants: one document per (teacher, friday), upserted.

    Admin: any class. Amin: only own class.
    """

    def _col(self):
        return self.db.collection(COLLECTION)

    def _resolve_teacher(self, teacher_id: str) -> dict:
        """Fetch the servant and enforce class access. Returns raw doc data."""
        doc = self.db.collection(TEACHERS_COLLECTION).document(teacher_id).get()
        if not doc.exists:
            logger.warning(f"TeacherCheck rejected: teacher id={teacher_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher id={teacher_id} not found.",
            )
        data = doc.to_dict()
        ensure_record_class_access(data.get("class_name"), self.current_user)
        return data

    def _upsert(
        self,
        teacher_id: str,
        teacher_name: str | None,
        class_name: str,
        action_date: date,
        attend,
        prepare_flag: bool,
        liturgy_flag: bool,
        follow_flag: bool,
        note: str | None,
    ) -> TeacherCheckResponse:
        """Insert or overwrite the (teacher, date) check — resubmits never duplicate."""
        date_str = date_to_str(action_date)
        existing = list(
            where_eq(where_eq(self._col(), "teacher_id", teacher_id), "action_date", date_str)
            .limit(1)
            .stream()
        )
        payload = {
            "teacher_id": teacher_id,
            "teacher_name": teacher_name,
            "class_name": class_name,
            "action_date": date_str,
            "attend": enum_value(attend),
            "prepare_flag": prepare_flag,
            "liturgy_flag": liturgy_flag,
            "follow_flag": follow_flag,
            "note": note,
            "recorded_by": self.user_id,
            "recorded_by_name": self.current_user.user_name,
        }
        if existing:
            doc_id = existing[0].id
            self._col().document(doc_id).update(payload)
            logger.info(f"TeacherCheck upserted (updated) teacher={teacher_id} date={date_str}")
            return _doc_to_response(doc_id, payload)
        _, doc_ref = self._col().add(payload)
        logger.info(f"TeacherCheck upserted (created) teacher={teacher_id} date={date_str}")
        return _doc_to_response(doc_ref.id, payload)

    def create(self, data: TeacherCheckCreate) -> TeacherCheckResponse:
        teacher = self._resolve_teacher(data.teacher_id)
        return self._upsert(
            teacher_id=data.teacher_id,
            teacher_name=teacher.get("teacher_name"),
            class_name=teacher.get("class_name"),
            action_date=data.action_date or date.today(),
            attend=data.attend,
            prepare_flag=data.prepare_flag,
            liturgy_flag=data.liturgy_flag,
            follow_flag=data.follow_flag,
            note=data.note,
        )

    def create_bulk(self, data: TeacherCheckBulkCreate) -> list[TeacherCheckResponse]:
        """Friday flow: all servants' checks in one request."""
        self.resolve_class(data.class_name)
        action_date = data.action_date or date.today()
        result = []
        for item in data.items:
            teacher = self._resolve_teacher(item.teacher_id)
            result.append(
                self._upsert(
                    teacher_id=item.teacher_id,
                    teacher_name=teacher.get("teacher_name"),
                    class_name=teacher.get("class_name"),
                    action_date=action_date,
                    attend=item.attend,
                    prepare_flag=item.prepare_flag,
                    liturgy_flag=item.liturgy_flag,
                    follow_flag=item.follow_flag,
                    note=item.note,
                )
            )
        logger.info(
            f"TeacherCheck bulk saved class={data.class_name} date={action_date} "
            f"count={len(result)} by {self.current_user.mail}"
        )
        return result

    def get(self, record_id: str) -> TeacherCheckResponse:
        doc = self._col().document(record_id).get()
        if not doc.exists:
            logger.warning(f"TeacherCheck lookup failed: id={record_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Teacher check not found."
            )
        record = _doc_to_response(doc.id, doc.to_dict())
        ensure_record_class_access(record.class_name, self.current_user)
        logger.debug(f"TeacherCheck fetched id={record_id}")
        return record

    def list(self, class_name=None, action_date: date | None = None) -> list[TeacherCheckResponse]:
        query = self._col()
        if self.current_user.role == RoleEnum.ADMIN:
            if class_name:
                query = where_eq(query, "class_name", enum_value(class_name))
        else:
            query = where_eq(query, "class_name", enum_value(self.current_user.class_name))
        if action_date:
            query = where_eq(query, "action_date", date_to_str(action_date))
        result = [_doc_to_response(d.id, d.to_dict()) for d in query.stream()]
        logger.debug(f"Listed teacher checks count={len(result)} class={class_name!r} date={action_date!r}")
        return result

    def update(self, record_id: str, data: TeacherCheckUpdate) -> TeacherCheckResponse:
        self.get(record_id)
        updates = data.model_dump(exclude_unset=True)
        if "attend" in updates and updates["attend"] is not None:
            updates["attend"] = enum_value(updates["attend"])
        if "action_date" in updates and updates["action_date"] is not None:
            updates["action_date"] = date_to_str(updates["action_date"])
        if "class_name" in updates and updates["class_name"] is not None:
            updates["class_name"] = enum_value(updates["class_name"])
        if updates:
            self._col().document(record_id).update(updates)
        logger.info(f"TeacherCheck updated id={record_id} fields={sorted(updates)} by {self.current_user.mail}")
        return self.get(record_id)

    def delete(self, record_id: str) -> None:
        self.get(record_id)
        self._col().document(record_id).delete()
        logger.info(f"TeacherCheck deleted id={record_id} by {self.current_user.mail}")
