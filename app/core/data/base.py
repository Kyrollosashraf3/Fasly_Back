"""Service layer: every route delegates here, and every permission decision
is taken in :class:`Scope` - services only ask it questions.

Permission matrix
-----------------
=============================  ===========  =================  =======================  ==============
operation                      super_admin  admin (أمين فصل)  teacher (خادم)           user (ولد)
=============================  ===========  =================  =======================  ==============
boys / teachers / groups       all          his class          own row / own group      - (boys: self)
attendance                     all          his class          his group's boys         himself
follow_ups                     all          his class          his own rows             himself
teacher_checks                 all          his class          himself                  -
write directory (boys/teachers/                 yes                    no                       no
  classes/users)
write attendance               yes          his class          his group's boys         no
write follow_ups               yes          his class          his own rows             no
write teacher_checks           yes          his class          no                       no
write groups                   yes          his class          no                       no
=============================  ===========  =================  =======================  ==============

A row that falls outside a login's scope is reported as **404**, never 403 -
a scoped-out caller must not learn that the row exists.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core.data.common import commit
from app.models import Boy, Group, Teacher
from app.models.enums import RoleEnum
from app.schemas.user import UserResponse

MANAGER_ROLES = (RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN)


class Scope:
    """What the current login may touch, resolved once per request."""

    def __init__(self, db: Session, current_user: UserResponse):
        self.db = db
        self.user = current_user
        self.role = current_user.role
        self.teacher_id = current_user.teacher_id
        self.boy_id = current_user.boy_id
        self.is_super_admin = current_user.role == RoleEnum.SUPER_ADMIN

        self._class_id: int | None = None
        self._class_resolved = False
        self._group_boy_ids: list[int] | None = None

    # ---------------------------------------------------------------- identity
    @property
    def class_id(self) -> int | None:
        """The single class this login is bound to; ``None`` = unrestricted."""
        if self.is_super_admin:
            return None
        if not self._class_resolved:
            self._class_id = self._resolve_class()
            self._class_resolved = True
        return self._class_id

    def _resolve_class(self) -> int | None:
        if self.teacher_id is not None:
            teacher = self.db.get(Teacher, self.teacher_id)
            return teacher.class_id if teacher is not None else None
        if self.boy_id is not None:
            boy = self.db.get(Boy, self.boy_id)
            return boy.class_id if boy is not None else None
        return None

    def group_boy_ids(self) -> list[int]:
        """Boy ids assigned to this servant's follow-up group (cached)."""
        if self._group_boy_ids is None:
            if self.teacher_id is None:
                self._group_boy_ids = []
            else:
                rows = (
                    self.db.query(Group.boy_id)
                    .filter(Group.teacher_id == self.teacher_id)
                    .all()
                )
                self._group_boy_ids = [row[0] for row in rows]
        return self._group_boy_ids

    # ------------------------------------------------------------------ guards
    @staticmethod
    def deny(detail: str, code: int = status.HTTP_403_FORBIDDEN) -> None:
        raise HTTPException(status_code=code, detail=detail)

    def require_roles(self, *roles: RoleEnum) -> None:
        if self.role not in roles:
            self.deny("You do not have permission to perform this operation.")

    def require_manager(self) -> None:
        """Directory / sheet writes: amin of the class or super admin."""
        if self.role not in MANAGER_ROLES:
            self.deny("Only the class amin or the super admin can do that.")

    def require_class(self) -> int:
        """The class this login manages; 403 when it is not attached to one."""
        class_id = self.class_id
        if class_id is None:
            self.deny("Your account is not attached to a class.")
        return class_id

    def ensure_class(self, class_id: int | None) -> None:
        """Allow super admin always; everyone else only sees their own class."""
        if self.is_super_admin:
            return
        mine = self.class_id
        if class_id is None or mine is None or class_id != mine:
            self.deny("You do not have access to that class.")

    def ensure_boy_visible(self, boy: Boy) -> None:
        if self.is_super_admin:
            return
        if self.role == RoleEnum.USER:
            if boy.id != self.boy_id:
                self.deny("You can only view your own record.")
            return
        if self.role == RoleEnum.TEACHER:
            if boy.class_id != self.require_class():
                self.deny("You do not have access to that class.")
            if boy.id not in self.group_boy_ids():
                self.deny("That boy is not in your follow-up group.")
            return
        self.ensure_class(boy.class_id)  # admin

    def ensure_teacher_visible(self, teacher: Teacher) -> None:
        if self.is_super_admin:
            return
        if self.role == RoleEnum.TEACHER:
            if teacher.id != self.teacher_id:
                self.deny("You can only view your own record.")
            return
        if self.role == RoleEnum.USER:
            self.deny("You do not have permission to view servants.")
        self.ensure_class(teacher.class_id)  # admin

    # ------------------------------------------------------------- query scope
    def restrict_class(self, query: Query, model) -> Query:
        """Keep only rows inside this login's class (identity for super admin)."""
        if self.is_super_admin:
            return query
        return query.filter(model.class_id == self.class_id)

    def restrict_boys(self, query: Query, model, boy_column) -> Query:
        """Keep only rows attached to a boy this login may see.

        ``model`` must expose ``class_id`` (Boy, Attend, FollowUp, ...).
        """
        if self.is_super_admin:
            return query
        if self.role == RoleEnum.USER:
            return query.filter(boy_column == self.boy_id)
        if self.role == RoleEnum.TEACHER:
            return query.filter(boy_column.in_(self.group_boy_ids()))
        return query.filter(model.class_id == self.class_id)  # admin


