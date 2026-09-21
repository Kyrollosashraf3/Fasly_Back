from app.config.settings import settings
from app.core.data.base import PersonCheckService
from app.core.data.common import append_boy_note, parse_date
from app.models.attend import AttendResponse


def _doc_to_response(doc_id: str, data: dict) -> AttendResponse:
    return AttendResponse(
        id=doc_id,
        boy_id=data.get("boy_id", ""),
        boy_name=data.get("boy_name"),
        class_name=data.get("class_name"),
        action_date=parse_date(data.get("action_date")),
        attend=data.get("attend"),
        note=data.get("note"),
        recorded_by=data.get("recorded_by"),
        recorded_by_name=data.get("recorded_by_name"),
    )


class AttendanceService(PersonCheckService):
    """Friday attendance: one document per (boy, date), upserted.

    Admin: any class. Amin: only own class (class_name auto-stamped from the boy).
    """

    COLLECTION = settings.COLLECTION_ATTEND
    PERSON_COLLECTION = settings.COLLECTION_BOY
    PERSON_KIND = "Boy"
    ID_FIELD = "boy_id"
    NAME_FIELD = "boy_name"
    PERSON_NOT_FOUND = "Boy id={id} not found."
    RECORD_NOT_FOUND = "Attendance record not found."

    @staticmethod
    def to_response(doc_id: str, data: dict) -> AttendResponse:
        return _doc_to_response(doc_id, data)

    def after_upsert(self, person_id: str, payload: dict) -> None:
        append_boy_note(self.db, person_id, payload.get("note"),
                        tag=f"{payload.get('action_date')} - حضور")
