"""Shared helpers used by every service in ``app.core.data``.

Authorization lives in ``app.core.data.base.Scope`` - nothing in here makes a
permission decision.
"""

import re
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.logger import get_logger
from app.models.boy import Boy

logger = get_logger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def touch(record: Any) -> None:
    """Stamp ``updated_at`` on a record that has the column."""
    if hasattr(record, "updated_at"):
        record.updated_at = now_utc()


def get_or_404(db: Session, model: Any, record_id: int, label: str = "Record") -> Any:
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} {record_id} not found.",
        )
    return record


def commit(db: Session, context: str) -> None:
    """Commit, translating driver errors into HTTP statuses.

    ``IntegrityError`` -> 409 (duplicate / FK), anything else -> 500. The
    session is always rolled back first so the connection is reusable.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity error while %s: %s", context, exc.orig)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That record conflicts with an existing one.",
        ) from exc
    except Exception:
        db.rollback()
        logger.exception("Database error while %s", context)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
        ) from None


def ensure_unique_field(
    db: Session,
    model: Any,
    field: str,
    value: str | None,
    exclude_id: int | None = None,
    label: str = "Record",
) -> None:
    """409 when another row already carries ``value`` in ``field``."""
    if value is None:
        return
    query = db.query(model).filter(getattr(model, field) == value)
    if exclude_id is not None:
        query = query.filter(model.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{label}: '{value}' already exists.",
        )


def bulk_create(
    create_fn: Callable[[Any], Any],
    items: Iterable[Any],
    *,
    label: str,
    name_attr: str,
) -> dict:
    """Create one by one, collecting failures instead of aborting the batch.

    ``create_fn`` commits each row on its own, so a rejected item never
    poisons the ones before it.

    Authorization failures (401/403) are re-raised: the whole request is
    forbidden, it is not a per-row data problem.
    """
    created: list[Any] = []
    failed: list[dict] = []
    for item in items:
        try:
            created.append(create_fn(item))
        except HTTPException as exc:
            if exc.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise
            failed.append(
                {
                    name_attr: getattr(item, name_attr, None),
                    "error": exc.detail,
                }
            )
    logger.info("%s bulk done: created=%d failed=%d", label, len(created), len(failed))
    return {"created": created, "failed": failed}


def append_boy_note(
    db: Session,
    boy_id: int,
    note: str | None,
    tag: str | None = None,
) -> None:
    """Append a dated line to ``boys.note`` (used to keep a boy's log)."""
    if not note:
        return
    boy = db.get(Boy, boy_id)
    if boy is None:
        return
    stamp = date.today().isoformat()
    line = f"[{stamp}{' ' + tag if tag else ''}] {note.strip()}"
    boy.note = f"{boy.note}\n{line}" if boy.note else line
    boy.updated_at = now_utc()


# --- date / enum coercion ----------------------------------------------------


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def to_date(value: Any) -> date | None:
    """Best-effort coercion of ``str``/``datetime``/``date`` to ``date``."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        match = _DATE_RE.match(value.strip())
        if match:
            try:
                return date(int(match[1]), int(match[2]), int(match[3]))
            except ValueError:
                return None
    return None


def enum_value(value: Any) -> Any:
    """Unwrap an ``Enum`` member to its raw value; pass anything else through."""
    return getattr(value, "value", value)


def is_past_friday(value: Any) -> bool:
    """True when ``value`` is a Friday that has already happened."""
    day = to_date(value)
    return day is not None and day.weekday() == 4 and day <= date.today()
