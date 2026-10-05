"""Boys master data."""

from fastapi import HTTPException, status

from app.core.data.base import AdminService
from app.core.data.common import bulk_create
from app.models.boy import Boy
from app.models.group import Group
from app.models.teacher import Teacher
from app.schemas.boy import BoyCreate, BoyUpdate

_MISSING = object()


class BoyService(AdminService):
    """The main directory.

    read : super_admin all | admin his class | teacher his group's boys | user himself
    write: super_admin all | admin his class
    """

    def _query(self):
        return self.scope.restrict_boys(self.db.query(Boy), Boy, Boy.id)

    def _assign_servant(self, boy: Boy, teacher_id: int) -> None:
        """File the boy under a servant's follow-up group.

        Same contract as ``POST /groups/assign``: the servant must exist, live
        in the boy's class and be visible to this login - and since a boy
        belongs to exactly one group, any previous row is dropped first.
        """
        teacher = self.db.get(Teacher, teacher_id)
        if teacher is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Servant {teacher_id} not found.",
            )
        self.scope.ensure_class(teacher.class_id)
        if teacher.class_id != boy.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Servant '{teacher.teacher_name}' is not in "
                    f"'{boy.boy_name}'s class."
                ),
            )
        self.db.query(Group).filter(Group.boy_id == boy.id).delete(
            synchronize_session=False
        )
        self.db.add(Group(teacher_id=teacher.id, boy_id=boy.id))

    def create(self, data: BoyCreate) -> Boy:
        self._ensure_write()
        self.scope.ensure_class(data.class_id)
        boy = Boy(
            boy_name=data.boy_name.strip(),
            gender=data.gender,
            birth_date=data.birth_date,
            phone=data.phone,
            phone_2=data.phone_2,
            zone=data.zone,
            address=data.address,
            location=data.location,
            class_id=data.class_id,
            note=data.note,
            issue_flag=data.issue_flag,
        )
        self.db.add(boy)
        if data.teacher_id is not None:
            self.db.flush()  # the group row needs boy.id
            self._assign_servant(boy, data.teacher_id)
        self._commit(f"Boy create name={data.boy_name}")
        return boy

    def add_list(self, items: list[BoyCreate]) -> dict:
        """Bulk import - a bad row never stops the rest.

        The write permission is checked once up front so a non-manager gets a
        single 403 instead of one failure per row.
        """
        self._ensure_write()
        return bulk_create(
            self.create, items, label="boys", name_attr="boy_name"
        )

    def get(self, boy_id: int) -> Boy:
        boy = self._query().filter(Boy.id == boy_id).first()
        if boy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Boy {boy_id} not found.",
            )
        return boy

    def list(self, class_id: int | None = None, issue_flag: bool | None = None):
        query = self._query()
        if class_id is not None:
            self.scope.ensure_class(class_id)
            query = query.filter(Boy.class_id == class_id)
        if issue_flag is not None:
            query = query.filter(Boy.issue_flag == issue_flag)
        return query.order_by(Boy.boy_name).all()

    def update(self, boy_id: int, data: BoyUpdate) -> Boy:
        boy = self.get(boy_id)
        self._ensure_write()
        updates = data.model_dump(exclude_unset=True)
        teacher_id = updates.pop("teacher_id", _MISSING)
        old_class = boy.class_id
        if "class_id" in updates:
            self.scope.ensure_class(updates["class_id"])
        if "boy_name" in updates:
            updates["boy_name"] = updates["boy_name"].strip()
        for field, value in updates.items():
            setattr(boy, field, value)

        if teacher_id is _MISSING:
            # Moving class silently ends the membership: a servant of another
            # class cannot keep a boy he is no longer allowed to see.
            if boy.class_id != old_class:
                self.db.query(Group).filter(Group.boy_id == boy.id).delete(
                    synchronize_session=False
                )
        elif teacher_id is None:
            self.db.query(Group).filter(Group.boy_id == boy.id).delete(
                synchronize_session=False
            )
        else:
            self._assign_servant(boy, teacher_id)

        self._commit(f"Boy update id={boy_id}")
        return boy

    def delete(self, boy_id: int) -> None:
        boy = self.get(boy_id)
        self._ensure_write()
        self.db.delete(boy)
        # a boy with attendance / follow-up history is refused by RESTRICT
        self._commit(f"Boy delete id={boy_id}")
