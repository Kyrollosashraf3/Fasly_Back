"""Every permission question and every shared helper the app asks.

Authorization lives here and only here: a route never decides anything, and a
service just calls the check it needs at the top of a method.

The whole model in two sentences
-------------------------------
**A login belongs to one church and to a set of classes inside it.** Every
data row carries ``church_id``; the first question is always "is this row in my
church?" and only then "is its class one of mine?". The platform owner
(``super_admin``) is the only role with no church and no class limit: he sees
every church. The church amin (``abona``) sees every class of *his* church; a
stage amin (``general_admin``) sees only the classes written for him in
``general_admin_classes``; a class amin (``admin``) and a servant (``teacher``)
see their own class. A boy's login (``user``) only ever sees its own rows.

============  ===========  =======  =============  ==========  ========  ==========
operation     super_admin  abona    general_admin  admin       teacher   user
============  ===========  =======  =============  ==========  ========  ==========
churches      all          own      own            own         own       own
classes       all          all own  his own group  own class   read list -
boys          all          all own  his own group  own class   own class own only
servants      all          all own  his own group  own class   himself   -
attendance    all          all own  his own group  own class   own class -
follow_ups    all          all own  his own group  own class   own rows  own only
teacher_checks all         all own  his own group  own class   own rows  -
groups        all          all own  his own group  own class   own group -
accounts      all          all own  his own group  own class   himself   own only
============  ===========  =======  =============  ==========  ========  ==========

A row outside a login's scope reads as **404** because the read queries are
filtered before they reach the database - a scoped-out caller never learns
the row exists. Tenant isolation is enforced first, at ``scope_church`` /
``ensure_my_church``, so a class id from another church can never be reached
by guessing it.
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
from app.models.church import Church
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.teacher_check import TeacherCheck
from app.models.user import User

logger = get_logger(__name__)

#: Roles allowed to write the directories (classes, servants, accounts, groups)
#: and to run the servant review. Each one is limited to his own church and,
#: inside it, to his own class set.
MANAGERS = (
    RoleEnum.ADMIN,
    RoleEnum.GENERAL_ADMIN,
    RoleEnum.ABONA,
    RoleEnum.SUPER_ADMIN,
)

#: Every login except a boy's - i.e. everyone attached to a church.
STAFF = (
    RoleEnum.TEACHER,
    RoleEnum.ADMIN,
    RoleEnum.GENERAL_ADMIN,
    RoleEnum.ABONA,
    RoleEnum.SUPER_ADMIN,
)

#: Roles allowed to review servants (a boy has no business on that page).
REVIEWERS = (
    RoleEnum.TEACHER,
    RoleEnum.ADMIN,
    RoleEnum.GENERAL_ADMIN,
    RoleEnum.ABONA,
    RoleEnum.SUPER_ADMIN,
)

#: Roles that may create / rename / retire a class. A stage amin is deliberately
#: left out: he is answerable for classes that already exist, he does not
#: invent them. The church amin (abona) may, since every class in his church is
#: his.
CLASS_KEEPERS = (RoleEnum.ADMIN, RoleEnum.ABONA, RoleEnum.SUPER_ADMIN)


# ============================================================== who am I


def is_manager(user: User) -> bool:
    """Class amin, stage amin, church amin or the platform owner."""
    return user.role in MANAGERS


# ============================================================ tenancy


def my_church_ids(user: User) -> list[int] | None:
    """Churches this login may touch; ``None`` means every church.

    Only the platform owner has no church. Every other role is pinned to
    ``users.church_id``; a NULL there (a misconfigured account) yields an empty
    set rather than "all", so a broken account can never leak another tenant.

    The owner may narrow his whole session to one church from the header
    filter; that choice arrives as ``user.selected_church_id`` and is applied
    here so every scoped read follows it without each route knowing about it.
    """
    if user.role == RoleEnum.SUPER_ADMIN:
        selected = getattr(user, "selected_church_id", None)
        return None if selected is None else [int(selected)]
    if user.church_id is None:
        return []
    return [user.church_id]


def default_church_id(db: Session) -> int:
    """Id of the bootstrap church named in settings, creating it if missing.

    Used when the platform owner writes a row without naming a church, so a
    super-admin create never lands with a NULL ``church_id``.
    """
    from app.config.settings import settings

    church = db.query(Church).filter(Church.name == settings.DEFAULT_CHURCH_NAME).first()
    if church is not None:
        return church.id
    church = Church(
        name=settings.DEFAULT_CHURCH_NAME,
        region=settings.DEFAULT_CHURCH_REGION,
        address=settings.DEFAULT_CHURCH_ADDRESS,
        phone=settings.DEFAULT_CHURCH_PHONE,
        phone_2=settings.DEFAULT_CHURCH_PHONE_2,
    )
    db.add(church)
    db.flush()
    return church.id


def target_church_id(
    db: Session,
    user: User,
    requested_church_id: int | None = None,
    *,
    class_id: int | None = None,
    person=None,
) -> int:
    """Resolve the church a newly-written row belongs to.

    A tenant user is *always* pinned to his own church: a supplied church that
    differs is a 403, never a silent reassignment. The platform owner may name
    any church; when he does not, the church is inferred from the class or the
    person, and finally falls back to the configured default church.
    """
    if requested_church_id is not None and db.get(Church, int(requested_church_id)) is None:
        deny("That church does not exist.")
    if user.role == RoleEnum.SUPER_ADMIN:
        if requested_church_id is not None:
            return int(requested_church_id)
        if class_id is not None:
            klass = db.get(SchoolClass, class_id)
            if klass is not None:
                return klass.church_id
        if person is not None and getattr(person, "church_id", None) is not None:
            return person.church_id
        # A class created while the header is filtered belongs to that church,
        # not to the bootstrap default.
        selected = getattr(user, "selected_church_id", None)
        if selected is not None:
            return int(selected)
        return default_church_id(db)

    if user.church_id is None:
        deny("Your account is not assigned to a church.")
    if requested_church_id is not None and int(requested_church_id) != user.church_id:
        deny("You can only write to your own church.")
    return user.church_id


def ensure_my_church(db: Session, user: User, church_id: int | None) -> None:
    """403 unless ``church_id`` is a church this login may touch.

    The platform owner normally passes for every church, but while the header
    filter is set to one church his whole view is narrowed to it - including
    writes - so a row from another tenant is refused here too.
    """
    ids = my_church_ids(user)
    if ids is None:
        return
    if church_id is None or church_id not in ids:
        deny("You do not have access to that church.")


def scope_church(query: Query, model, user: User) -> Query:
    """Keep only rows of the login's church (super admin keeps everything)."""
    ids = my_church_ids(user)
    return query if ids is None else query.filter(model.church_id.in_(ids))