class BaseService:
    """``db`` + the current login + its :class:`Scope`."""

    def __init__(self, db: Session, current_user: UserResponse):
        self.db = db
        self.current_user = current_user
        self.scope = Scope(db, current_user)

    def _commit(self, context: str) -> None:
        commit(self.db, context)


class AdminService(BaseService):
    """Directories an amin manages: boys, teachers, classes, users.

    Reads are class-scoped through ``self.scope``; every mutation must call
    :meth:`_ensure_write` first so a teacher/boy login can still *read*.
    """

    def _ensure_write(self) -> None:
        self.scope.require_manager()


class ClassScopedService(BaseService):
    """Rows that carry ``class_id``: attendance, follow-ups, checks, groups."""

    def _scoped(self, model) -> Query:
        return self.scope.restrict_class(self.db.query(model), model)


class PersonCheckService(ClassScopedService):
    """CRUD shared by the two Friday sheets (attendance and servant review).

    The subclass supplies the table, the person being checked and their
    column / relationship names:

        model         person_model  person_fk  person_attr  person_label
        -----------   ------------  ---------  -----------  -------------
        Attend        Boy           boy_id     boy          Boy
        TeacherCheck  Teacher       teacher_id teacher      Servant

    Only ``person_fk``/``date`` are protected: everything else on the payload
    (``present``, ``prepare``, ``note``, ...) is copied straight onto the row.
    """

    model = None
    person_model = None
    person_fk: str = ""      # column holding the person id ("boy_id"/"teacher_id")
    person_attr: str = ""    # relationship for the same person ("boy"/"teacher")
    person_label: str = "Person"
    label: str = "Record"

    # ------------------------------------------------------------------ hooks
    def _records_query(self) -> Query:
        return self._scoped(self.model)

    def _ensure_visible(self, person) -> None:
        raise NotImplementedError

    def _ensure_writable(self, person) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------- read
    def _person_for(self, person_id: int):
        person = self.db.get(self.person_model, person_id)
        if person is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.person_label} {person_id} not found.",
            )
        return person

    def get(self, record_id: int):
        record = (
            self._records_query().filter(self.model.id == record_id).first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.label} {record_id} not found.",
            )
        return record

    def list(self, class_id: int | None = None, action_date: date | None = None):
        query = self._records_query()
        if class_id is not None:
            self.scope.ensure_class(class_id)
            query = query.filter(self.model.class_id == class_id)
        if action_date is not None:
            query = query.filter(self.model.date == action_date)
        return query.order_by(self.model.date.desc(), self.model.id.desc()).all()

    # ------------------------------------------------------------------ write
    def _apply(self, record, data) -> None:
        """Copy the payload onto the row, never touching the row's identity."""
        protected = {self.person_fk, "date"}
        for field in data.model_fields_set:
            if field in protected:
                continue
            setattr(record, field, getattr(data, field))

    def _upsert(self, person, action_date: date, data):
        """One row per (person, date): insert it, or refresh today's copy."""
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
                    "class_id": person.class_id,
                    "recorded_by": self.current_user.id,
                }
            )
            self.db.add(record)
        else:
            record.recorded_by = self.current_user.id
        self._apply(record, data)
        return record

    def _create_one(self, data, action_date: date):
        person = self._person_for(getattr(data, self.person_fk))
        self._ensure_visible(person)
        self._ensure_writable(person)
        return self._upsert(person, action_date, data)

    def create(self, data):
        record = self._create_one(data, data.date or date.today())
        self._commit(f"{self.label} create")
        return record

    def create_bulk(self, data) -> list:
        """Whole sheet in one transaction - it either lands or it does not."""
        action_date = data.date or date.today()
        records = [self._create_one(item, action_date) for item in data.items]
        self._commit(f"{self.label} bulk {action_date}")
        return records

    def update(self, record_id: int, data):
        record = self.get(record_id)
        person = getattr(record, self.person_attr)
        self._ensure_writable(person)
        self._apply(record, data)
        record.recorded_by = self.current_user.id
        self._commit(f"{self.label} update id={record_id}")
        return record

    def delete(self, record_id: int) -> None:
        record = self.get(record_id)
        self.scope.require_manager()
        self.db.delete(record)
        self._commit(f"{self.label} delete id={record_id}")
