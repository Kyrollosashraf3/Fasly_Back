"""المسابقات (tasks): كل فصل مسابقاته ومكافأة كل واحدة بالطايو."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    is_unrestricted,
    owner_class_id,
)
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService(BaseService):
    """مسابقات الفصل: القراءة، والإضافة/التعديل/الحذف لأمناء الفصل.

    القراءة:
      - الخادم / أمين الفصل: مسابقات فصله.
      - أمين المرحلة: مسابقات فصوله.
      - أمين الكنيسة (سوبر أدمن): كل الفصول، ويرشّح فصل بعينه بـ ``class_id``.

    الكتابة (create / edit / delete):
      - أمين الفصل عليه في فصله فقط (يُفرض ``class_id``).
      - أمين المرحلة: أي فصل من فصوله.
      - الأدمن العام يختار أي فصل.
      - الخادم والولد مرفوضان: الخادم يسجل التسميع، ما يفتحش مسابقة.
    """

    def query(self) -> Query:
        return self.classes_query(Task)

    def list(
        self,
        status: str | None = 'active',
        class_id: int | None = None,
    ) -> list[Task]:
        """Tasks in scope, newest first.

        ``status`` defaults to the active tasks - what the page is about; an
        amin asks for ``inactive`` to revisit an old task. ``class_id`` narrows
        the list to one class (the super admin choosing a class filter).
        """
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Task.class_id == class_id)
        if status in ('active', 'inactive'):
            query = query.filter(Task.status == status)
        return query.order_by(Task.created_at.desc(), Task.id.desc()).all()

    def get(self, task_id: int) -> Task:
        task = self.query().filter(Task.id == task_id).first()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المسابقة غير موجودة.",
            )
        return task

    def create(self, data: TaskCreate) -> Task:
        self.ensure_manager()

        # أمين الفصل: تُفرض المسابقة على فصله وحده
        if self.user.role == RoleEnum.ADMIN:
            my_class = owner_class_id(self.db, self.user)
            if my_class is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="لا يوجد فصل مرتبط بحسابك.",
                )
            effective_class_id = my_class
        else:
            # الأدمن العام: يحتفظ بالفصل الذي أرسله
            # أمين المرحلة: نفس الفصل، بشرط ما يكونش خارج فصوله
            effective_class_id = data.class_id
            if not is_unrestricted(self.user):
                self.ensure_class(effective_class_id)

        self._ensure_class(effective_class_id)
        self._ensure_no_duplicate(data.task_name.strip(), effective_class_id)
        task = Task(
            task_name=data.task_name.strip(),
            value=data.value,
            church_id=self.church_for(class_id=effective_class_id),
            class_id=effective_class_id,
            created_at=data.created_at or date.today(),
            status=data.status or 'active',
        )
        self.db.add(task)
        commit(self.db, f"Task create name={data.task_name}")
        return task

    def update(self, task_id: int, data: TaskUpdate) -> Task:
        task = self.get(task_id)  # مقسّم على الفصول تلقائيًا
        self.ensure_manager()

        new_name = (data.task_name or "").strip() or task.task_name
        new_class_id = data.class_id if data.class_id is not None else task.class_id

        if self.user.role == RoleEnum.ADMIN:
            # لا يسمح بنقل مسابقة لفصل آخر
            if data.class_id is not None and data.class_id != task.class_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="غير مسموح لك بنقل مسابقة لفصل آخر.",
                )
        elif data.class_id is not None:
            self._ensure_class(data.class_id)
            # أمين المرحلة ما ينقلش مسابقة لفصل خارج فصوله
            if not is_unrestricted(self.user):
                self.ensure_class(data.class_id)

        # لو الاسم أو الفصل اتغيّر، اتأكد إن مفيش مسابقة تانية بنفس الاسم في نفس الفصل
        if (new_name, new_class_id) != (task.task_name, task.class_id):
            self._ensure_no_duplicate(
                new_name, new_class_id, exclude_id=task_id
            )

        apply_update(task, data, strip=("task_name",))
        commit(self.db, f"Task update id={task_id}")
        return task

    def delete(self, task_id: int) -> None:
        task = self.get(task_id)  # مقسّم على الفصول تلقائيًا
        self.ensure_manager()
        self.db.delete(task)
        commit(self.db, f"Task delete id={task_id}")

    def _ensure_class(self, class_id: int) -> None:
        school_class = self.db.get(SchoolClass, class_id)
        if school_class is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الفصل غير موجود.",
            )

    def _ensure_no_duplicate(
        self,
        task_name: str,
        class_id: int,
        exclude_id: int | None = None,
    ) -> None:
        """يمنع مسابقة مكررة: نفس الاسم في نفس الفصل.

        مسابقة بنفس الاسم في فصل تاني رسالة جديدة، كل فصل وبرنامجها.
        """
        query = self.db.query(Task).filter(
            Task.task_name == task_name,
            Task.class_id == class_id,
        )
        if exclude_id is not None:
            query = query.filter(Task.id != exclude_id)
        if query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="مسابقة بهذا الاسم موجودة بالفعل لنفس الفصل.",
            )
