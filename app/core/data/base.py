"""The two service bases every service in ``app.core.data`` is built from.

    BaseService          the session, the login, and nothing else
    WeeklySheetService   the shared CRUD of the two Friday sheets

A service module handles one table and nothing more: it calls the check it
needs from ``app.core.data.common``, copies the payload onto the row and
commits. Permission rules never live in a route and never live in a model.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core.data.common import (
    apply_update,
    commit,
    ensure_manager,
    ensure_my_class,
    get_or_404,
    scope_classes,
    target_church_id,
)
from app.features.user.models.user import User


class BaseService:
    """The DB session and the login this request acts as."""

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.user = current_user
        self.user_id = current_user.id

    def classes_query(self, model) -> Query:
        """Every row of ``model`` the login may see (church- and class-scoped)."""
        return scope_classes(self.db, self.db.query(model), model, self.user)

    def church_for(
        self,
        requested_church_id: int | None = None,
        *,
        class_id: int | None = None,
        person=None,
    ) -> int:
        """Resolve the tenant for a row this login is about to write."""
        return target_church_id(
            self.db,
            self.user,
            requested_church_id,
            class_id=class_id,
            person=person,
        )

    def ensure_class(self, class_id: int | None) -> None:
        """403 unless ``class_id`` is the login's own class."""
        ensure_my_class(self.db, self.user, class_id)

    def ensure_manager(self) -> None:
        """403 unless the login may write the directories."""
        ensure_manager(self.user)


class WeeklySheetService(BaseService):
    """CRUD shared by the two Friday sheets: attendance and servant review.

    Both hold **one row per (person, date)** and stamp ``class_id`` as a
    snapshot taken on that date, so promoting boys later never rewrites
    history. A subclass names the person and answers two questions:

        ===========  =============  ==================
        attribute    attendance     servant review
        ===========  =============  ==================
        ``model``    ``Attend``     ``TeacherCheck``
        ``person``   ``Boy``        ``Teacher``
        ``person_fk`` ``boy_id``    ``teacher_id``
        ``person_attr`` ``boy``     ``teacher``
        ``label``    Attendance     Teacher check
        ===========  =============  ==================

        ``query()``          which rows this login may read
        ``can_read(person)`` 403 unless the login may look at that person
        ``can_write(person)`` 403 unless the login may change his row

    Only ``person_fk`` and ``date`` are protected on an update - every other
    field on the payload is copied straight onto the row.
    """

    model = None
    person = None
    person_fk: str = ""      # column holding the person id
    person_attr: str = ""    # relationship to the same person
    label: str = "Record"
    person_label: str = "Person"

    #: the (person, date) pair is the row's identity - a PATCH never moves it
    IDENTITY = ("date",)

    # ------------------------------------------------------------- subclass
    def query(self) -> Query:
        """Every row of this sheet the login may see."""
        return self.classes_query(self.model)

    def can_read(self, person) -> None:
        raise NotImplementedError

    def can_write(self, person) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------ read
    def get(self, record_id: int):
        record = self.query().filter(self.model.id == record_id).first()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.label} {record_id} not found.",
            )
        return record

    def list(
        self, class_id: int | None = None, action_date: date | None = None
    ) -> list:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(self.model.class_id == class_id)
        if action_date is not None:
            query = query.filter(self.model.date == action_date)
        return query.order_by(self.model.date.desc(), self.model.id.desc()).all()

    # ----------------------------------------------------------------- write
    def create(self, data):
        """Save one person's answer, overwriting that day's copy if it exists."""
        person = self._person(getattr(data, self.person_fk))
        record = self._save(person, data, data.date or date.today())
        commit(self.db, f"{self.label} save person={person.id}")
        return record

    def create_bulk(self, data) -> list:
        """The whole sheet in one transaction - it either lands or it does not."""
        action_date = data.date or date.today()
        records = [
            self._save(self._person(getattr(item, self.person_fk)), item, action_date)
            for item in data.items
        ]
        commit(self.db, f"{self.label} bulk {action_date}")
        return records

    def update(self, record_id: int, data):
        record = self.get(record_id)
        self.can_write(getattr(record, self.person_attr))
        apply_update(record, data, skip=self.IDENTITY)
        record.recorded_by = self.user_id
        commit(self.db, f"{self.label} update id={record_id}")
        return record

    def delete(self, record_id: int) -> None:
        """Removing a whole row is an amin action on both sheets - a servant
        who ticked a box wrong uses ``update`` instead."""
        record = self.get(record_id)
        self.ensure_manager()
        self.db.delete(record)
        commit(self.db, f"{self.label} delete id={record_id}")

    # -------------------------------------------------------------- internals
    def _person(self, person_id: int):
        person = get_or_404(self.db, self.person, person_id, self.person_label)
        self.can_read(person)
        self.can_write(person)
        return person

    def _save(self, person, data, action_date: date):
        """Insert the row for (person, date), or refresh today's copy."""
        record = (
            self.db.query(self.model)
            .filter(
                getattr(self.model, self.person_fk) == person.id,
                self.model.date == action_date,
            )
            .first()
        )
        if record is None:
            record = self.model(
                **{
                    self.person_fk: person.id,
                    "date": action_date,
                    "class_id": person.class_id,  # snapshot taken now
                    "church_id": self.church_for(person=person),
                    "recorded_by": self.user_id,
                }
            )
            self.db.add(record)
        else:
            record.recorded_by = self.user_id
        apply_update(record, data, skip=self.IDENTITY)
        return record