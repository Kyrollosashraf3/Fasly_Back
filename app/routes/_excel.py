"""Shared helpers for the Excel upload / download routes."""

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.data import ClassService
from app.core.EDA.templates import XLSX_MEDIA_TYPE
from app.schemas.user import UserResponse


def xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def class_labels(db: Session, current_user: UserResponse) -> dict[int, str]:
    """``class_id -> display name`` for the classes this login can see."""
    return {row.id: row.name for row in ClassService(db, current_user).list()}


def label_for(db: Session, current_user: UserResponse):
    """A ``class_id -> name`` callable used to fill the ``class_name`` column."""
    labels = class_labels(db, current_user)

    def _label(class_id: int) -> str:
        return labels.get(class_id, str(class_id))

    return _label


def writable_class_names(db: Session, current_user: UserResponse) -> list[str]:
    """Names of the classes this login may import into, ordered by grade.

    ``label_lookup()`` is already limited to writable classes, so its id set
    is the filter. Falls back to the bare grade number when nothing is
    writable yet, so a template is always downloadable.
    """
    service = ClassService(db, current_user)
    writable_ids = set(service.label_lookup().values())
    rows = [row for row in service.list() if row.id in writable_ids]
    if not rows:
        return [str(n) for n in range(1, 7)]
    return [row.name for row in rows]
