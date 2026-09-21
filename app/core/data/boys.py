from datetime import datetime, timezone

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.data.base import ClassScopedService
from app.core.data.common import (
    bulk_create,
    date_to_str,
    ensure_record_class_access,
    ensure_unique_field,
    enum_value,
    get_doc_or_404,
    parse_date,
    where_eq,
)
from app.models.boy import BoyCreate, BoyResponse, BoyUpdate

logger = get_logger(__name__)

COLLECTION = settings.COLLECTION_BOY


def _doc_to_response(doc_id: str, data: dict) -> BoyResponse:
    kwargs: dict = {
        "id": doc_id,
        "boy_name": data.get("boy_name", ""),
        "gender": data.get("gender"),
        "birth_date": parse_date(data.get("birth_date")),
        "age": data.get("age"),
        "phone": data.get("phone"),
        "phone_2": data.get("phone_2"),
        "address": data.get("address"),
        "location": data.get("location"),
        "class_name": data.get("class_name"),
        "note": data.get("note"),
        "issue_flag": data.get("issue_flag", False),
    }
    if data.get("created_at"):
        kwargs["created_at"] = data["created_at"]
    if data.get("updated_at"):
        kwargs["updated_at"] = data["updated_at"]
    return BoyResponse(**kwargs)


class BoyService(ClassScopedService):
    """Master data for Sunday school boys.

    Admin: any class. Amin: only own class (class_name auto-stamped).
    """

    def _col(self):
        return self.db.collection(COLLECTION)

    def create(self, data: BoyCreate) -> BoyResponse:
        class_name = self.resolve_class(data.class_name)
        boy_name = data.boy_name.strip()
        ensure_unique_field(self.db, COLLECTION, "boy_name", boy_name, label="Boy")
        now = datetime.now(timezone.utc)
        _, doc_ref = self._col().add(
            {
                "boy_name": boy_name,
                "gender": enum_value(data.gender),
                "birth_date": date_to_str(data.birth_date),
                "age": data.age,
                "phone": data.phone,
                "phone_2": data.phone_2,
                "address": data.address,
                "location": data.location,
                "class_name": enum_value(class_name),
                "note": data.note,
                "issue_flag": data.issue_flag,
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info(f"Boy created id={doc_ref.id} name={data.boy_name} class={class_name}")
        return self.get(doc_ref.id)


    def add_list(self, items: list[BoyCreate]) -> dict:
        """Bulk insert (e.g. from an Excel sheet).

        Inserts row by row via create() so class scoping + duplicate-name
        checks still apply. Bad rows don't stop the rest — they are
        collected in "failed" with their reason.
        Returns {"created": [BoyResponse...], "failed": [{boy_name, error}]}.
        """
        return bulk_create(self.create, items, label="boys", name_attr="boy_name")

    def get(self, boy_id: str) -> BoyResponse:
        doc = get_doc_or_404(self._col(), boy_id, "Boy")
        boy = _doc_to_response(doc.id, doc.to_dict())
        ensure_record_class_access(boy.class_name, self.current_user)
        logger.debug(f"Boy fetched id={boy_id} name={boy.boy_name}")
        return boy

    def list(self, class_name=None, issue_flag: bool | None = None) -> list[BoyResponse]:
        from app.models.enums import RoleEnum

        query = self._col()
        if self.current_user.role == RoleEnum.ADMIN:
            if class_name:
                query = where_eq(query, "class_name", enum_value(class_name))
        else:
            query = where_eq(query, "class_name", enum_value(self.current_user.class_name))
        if issue_flag is not None:
            query = where_eq(query, "issue_flag", issue_flag)
        result = [_doc_to_response(d.id, d.to_dict()) for d in query.stream()]
        logger.debug(f"Listed boys count={len(result)} class={class_name!r}")
        return result

    def update(self, boy_id: str, data: BoyUpdate) -> BoyResponse:
        boy = self.get(boy_id)
        updates = data.model_dump(exclude_unset=True)
        if "boy_name" in updates and updates["boy_name"] is not None:
            updates["boy_name"] = updates["boy_name"].strip()
            ensure_unique_field(self.db, COLLECTION, "boy_name", updates["boy_name"], exclude_id=boy_id, label="Boy")
        if "class_name" in updates and updates["class_name"] is not None:
            self.resolve_class(updates["class_name"])
            updates["class_name"] = enum_value(updates["class_name"])
        if "gender" in updates and updates["gender"] is not None:
            updates["gender"] = enum_value(updates["gender"])
        if "birth_date" in updates:
            updates["birth_date"] = date_to_str(updates["birth_date"])
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            self._col().document(boy_id).update(updates)
        logger.info(f"Boy updated id={boy_id} fields={sorted(updates)} by {self.current_user.mail}")
        return self.get(boy_id)

    def delete(self, boy_id: str) -> None:
        self.get(boy_id)
        self._col().document(boy_id).delete()
        logger.info(f"Boy deleted id={boy_id} by {self.current_user.mail}")
