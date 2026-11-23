"""Spreadsheet plumbing shared by the routes: the two download responses and
the class-label helpers every template needs.

Everything here is about *presentation* - turning rows into a file, or telling
a template which classes this login may fill. Reading the rows stays in the
services.
"""

from typing import Callable

from fastapi import Response
from sqlalchemy.orm import Session

from app.features.user.models.user import User

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


# ================================================================ responses


def xlsx_response(content: bytes, filename: str = "fasly.xlsx"):
    """Send workbook bytes as a download."""
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def csv_response(content: bytes, filename: str = "fasly.csv"):
    """Send CSV bytes as a download."""
    return Response(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================ class labels


def writable_class_names(db: Session, user: User) -> list[str]:
    """Class names this login may *write into*, for a template's dropdown.

    A class amin gets his own class, the super admin gets all of them - a
    template never offers a class the uploader could not fill.
    """
    from app.features.school_class.services import ClassService

    service = ClassService(db, user)
    lookup = service.label_lookup()
    return [name for name in lookup if name]


def class_labels(db: Session, user: User) -> dict[int, str]:
    """``class_id -> name`` for every class the login can read."""
    from app.features.school_class.services import ClassService

    return {row.id: row.name for row in ClassService(db, user).list()}


def label_for(db: Session, user: User) -> Callable[[int | None], str]:
    """A ``class_id -> name`` lookup that never raises.

    The export builders take a callable rather than a dict because a boy whose
    class was deleted, or a row written before the class existed, must still
    print something.
    """
    names = class_labels(db, user)
    return lambda class_id: names.get(class_id, "")