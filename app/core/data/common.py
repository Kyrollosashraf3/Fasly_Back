"""Every permission question and every shared helper the app asks.

Authorization lives here and only here: a route never decides anything, and a
service just calls the check it needs at the top of a method.

The whole model in one sentence
-------------------------------
**A login is attached to exactly one class.** ``users`` stores no class - a
servant carries it on ``teachers`` and a boy on ``boys`` - so "may this login
see that row?" is almost always "is that row's class mine?".

============  ==============  =============  ==================
operation     super_admin     admin          teacher
============  ==============  =============  ==================
classes       all             own class      read the list
boys          all             own class      own class, **write**
servants      all             own class      himself only
attendance    all             own class      own class
follow_ups    all             own class      his own rows
teacher_checks all            own class      his own rows
groups        all             own class      his own group
accounts      all             own class      himself only
============  ==============  =============  ==================

A ``user`` (boy) login is the exception: it only ever sees its own rows.

A row outside a login's scope reads as **404** because the read queries are
filtered before they reach the database - a scoped-out caller never learns
the row exists.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Iterable

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from app.config.logger import get_logger
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck
from app.models.user import User

logger = get_logger(__name__)

#: Roles allowed to write the directories (classes, servants, accounts, groups)
#: and to run the servant review.
MANAGERS = (RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN)

#: Every login except a boy's - i.e. everyone attached to a class.
STAFF = (RoleEnum.TEACHER, RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN)

#: Roles allowed to review servants (a boy has no business on that page).
REVIEWERS = (RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.TEACHER)


# ============================================================== who am I


def is_manager(user: User) -> bool:
    """Class amin or church-wide amin."""
    return user.role in MANAGERS


def my_class_id(db: Session, user: User) -> int | None:
    """The one class this login belongs to; ``None`` means unrestricted.

    Only the super admin is unrestricted. The value is resolved through the
    owner link (``users.teacher_id`` or ``users.boy_id``) and cached by the
    SQLAlchemy identity map, so asking twice costs nothing.
    """
    if user.role == RoleEnum.SUPER_ADMIN:
        return None
    if user.teacher_id is not None:
        teacher = db.get(Teacher, user.teacher_id)
        return teacher.class_id if teacher is not None else None
    if user.boy_id is not None:
        boy = db.get(Boy, user.boy_id)
        return boy.class_id if boy is not None else None
    return None


# ================================================================= guards


def deny(detail: str, code: int = status.HTTP_403_FORBIDDEN) -> None:
    raise HTTPException(status_code=code, detail=detail)


def ensure_roles(user: User, *roles: RoleEnum) -> None:
    """403 unless the login holds one of ``roles``."""
    if user.role not in roles:
        deny("You do not have permission to perform this operation.")


def ensure_manager(user: User) -> None:
    """403 unless the login is a class amin or the church-wide amin."""
    if user.role not in MANAGERS:
        deny("Only the class amin or the super admin can do that.")


def ensure_staff(user: User) -> None:
    """403 for a boy's login - servant-only pages start here."""
    if user.role not in STAFF:
        deny("You do not have permission to view servants.")


def ensure_my_class(db: Session, user: User, class_id: int | None) -> None:
    """403 unless ``class_id`` is the login's own class (super admin passes)."""
    mine = my_class_id(db, user)
    if mine is None:  # super admin
        return
    if class_id is None or class_id != mine:
        deny("You do not have access to that class.")


def ensure_boy_access(db: Session, user: User, boy: Boy) -> None:
    """403 unless the login may read this boy (a boy: only himself)."""
    if user.role == RoleEnum.SUPER_ADMIN:
        return
    if user.role == RoleEnum.USER:
        if boy.id != user.boy_id:
            deny("You can only view your own record.")
        return
    ensure_my_class(db, user, boy.class_id)


def ensure_teacher_access(db: Session, user: User, teacher: Teacher) -> None:
    """403 unless the login may read this servant (a servant: only himself)."""
    if user.role == RoleEnum.SUPER_ADMIN:
        return
    if user.role == RoleEnum.TEACHER:
        if teacher.id != user.teacher_id:
            deny("You can only view your own record.")
        return
    if user.role == RoleEnum.USER:
        deny("You do not have permission to view servants.")
    ensure_my_class(db, user, teacher.class_id)


# =========================================================== query scopes
#
# Each one takes a plain Query and returns it filtered, so a read is always
# "build the query, scope it, add the filters the client asked for".


def scope_classes(db: Session, query: Query, model, user: User) -> Query:
    """Keep only rows of the login's own class (super admin keeps everything)."""
    class_id = my_class_id(db, user)
    return query if class_id is None else query.filter(model.class_id == class_id)


