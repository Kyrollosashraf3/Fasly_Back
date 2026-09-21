from datetime import date

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.core.data.common import (
    date_to_str,
    ensure_admin,
    ensure_class_access,
    ensure_record_class_access,
    enum_value,
    where_eq,
)
from app.models.enums import RoleEnum
from app.models.user import UserResponse

logger = get_logger(__name__)


class BaseService:
    """Base service that binds the Firestore client and the acting user.

    `user_id` is always available from the authenticated user
    (resolved from the JWT by `get_current_user`).
    """

    def __init__(self, db, current_user: UserResponse):
        self.db = db
        self.current_user = current_user
        self.user_id = current_user.id


class AdminService(BaseService):
    """Base service restricted to admins.

    Used for user accounts management.
    """

    def __init__(self, db, current_user: UserResponse):
        super().__init__(db, current_user)
        ensure_admin(current_user)


class ClassScopedService(BaseService):
    """Base service for records tied to a class (boys, teachers, ...).

    Admin bypasses scoping; amin is locked to his own class.
    """

    def resolve_class(self, class_name):
        """Return the effective class: admin uses the requested one, amin his own."""
        ensure_class_access(class_name, self.current_user)
        if self.current_user.role == RoleEnum.ADMIN:
            return class_name
        return self.current_user.class_name


class PersonCheckService(ClassScopedService):
    """Generic Friday check: one document per (person, date), upserted.

    Covers attendance (per boy) and teacher checks (per servant) — same flow,
    different person. Subclasses configure only::

        COLLECTION         checks collection (attends / teacher_checks)
        PERSON_COLLECTION  master collection (boys / teachers)
        PERSON_KIND        "Boy" / "Teacher" (logs + 404 messages)
        ID_FIELD           "boy_id" / "teacher_id"
        NAME_FIELD         "boy_name" / "teacher_name"
        FLAG_FIELDS        extra boolean columns, e.g. ["prepare_flag", ...]
        to_response(doc_id, data)  response builder (as @staticmethod)
    """

    COLLECTION: str = ""
    PERSON_COLLECTION: str = ""
    PERSON_KIND: str = "Record"
    ID_FIELD: str = ""
    NAME_FIELD: str = ""
    FLAG_FIELDS: list[str] = []
    PERSON_NOT_FOUND: str = "{kind} id={id} not found."
    RECORD_NOT_FOUND: str = "{kind} check not found."

    @staticmethod
    def to_response(doc_id: str, data: dict):
        raise NotImplementedError

    def _col(self):
        return self.db.collection(self.COLLECTION)

    def _not_found(self, person_id: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=self.PERSON_NOT_FOUND.format(kind=self.PERSON_KIND, id=person_id),
        )

    def _resolve_person(self, person_id: str) -> dict:
        """Fetch the master record and enforce class access."""
        doc = self.db.collection(self.PERSON_COLLECTION).document(person_id).get()
        if not doc.exists:
            raise self._not_found(person_id)
        data = doc.to_dict()
        ensure_record_class_access(data.get("class_name"), self.current_user)
        return data

    def _find_existing(self, person_id: str, date_str: str) -> str | None:
        """Id of the (person, date) document if it already exists."""
        existing = list(
            where_eq(where_eq(self._col(), self.ID_FIELD, person_id),
                     "action_date", date_str).limit(1).stream()
        )
        return existing[0].id if existing else None

    def after_upsert(self, person_id: str, payload: dict) -> None:
        """Hook for side effects (e.g. accumulating notes). Default: none."""

    def _upsert(self, person_id: str, person_name: str | None, class_name: str,
                action_date: date, attend, note: str | None = None,
                **flags) -> object:
        """Insert or overwrite the (person, date) record — resubmits never duplicate."""
        date_str = date_to_str(action_date)
        payload = {
            self.ID_FIELD: person_id,
            self.NAME_FIELD: person_name,
            "class_name": class_name,
            "action_date": date_str,
            "attend": enum_value(attend),
            "note": note,
            "recorded_by": self.user_id,
            "recorded_by_name": self.current_user.user_name,
        }
        for field in self.FLAG_FIELDS:
            payload[field] = bool(flags.get(field, False))
        doc_id = self._find_existing(person_id, date_str)
        if doc_id:
            self._col().document(doc_id).update(payload)
        else:
            _, doc_ref = self._col().add(payload)
            doc_id = doc_ref.id
        self.after_upsert(person_id, payload)
        return self.to_response(doc_id, payload)

    def _flags_of(self, item) -> dict:
        return {f: bool(getattr(item, f, False)) for f in self.FLAG_FIELDS}

    def create(self, data) -> object:
        person_id = getattr(data, self.ID_FIELD)
        person = self._resolve_person(person_id)
        return self._upsert(
            person_id=person_id,
            person_name=person.get(self.NAME_FIELD),
            class_name=person.get("class_name"),
            action_date=getattr(data, "action_date", None) or date.today(),
            attend=data.attend,
            note=data.note,
            **self._flags_of(data),
        )

    def create_bulk(self, data) -> list:
        """Friday flow: whole class in one request (duplicate rows rejected)."""
        self.resolve_class(data.class_name)
        action_date = data.action_date or date.today()
        seen: set[str] = set()
        dupes: set[str] = set()
        for item in data.items:
            pid = getattr(item, self.ID_FIELD)
            if pid in seen:
                dupes.add(pid)
            seen.add(pid)
        if dupes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate rows in the same save — submit each person only once.",
            )
        result = []
        for item in data.items:
            person_id = getattr(item, self.ID_FIELD)
            person = self._resolve_person(person_id)
            result.append(self._upsert(
                person_id=person_id,
                person_name=person.get(self.NAME_FIELD),
                class_name=person.get("class_name"),
                action_date=action_date,
                attend=item.attend,
                note=item.note,
                **self._flags_of(item),
            ))
        logger.info(
            f"{self.PERSON_KIND} bulk saved class={data.class_name} "
            f"date={action_date} count={len(result)}"
        )
        return result

    def get(self, record_id: str) -> object:
        doc = self._col().document(record_id).get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=self.RECORD_NOT_FOUND.format(kind=self.PERSON_KIND),
            )
        record = self.to_response(doc.id, doc.to_dict())
        ensure_record_class_access(record.class_name, self.current_user)
        return record

    def list(self, class_name=None, action_date: date | None = None) -> list:
        query = self._col()
        if self.current_user.role == RoleEnum.ADMIN:
            if class_name:
                query = where_eq(query, "class_name", enum_value(class_name))
        else:
            query = where_eq(query, "class_name", enum_value(self.current_user.class_name))
        if action_date:
            query = where_eq(query, "action_date", date_to_str(action_date))
        return [self.to_response(d.id, d.to_dict()) for d in query.stream()]

    def update(self, record_id: str, data) -> object:
        self.get(record_id)
        updates = data.model_dump(exclude_unset=True)
        if updates.get("attend") is not None:
            updates["attend"] = enum_value(updates["attend"])
        if updates.get("action_date") is not None:
            updates["action_date"] = date_to_str(updates["action_date"])
        if updates.get("class_name") is not None:
            updates["class_name"] = enum_value(updates["class_name"])
        if updates:
            self._col().document(record_id).update(updates)
        return self.get(record_id)

    def delete(self, record_id: str) -> None:
        self.get(record_id)
        self._col().document(record_id).delete()
