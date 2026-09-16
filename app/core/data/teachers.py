from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import ensure_record_class_access, ensure_unique_field, enum_value, where_eq
from app.models.enums import RoleEnum
from app.models.teacher import TeacherCreate, TeacherResponse, TeacherUpdate

logger = get_logger(__name__)

COLLECTION = settings.COLLECTION_TEACHER


def _doc_to_response(doc_id: str, data: dict) -> TeacherResponse:
    kwargs: dict = {
        "id": doc_id,
        "teacher_name": data.get("teacher_name", ""),
        "phone": data.get("phone"),
        "class_name": data.get("class_name"),
        "duty": data.get("duty"),
        "note": data.get("note"),
    }
    if data.get("created_at"):
        kwargs["created_at"] = data["created_at"]
    if data.get("updated_at"):
        kwargs["updated_at"] = data["updated_at"]
    return TeacherResponse(**kwargs)


class TeacherService(ClassScopedService):
    """Servants data (entered/edited by أمين الفصل).

    Admin: any class. Amin: only own class (class_name auto-stamped).
    """

    def _col(self):
        return self.db.collection(COLLECTION)

    def create(self, data: TeacherCreate) -> TeacherResponse:
        class_name = self.resolve_class(data.class_name)
        teacher_name = data.teacher_name.strip()
        ensure_unique_field(self.db, COLLECTION, "teacher_name", teacher_name, label="Teacher")
        now = datetime.now(timezone.utc)
        _, doc_ref = self._col().add(
            {
                "teacher_name": teacher_name,
                "phone": data.phone,
                "class_name": enum_value(class_name),
                "duty": data.duty,
                "note": data.note,
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info(f"Teacher created id={doc_ref.id} name={data.teacher_name} class={class_name}")
        return self.get(doc_ref.id)

    def get(self, teacher_id: str) -> TeacherResponse:
        doc = self._col().document(teacher_id).get()
        if not doc.exists:
            logger.warning(f"Teacher lookup failed: id={teacher_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found."
            )
        teacher = _doc_to_response(doc.id, doc.to_dict())
        ensure_record_class_access(teacher.class_name, self.current_user)
        logger.debug(f"Teacher fetched id={teacher_id} name={teacher.teacher_name}")
        return teacher

    def list(self, class_name=None) -> list[TeacherResponse]:
        query = self._col()
        if self.current_user.role == RoleEnum.ADMIN:
            if class_name:
                query = where_eq(query, "class_name", enum_value(class_name))
        else:
            query = where_eq(query, "class_name", enum_value(self.current_user.class_name))
        result = [_doc_to_response(d.id, d.to_dict()) for d in query.stream()]
        logger.debug(f"Listed teachers count={len(result)} class={class_name!r}")
        return result

    def update(self, teacher_id: str, data: TeacherUpdate) -> TeacherResponse:
        self.get(teacher_id)
        updates = data.model_dump(exclude_unset=True)
        if "teacher_name" in updates and updates["teacher_name"] is not None:
            updates["teacher_name"] = updates["teacher_name"].strip()
            ensure_unique_field(self.db, COLLECTION, "teacher_name", updates["teacher_name"], exclude_id=teacher_id, label="Teacher")
        if "class_name" in updates and updates["class_name"] is not None:
            self.resolve_class(updates["class_name"])
            updates["class_name"] = enum_value(updates["class_name"])
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            self._col().document(teacher_id).update(updates)
        logger.info(f"Teacher updated id={teacher_id} fields={sorted(updates)} by {self.current_user.mail}")
        return self.get(teacher_id)

    def delete(self, teacher_id: str) -> None:
        self.get(teacher_id)
        self._col().document(teacher_id).delete()
        logger.info(f"Teacher deleted id={teacher_id} by {self.current_user.mail}")