def scope_boys(db: Session, query: Query, model, user: User, boy_column) -> Query:
    """Keep only rows attached to a boy this login may see.

    ``boy_column`` is the id column holding the boy (``Boy.id``,
    ``Attend.boy_id``, ``FollowUp.boy_id``). Every one of those tables also
    carries ``class_id``, so the class filter needs no join.
    """
    if user.role == RoleEnum.USER:
        return query.filter(boy_column == user.boy_id)
    return scope_classes(db, query, model, user)


def scope_teachers(db: Session, query: Query, user: User) -> Query:
    """Servants this login may see: a servant only himself, staff his class."""
    ensure_staff(user)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(Teacher.id == user.teacher_id)
    return query.filter(Teacher.class_id == my_class_id(db, user))


def scope_follow_ups(db: Session, query: Query, user: User) -> Query:
    """Follow-up rows this login may see.

    A boy sees the calls made about him, a servant only the ones he wrote,
    an amin every row of his class.
    """
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(FollowUp.teacher_id == user.teacher_id)
    if user.role == RoleEnum.USER:
        return query.filter(FollowUp.boy_id == user.boy_id)
    return query.filter(FollowUp.class_id == my_class_id(db, user))


def scope_checks(db: Session, query: Query, user: User) -> Query:
    """Servant review rows: a servant his own reviews, staff their class."""
    ensure_roles(user, *REVIEWERS)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(TeacherCheck.teacher_id == user.teacher_id)
    return query.filter(TeacherCheck.class_id == my_class_id(db, user))


def scope_users(db: Session, query: Query, user: User) -> Query:
    """Accounts this login may see.

    super admin: every login.  servant / boy: only their own.
    class amin: the accounts of the servants and boys of his class.
    """
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role in (RoleEnum.TEACHER, RoleEnum.USER):
        return query.filter(User.id == user.id)
    class_id = my_class_id(db, user)
    teacher_ids = [
        row[0] for row in db.query(Teacher.id).filter(Teacher.class_id == class_id)
    ]
    boy_ids = [row[0] for row in db.query(Boy.id).filter(Boy.class_id == class_id)]
    return query.filter(
        or_(User.teacher_id.in_(teacher_ids), User.boy_id.in_(boy_ids))
    )


# ================================================================ helpers


def get_or_404(
    db: Session, model: Any, record_id: int, label: str = "Record"
) -> Any:
    """Load a row by id, or 404."""
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} {record_id} not found.",
        )
    return record


def commit(db: Session, context: str) -> None:
    """Commit, translating driver errors into HTTP statuses.

    ``IntegrityError`` -> 409 (duplicate / FK / check constraint), anything
    else -> 500. The session is always rolled back first so the connection
    returns to the pool usable.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Conflict while %s: %s", context, exc.orig)
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


def ensure_unique(
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


def apply_update(
    record,
    data,
    *,
    skip: tuple[str, ...] = (),
    strip: tuple[str, ...] = (),
) -> None:
    """Copy a PATCH payload onto the row - only the fields actually sent.

    ``skip`` protects the row's identity (the person and the date of a
    weekly sheet); ``strip`` names the text fields to trim.
    """
    for field in data.model_fields_set:
        if field in skip:
            continue
        value = getattr(data, field)
        if field in strip and isinstance(value, str):
            value = value.strip()
        setattr(record, field, value)


def bulk_create(
    create_fn: Callable[[Any], Any],
    items: Iterable[Any],
    *,
    label: str,
    name_attr: str,
) -> dict:
    """Create one by one, collecting failures instead of aborting the batch.

    ``create_fn`` commits each row on its own, so a rejected item never
    poisons the ones before it. Authorization failures (401/403) are
    re-raised: the whole request is forbidden, not this row.
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
            failed.append({name_attr: getattr(item, name_attr, None), "error": exc.detail})
    logger.info("%s bulk: created=%d failed=%d", label, len(created), len(failed))
    return {"created": created, "failed": failed}


def normalise_name(value: Any) -> str:
    """Case/whitespace-insensitive form of a person's name.

    Used to match a name typed into a spreadsheet cell against the rows
    already in the database.
    """
    return " ".join(str(value).split()).lower()


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def is_past_friday(value: Any) -> bool:
    """True when ``value`` is a Friday that has already happened.

    The school meets on Friday, so only those days count as attendance.
    """
    if value is None:
        return False
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        match = _DATE_RE.match(value.strip())
        if not match:
            return False
        try:
            value = date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return False
    return value.weekday() == 4 and value <= date.today()