def owner_class_id(db: Session, user: User) -> int | None:
    """The class sitting behind this login's owner row, if it has one.

    ``users.teacher_id`` -> ``teachers.class_id``, ``users.boy_id`` ->
    ``boys.class_id``. It answers "whose class is this row?", never "which
    classes may he see": a stage amin is not pinned to his servant row's class
    and the church-wide amin has no owner row at all - ask
    :func:`my_class_ids` for the scope.
    """
    if user.teacher_id is not None:
        teacher = db.get(Teacher, user.teacher_id)
        return teacher.class_id if teacher is not None else None
    if user.boy_id is not None:
        boy = db.get(Boy, user.boy_id)
        return boy.class_id if boy is not None else None
    return None


def my_class_ids(db: Session, user: User) -> list[int] | None:
    """Every class this login belongs to; ``None`` means every class everywhere.

    Only the platform owner is unrestricted across churches. The church amin
    (``abona``) gets every class of his own church (a concrete list, never
    ``None`` - his limit is the church, enforced by ``scope_church``). A stage
    amin is limited to ``general_admin_classes``: an empty set means he sees
    nothing until a class is assigned. Everyone else is pinned to the single
    class of his servant / boy row.
    """
    if user.role == RoleEnum.SUPER_ADMIN:
        selected = getattr(user, "selected_church_id", None)
        if selected is None:
            return None
        # While the header is filtered, "every class" means every class of the
        # selected church - not every class on the platform.
        return [
            row[0]
            for row in db.query(SchoolClass.id).filter(
                SchoolClass.church_id == int(selected)
            )
        ]
    if user.role == RoleEnum.ABONA:
        return [
            row[0]
            for row in db.query(SchoolClass.id).filter(
                SchoolClass.church_id == user.church_id
            )
        ]
    if user.role == RoleEnum.GENERAL_ADMIN:
        return list(user.managed_class_ids)
    single = owner_class_id(db, user)
    return [] if single is None else [single]


def is_unrestricted(user: User) -> bool:
    """True only for the platform owner - the one scope with no class limit."""
    return user.role == RoleEnum.SUPER_ADMIN


# ================================================================= guards


def deny(detail: str, code: int = status.HTTP_403_FORBIDDEN) -> None:
    raise HTTPException(status_code=code, detail=detail)


