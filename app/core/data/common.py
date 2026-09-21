from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from google.cloud.firestore_v1.base_query import FieldFilter

from app.config.logger import get_logger
from app.models.enums import ClassEnum, RoleEnum
from app.models.user import UserResponse

logger = get_logger(__name__)


def append_boy_note(db, boy_id: str, note: str | None, tag: str | None = None) -> None:
    """Accumulate a follow-up/attendance note into the boy's master note column.

    Appends "[tag] text" to boys.note so the master record grows with every
    new comment. Skips empty notes and exact duplicates (re-saving the same
    date/note won't duplicate the text).
    """
    text = (note or "").strip()
    if not text or not boy_id:
        return
    from app.config.settings import settings  # local import: avoids circulars

    ref = db.collection(settings.COLLECTION_BOY).document(boy_id)
    doc = ref.get()
    if not doc.exists:
        return
    current = (doc.to_dict() or {}).get("note") or ""
    if text in current:
        return  # already recorded before
    entry = f"[{tag}] {text}" if tag else text
    ref.update({"note": f"{current}\n{entry}".strip() if current else entry,
                "updated_at": datetime.now(timezone.utc)})
    logger.info(f"Boy note appended id={boy_id} tag={tag}")


def where_eq(target, field: str, value):
    """Equality filter using the `filter=` keyword (positional args are deprecated)."""
    return target.where(filter=FieldFilter(field, "==", value))


def ensure_admin(user: UserResponse) -> None:
    """Raise 403 unless the acting user holds the Admin role."""
    if user.role != RoleEnum.ADMIN:
        logger.warning(
            f"Admin-only operation blocked: user={user.mail} role={user.role}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this operation.",
        )


def ensure_class_access(target_class: ClassEnum | None, user: UserResponse) -> None:
    """Generic class boundary: Admin bypasses, amin must match own class.

    Compares by value because Firestore returns raw strings ("5")
    while the user carries ClassEnum members.
    """
    if user.role == RoleEnum.ADMIN:
        return
    if enum_value(target_class) != enum_value(user.class_name):
        logger.warning(
            f"Class access denied: user={user.mail} class={user.class_name} "
            f"target_class={target_class}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to this resource (different class, your class={user.class_name}).",
        )


def ensure_record_class_access(record_class: ClassEnum | None, user: UserResponse) -> None:
    """Enforce class boundary for a single record (wrapper over ensure_class_access)."""
    ensure_class_access(record_class, user)


def date_to_str(value: date | None) -> str | None:
    """Store dates as ISO strings — Firestore has no native date type."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def parse_date(value) -> date | None:
    """Read back an ISO string (or datetime) as a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def enum_value(value) -> str | None:
    """Store enums by their value."""
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def get_doc_or_404(collection_ref, doc_id: str, label: str = "Record"):
    """Fetch a document or raise 404 — shared by all service get() methods."""
    doc = collection_ref.document(doc_id).get()
    if not doc.exists:
        logger.warning(f"{label} lookup failed: id={doc_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found."
        )
    return doc


def bulk_create(create_fn, items: list, *, label: str, name_attr: str) -> dict:
    """Insert items one by one via create_fn, collecting per-row failures.

    Row-level errors (duplicates, class violations) don't stop the rest.
    Returns {"created": [...], "failed": [{<name_attr>, "error"}]}.
    """
    created: list = []
    failed: list[dict] = []
    for item in items:
        try:
            created.append(create_fn(item))
        except HTTPException as exc:
            failed.append({name_attr: getattr(item, name_attr), "error": exc.detail})
            logger.warning(f"Bulk {label} skipped: {exc.detail}")
    logger.info(f"Bulk {label} done: created={len(created)} failed={len(failed)}")
    return {"created": created, "failed": failed}


def ensure_unique_field(
    db,
    collection: str,
    field: str,
    value: str | None,
    exclude_id: str | None = None,
    label: str = "Record",
) -> None:
    """Raise 400 if another document already uses this field value.

    Used for duplicate-name checks on create/update (users, teachers, boys).
    `exclude_id` skips the document being updated so edits keep their own name.
    """
    if value is None or not str(value).strip():
        return
    cleaned = str(value).strip()
    docs = list(where_eq(db.collection(collection), field, cleaned).stream())
    if exclude_id:
        docs = [d for d in docs if d.id != exclude_id]
    if docs:
        logger.warning(
            f"Duplicate {field} rejected: '{cleaned}' in collection '{collection}'"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} with this {field} already exists: '{cleaned}'.",
        )
