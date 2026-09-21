from app.config.settings import settings
from app.core.data.base import PersonCheckService
from app.core.data.common import parse_date
from app.models.teacher_check import TeacherCheckResponse


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


class TeacherCheckService(PersonCheckService):
    """Weekly check on servants: one document per (teacher, friday), upserted.

    Admin: any class. Amin: only own class.
    """

    COLLECTION = settings.COLLECTION_TEACHER_CHECK
    PERSON_COLLECTION = settings.COLLECTION_TEACHER
    PERSON_KIND = "Teacher"
    ID_FIELD = "teacher_id"
    NAME_FIELD = "teacher_name"
    FLAG_FIELDS = ["prepare_flag", "liturgy_flag", "follow_flag"]
    PERSON_NOT_FOUND = "Teacher id={id} not found."
    RECORD_NOT_FOUND = "Teacher check not found."

    @staticmethod
    def to_response(doc_id: str, data: dict) -> TeacherCheckResponse:
        return _doc_to_response(doc_id, data)