def ensure_roles(user: User, *roles: RoleEnum) -> None:
    """403 unless the login holds one of ``roles``."""
    if user.role not in roles:
        deny("You do not have permission to perform this operation.")


def ensure_manager(user: User) -> None:
    """403 unless the login is any kind of amin."""
    if user.role not in MANAGERS:
        deny("Only an amin can do that.")


def ensure_staff(user: User) -> None:
    """403 for a boy's login - servant-only pages start here."""
    if user.role not in STAFF:
        deny("You do not have permission to view servants.")


def ensure_my_class(db: Session, user: User, class_id: int | None) -> None:
    """403 unless ``class_id`` is one of the login's classes (owner passes).

    The church is checked first: a class from another tenant is refused even
    if a caller somehow guessed its id.
    """
    if class_id is None:
        deny("You do not have access to that class.")
    if user.role != RoleEnum.SUPER_ADMIN:
        klass = db.get(SchoolClass, class_id)
        ensure_my_church(db, user, klass.church_id if klass is not None else None)
    mine = my_class_ids(db, user)
    if mine is None:  # super admin
        return
    if class_id not in mine:
        deny("You do not have access to that class.")


def ensure_boy_access(db: Session, user: User, boy: Boy) -> None:
    """403 unless the login may read this boy (a boy: only himself)."""
    # Church first, for every role: a filtered platform owner is pinned to the
    # selected church just like a tenant login is pinned to its own.
    ensure_my_church(db, user, boy.church_id)
    if user.role == RoleEnum.SUPER_ADMIN:
        return
    if user.role == RoleEnum.USER:
        if boy.id != user.boy_id:
            deny("You can only view your own record.")
        return
    ensure_my_class(db, user, boy.class_id)


def ensure_teacher_access(db: Session, user: User, teacher: Teacher) -> None:
    """403 unless the login may read this servant (a servant: only himself)."""
    ensure_my_church(db, user, teacher.church_id)
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
    """Keep only rows of the login's church **and** own classes.

    Church first: every model passed here (class, attend, task, trip, ...) has a
    ``church_id``, so a guessed id from another tenant is filtered out before
    the class test even runs. The platform owner keeps everything.
    """
    query = scope_church(query, model, user)
    class_ids = my_class_ids(db, user)
    return query if class_ids is None else query.filter(model.class_id.in_(class_ids))


def scope_boys(db: Session, query: Query, model, user: User, boy_column) -> Query:
    """Keep only rows attached to a boy this login may see.

    ``boy_column`` is the id column holding the boy (``Boy.id``,
    ``Attend.boy_id``, ``FollowUp.boy_id``). Every one of those tables also
    carries ``class_id``, so the class filter needs no join.
    """
    if user.role == RoleEnum.USER:
        return scope_church(query, model, user).filter(boy_column == user.boy_id)
    return scope_classes(db, query, model, user)


def scope_teachers(db: Session, query: Query, user: User) -> Query:
    """Servants this login may see: a servant only himself, staff his classes."""
    ensure_staff(user)
    church_ids = my_church_ids(user)
    if user.role == RoleEnum.SUPER_ADMIN and church_ids is None:
        return query
    query = scope_church(query, Teacher, user)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(Teacher.id == user.teacher_id)
    return query.filter(Teacher.class_id.in_(my_class_ids(db, user) or []))


def scope_follow_ups(db: Session, query: Query, user: User) -> Query:
    """Follow-up rows this login may see.

    A boy sees the calls made about him, a servant only the ones he wrote,
    an amin every row of his classes.
    """
    church_ids = my_church_ids(user)
    if user.role == RoleEnum.SUPER_ADMIN and church_ids is None:
        return query
    query = scope_church(query, FollowUp, user)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(FollowUp.teacher_id == user.teacher_id)
    if user.role == RoleEnum.USER:
        return query.filter(FollowUp.boy_id == user.boy_id)
    return query.filter(FollowUp.class_id.in_(my_class_ids(db, user) or []))


def scope_checks(db: Session, query: Query, user: User) -> Query:
    """Servant review rows: a servant his own reviews, staff their classes."""
    ensure_roles(user, *REVIEWERS)
    church_ids = my_church_ids(user)
    if user.role == RoleEnum.SUPER_ADMIN and church_ids is None:
        return query
    query = scope_church(query, TeacherCheck, user)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role == RoleEnum.TEACHER:
        return query.filter(TeacherCheck.teacher_id == user.teacher_id)
    return query.filter(TeacherCheck.class_id.in_(my_class_ids(db, user) or []))


