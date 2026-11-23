"""تسميعات الأولاد في المسابقات: مين سمّع، ومين سمّعله، وهل استلم الطايو."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, joinedload

from app.core.data.base import BaseService
from app.core.data.common import apply_update, commit, deny, ensure_boy_access
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.task import Task
from app.models.task_value import TaskValue
from app.schemas.task_value import (
    TaskValueCreate,
    TaskValueDuesBulk,
    TaskValueUpdate,
)


class TaskValueService(BaseService):
    """سطر واحد لكل تسميع: ``(task_id, boy_id)`` لا يتكرر.

    القراءة:
      - الولد (``user``): تسميعاته هو فقط.
      - الخادم / أمين الفصل: تسميعات أولاد فصله.
      - الأدمن العام: كل التسميعات.

    الكتابة:
      - تسجيل التسميع وحفظ المستحقات: خادم أو أمين فصل أو أدمن عام.
      - حذف سجل: أمين فصل أو أدمن عام - اللي غلط في علامة يستخدم التعديل.
    """

    # ------------------------------------------------------------- read
    def query(self) -> Query:
        """Rows this login may see, scoped on the class snapshotted at saving."""
        q = self.db.query(TaskValue)
        if self.user.role == RoleEnum.USER:
            from app.core.data.common import scope_church

            return scope_church(q, TaskValue, self.user).filter(
                TaskValue.boy_id == self.user.boy_id
            )
        return self.classes_query(TaskValue)

    @staticmethod
    def _with_names(query: Query) -> Query:
        """Eager-load everything the response names (boy, task, servant)."""
        return query.options(
            joinedload(TaskValue.boy),
            joinedload(TaskValue.task),
            joinedload(TaskValue.teacher),
        )

    def list(
        self,
        task_id: int | None = None,
        received: bool | None = None,
        class_id: int | None = None,
    ) -> list[TaskValue]:
        """Recitations in scope, newest recitation first.

        ``task_id`` opens one task's own ledger (what the module is about);
        ``received`` splits the dues page from what was already handed over;
        ``class_id`` narrows to one class for the super admin's filter.
        """
        query = self._with_names(self.query())
        if task_id is not None:
            query = query.filter(TaskValue.task_id == task_id)
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(TaskValue.class_id == class_id)
        if received is not None:
            query = query.filter(TaskValue.received == received)
        return query.order_by(TaskValue.action_date.desc(), TaskValue.id.desc()).all()

    def get(self, value_id: int) -> TaskValue:
        record = (
            self._with_names(self.query()).filter(TaskValue.id == value_id).first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="التسميع غير موجود.",
            )
        return record

    # ------------------------------------------------------------ write
    def create(self, data: TaskValueCreate) -> TaskValue:
        self.ensure_staff()

        task = self.db.get(Task, data.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المسابقة غير موجودة.",
            )
        self.ensure_class(task.class_id)

        boy = self.db.get(Boy, data.boy_id)
        if boy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الولد غير موجود.",
            )
        ensure_boy_access(self.db, self.user, boy)
        if boy.class_id != task.class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="الولد ليس في فصل هذه المسابقة.",
            )

        duplicate = (
            self.db.query(TaskValue)
            .filter(TaskValue.task_id == task.id, TaskValue.boy_id == boy.id)
            .first()
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{boy.boy_name} سمّع «{task.task_name}» من قبل "
                    f"في {duplicate.action_date:%d/%m/%Y}. "
                    "كل مسابقة لها تسجيلها لوحدها."
                ),
            )

        record = TaskValue(
            church_id=self.church_for(class_id=boy.class_id, person=boy),
            class_id=boy.class_id,  # snapshot taken now
            task_id=task.id,
            boy_id=boy.id,
            action_date=data.action_date or date.today(),
            received=bool(data.received),
            created_by=self.user.teacher_id,
        )
        self.db.add(record)
        commit(self.db, f"TaskValue create task={task.id} boy={boy.id}")
        return self.get(record.id)

    def update(self, value_id: int, data: TaskValueUpdate) -> TaskValue:
        record = self.get(value_id)  # scoped to the login's class already
        self.ensure_staff()
        apply_update(record, data)
        commit(self.db, f"TaskValue update id={value_id}")
        return record

    def save_dues(self, data: TaskValueDuesBulk) -> list[TaskValue]:
        """The dues page saved at once - every tick lands or none does."""
        self.ensure_staff()
        records = []
        for item in data.items:
            record = self.get(item.id)  # 404 on a row outside this login's class
            record.received = item.received
            records.append(record)
        commit(self.db, f"TaskValue dues saved count={len(records)}")
        return [self.get(record.id) for record in records]

    def delete(self, value_id: int) -> None:
        """Dropping a whole row is an amin action - a servant who ticked a
        recitation wrong uses ``update`` instead."""
        record = self.get(value_id)
        self.ensure_manager()
        self.db.delete(record)
        commit(self.db, f"TaskValue delete id={value_id}")

    def ensure_staff(self) -> None:
        """403 for a boy's login: his recitations are recorded for him."""
        if self.user.role == RoleEnum.USER:
            deny("لا يمكنك تسجيل التسميعات. الخادم أو أمين الفصل يسجّلها.")
