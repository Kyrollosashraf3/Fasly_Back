"""Servants (الخدام) master data - not login accounts."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import apply_update, bulk_create, commit, scope_teachers
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


class TeacherService(BaseService):
    """The servant directory. A login for a servant is created separately in
    ``UserService`` and points back here through ``users.teacher_id``.

    read : super_admin all | admin his class | teacher himself | boy none
    write: super_admin all | admin his class
    """


    def query(self) -> Query:
        return scope_teachers(self.db, self.db.query(Teacher), self.user)

    def list(self, class_id: int | None = None) -> list[Teacher]:
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Teacher.class_id == class_id)
        return query.order_by(Teacher.teacher_name).all()

    def get(self, teacher_id: int) -> Teacher:
        teacher = self.query().filter(Teacher.id == teacher_id).first()
        if teacher is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Servant {teacher_id} not found.",
            )
        return teacher

    def create(self, data: TeacherCreate) -> Teacher:
        self.ensure_manager()
        self.ensure_class(data.class_id)
        teacher_name = data.teacher_name.strip()
        self._ensure_name_free(teacher_name, data.class_id)
        teacher = Teacher(
            teacher_name=teacher_name,
            phone=data.phone,
            class_id=data.class_id,
            last_visit_date=data.last_visit_date,
            note=data.note,
        )
        self.db.add(teacher)
        commit(self.db, f"Servant create name={teacher_name}")
        return teacher

    def add_list(self, items: list[TeacherCreate]) -> dict:
        """Bulk import - a bad row never stops the rest. The write permission
        is checked once up front so a non-manager gets a single 403 instead of
        one failure per row."""
        self.ensure_manager()
        return bulk_create(
            self.create, items, label="servants", name_attr="teacher_name"
        )

    def update(self, teacher_id: int, data: TeacherUpdate) -> Teacher:
        teacher = self.get(teacher_id)
        self.ensure_manager()
        apply_update(teacher, data, strip=("teacher_name",))
        self.ensure_class(teacher.class_id)
        if data.model_fields_set & {"teacher_name", "class_id"}:
            self._ensure_name_free(
                teacher.teacher_name, teacher.class_id, exclude_id=teacher_id
            )
        commit(self.db, f"Servant update id={teacher_id}")
        return teacher

    def delete(self, teacher_id: int) -> None:
        teacher = self.get(teacher_id)
        self.ensure_manager()
        self.db.delete(teacher)
        # A servant with recorded follow-ups / reviews is refused by RESTRICT.
        commit(self.db, f"Servant delete id={teacher_id}")

    def _ensure_name_free(
        self, teacher_name: str, class_id: int, exclude_id: int | None = None
    ) -> None:
        """Names only need to be unique *inside* a class."""
        query = self.db.query(Teacher).filter(
            Teacher.teacher_name == teacher_name, Teacher.class_id == class_id
        )
        if exclude_id is not None:
            query = query.filter(Teacher.id != exclude_id)
        if query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Teacher: '{teacher_name}' already exists in that class.",
            )