def scope_users(db: Session, query: Query, user: User) -> Query:
    """Accounts this login may see.

    super admin: every login.  servant / boy: only their own.
    an amin: the accounts of the servants and boys of his classes - and the
    church is always checked first, so no other tenant's login leaks.
    """
    church_ids = my_church_ids(user)
    if user.role == RoleEnum.SUPER_ADMIN and church_ids is None:
        return query
    query = scope_church(query, User, user)
    if user.role == RoleEnum.SUPER_ADMIN:
        return query
    if user.role in (RoleEnum.TEACHER, RoleEnum.USER):
        return query.filter(User.id == user.id)
    class_ids = my_class_ids(db, user) or []
    teacher_ids = [
        row[0]
        for row in db.query(Teacher.id).filter(
            Teacher.church_id == user.church_id, Teacher.class_id.in_(class_ids)
        )
    ]
    boy_ids = [
        row[0]
        for row in db.query(Boy.id).filter(
            Boy.church_id == user.church_id, Boy.class_id.in_(class_ids)
        )
    ]
    # His own login always answers: a stage amin without a servant row would
    # otherwise be locked out of his account (even his own password).
    return query.filter(
        or_(User.id == user.id, User.teacher_id.in_(teacher_ids), User.boy_id.in_(boy_ids))
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


def ensure_name_free(
    db: Session,
    model: Any,
    name_field: str,
    name: str,
    class_id: int | None,
    *,
    label: str,
    exclude_id: int | None = None,
) -> None:
    """409 when another row already carries this name in the same class.

    A person's name only has to be unique *inside* a class, and the comparison
    ignores case and runs of whitespace (see :func:`normalise_name`), so
    ``'Mina '`` and ``'mina'`` are treated as the same boy/servant. Used by the
    create *and* the spreadsheet import of both the boys and servants
    directories, so a re-uploaded sheet no longer creates twins.
    """
    wanted = normalise_name(name)
    query = db.query(model).filter(model.class_id == class_id)
    if exclude_id is not None:
        query = query.filter(model.id != exclude_id)
    for row in query.all():
        if normalise_name(getattr(row, name_field)) == wanted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{label}: '{name}' already exists in that class.",
            )


def ensure_phone_free(
    db: Session,
    model: Any,
    *,
    phone: str | None = None,
    phone2: str | None = None,
    exclude_id: int | None = None,
    label: str = "Record",
) -> None:
    """409 when any of the provided phones is already in use on another row.

    Phones are normalised before comparison against ``User`` (the login table)
    and against the given ``model`` (Boy/Teacher).
    """
    from app.models.user import User

    phones: list[str] = []
    if phone:
        phones.append(normalise_phone(phone))
    if phone2:
        phones.append(normalise_phone(phone2))
    # dedupe
    seen: set[str] = set()
    for p in phones:
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        # check against User accounts
        user_q = db.query(User).filter(User.phone == p)
        if user_q.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{label}: phone '{p}' already exists.",
            )
        # check against the model itself (Boy/Teacher)
        q = db.query(model).filter(or_(model.phone == p, model.phone_2 == p))
        if exclude_id is not None:
            q = q.filter(model.id != exclude_id)
        if q.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{label}: phone '{p}' already exists.",
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


def normalise_phone(value: Any) -> Any:
    """Reduce every way a phone is written to the one shape stored in the DB.

    A spreadsheet cell or a form can hand us any of::

        1281875199            # bare 10-digit mobile (no trunk 0)
        01281875199           # already correct
        +201281875199         # country code with a plus
        +2012 818 75199       # country code, human spacing
        00201281875199        # country code dialled internationally

    and every one of them must land in the database as ``01281875199`` so a
    later login finds it again. Non-strings (``None``, a number) pass through
    untouched so a nullable column stays nullable.

    Rules, applied in order:
    * keep the digits only - drops ``+``, spaces, dashes and brackets;
    * ``0020…`` (international prefix) -> ``0…``;
    * ``20…`` written with 12 digits (country code without a plus) -> ``0…``;
    * a bare 10-digit mobile ``1…`` -> prepend the trunk ``0``.
    """
    if not isinstance(value, str):
        return value
    cleaned = re.sub(r"\D", "", value)
    if cleaned.startswith("0020"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("20") and len(cleaned) >= 12:
        cleaned = "0" + cleaned[2:]
    if len(cleaned) == 10 and cleaned.startswith("1"):
        cleaned = "0" + cleaned
    return cleaned


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