"""Boys master data - the main directory the whole app revolves around."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    bulk_create,
    commit,
    ensure_name_free,
    ensure_teacher_access,
    get_or_404,
    scope_boys,
)
from app.core.data.names import ensure_full_name, ensure_name_addable
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.group import Group
from app.models.teacher import Teacher
from app.schemas.boy import BoyCreate, BoyUpdate

#: ``teacher_id`` is not a column - it files the boy under a servant's
#: follow-up group, so it is handled apart from the plain PATCH fields.
_ASSIGN = "teacher_id"

#: The payload said nothing about the group (``null`` means "drop it").
_NOT_SENT = object()


class BoyService(BaseService):
    """read : super_admin all | admin his class | teacher his class | boy himself
    write: super_admin all | admin his class | teacher his class
    """


    def query(self) -> Query:
        return scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)

    def list(
        self, class_id: int | None = None, issue_flag: bool | None = None
    ) -> list[Boy]:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Boy.class_id == class_id)
        if issue_flag is not None:
            query = query.filter(Boy.issue_flag == issue_flag)
        return query.order_by(Boy.boy_name).all()

    def get(self, boy_id: int) -> Boy:
        boy = self.query().filter(Boy.id == boy_id).first()
        if boy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Boy {boy_id} not found.",
            )
        return boy

    def create(self, data: BoyCreate, *, from_sheet: bool = False) -> Boy:
        """File a new boy.

        A form answer is checked against every name this login can see: three
        parts, and nobody already on file. A sheet row keeps the rule it always
        had - one boy per name per class - because a spreadsheet cannot answer
        a question back mid-import.
        """
        self._ensure_may_write()
        self.ensure_class(data.class_id)
        boy_name = " ".join(data.boy_name.split())

        if from_sheet:
            ensure_name_free(
                self.db, Boy, "boy_name", boy_name, data.class_id, label="Boy"
            )
        else:
            ensure_full_name(boy_name)
            ensure_name_addable(
                self.db,
                self.user,
                boy_name,
                confirm_similar=data.confirm_similar,
            )

        boy = Boy(
            boy_name=boy_name,
            gender=data.gender,
            birth_date=data.birth_date,
            phone=data.phone,
            phone_2=data.phone_2,
            zone=data.zone,
            address=data.address,
            latitude=data.latitude,
            longitude=data.longitude,
            father_name=data.father_name,
            national_id=data.national_id,
            skills=data.skills,
            class_id=data.class_id,
            last_visit_date=data.last_visit_date,
            note=data.note,
            issue_flag=data.issue_flag,
        )
        self.db.add(boy)
        if data.teacher_id is not None:
            self.db.flush()  # the group row needs boy.id
            self._assign_servant(boy, data.teacher_id)
        commit(self.db, f"Boy create name={data.boy_name}")
        return boy

    def add_list(self, items: list[BoyCreate]) -> dict:
        """Bulk import - a bad row never stops the rest. The write permission
        is checked once up front so a login without it gets a single 403
        instead of one failure per row."""
        self._ensure_may_write()
        return bulk_create(
            lambda item: self.create(item, from_sheet=True),
            items,
            label="boys",
            name_attr="boy_name",
        )

    def update(self, boy_id: int, data: BoyUpdate) -> Boy:
        self._ensure_may_write()
        boy = self.get(boy_id)
        self.ensure_class(boy.class_id)

        old_class = boy.class_id
        teacher_id = data.teacher_id if _ASSIGN in data.model_fields_set else _NOT_SENT
        apply_update(boy, data, skip=(_ASSIGN,), strip=("boy_name",))
        self.ensure_class(boy.class_id)

        if teacher_id is _NOT_SENT:
            # Moving class silently ends the membership: a servant of another
            # class cannot keep a boy he is no longer allowed to see.
            if boy.class_id != old_class:
                self._drop_group(boy.id)
        elif teacher_id is None:
            self._drop_group(boy.id)
        else:
            self._assign_servant(boy, teacher_id)

        commit(self.db, f"Boy update id={boy_id}")
        return boy

    def delete(self, boy_id: int) -> None:
        boy = self.get(boy_id)
        self._ensure_may_write()
        self.db.delete(boy)
        # A boy with attendance / follow-up history is refused by RESTRICT.
        commit(self.db, f"Boy delete id={boy_id}")

    # -------------------------------------------------------------- internals
    def _ensure_may_write(self) -> None:
        """A boy login may read his own row but never write it."""
        if self.user.role == RoleEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the class amin, the super admin or a servant can do that.",
            )

    def _drop_group(self, boy_id: int) -> None:
        self.db.query(Group).filter(Group.boy_id == boy_id).delete(
            synchronize_session=False
        )

    def _assign_servant(self, boy: Boy, teacher_id: int) -> None:
        """File the boy under a servant's follow-up group.

        Same contract as ``POST /groups/assign``: the servant must exist, live
        in the boy's class and be visible to this login - and since a boy
        belongs to exactly one group, any previous row is dropped first.
        """
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_teacher_access(self.db, self.user, teacher)
        if teacher.class_id != boy.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Servant '{teacher.teacher_name}' is not in "
                    f"'{boy.boy_name}'s class."
                ),
            )
        self._drop_group(boy.id)
        self.db.add(Group(teacher_id=teacher.id, boy_id=boy.id))
