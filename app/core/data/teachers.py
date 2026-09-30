"""Servants (خدام) master data - not login accounts."""

from fastapi import HTTPException, status

from app.core.data.base import AdminService
from app.core.data.common import bulk_create
from app.models.enums import RoleEnum
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


class TeacherService(AdminService):
    """Servant directory. The login for a servant is created separately in
    ``UserService`` and points back here through ``users.teacher_id``.

    read : super_admin all | admin his class | teacher himself | user none
    write: super_admin all | admin his class
    """

    def _query(self):
        role = self.scope.role
        if role == RoleEnum.USER:
            self.scope.deny("You do not have permission to view servants.")
        if role == RoleEnum.TEACHER:
            return self.db.query(Teacher).filter(
                Teacher.id == self.scope.teacher_id
            )
        return self.scope.restrict_class(self.db.query(Teacher), Teacher)

    def _ensure_name_free(
        self, teacher_name: str, class_id: int, exclude_id: int | None = None
    ) -> None:
        """Names only need to be unique *inside* a class."""
        query = self.db.query(Teacher).filter(
            Teacher.teacher_name == teacher_name,
            Teacher.class_id == class_id,
        )
        if exclude_id is not None:
            query = query.filter(Teacher.id != exclude_id)
        if query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Teacher: '{teacher_name}' already exists in that class.",
            )

    def create(self, data: TeacherCreate) -> Teacher:
        self._ensure_write()
        self.scope.ensure_class(data.class_id)
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
        self._commit(f"Teacher create name={teacher_name}")
        return teacher

    def add_list(self, items: list[TeacherCreate]) -> dict:
        """Bulk import - checked once up front so a non-manager gets a single
        403 instead of one failure per row."""
        self._ensure_write()
        return bulk_create(
            self.create, items, label="teachers", name_attr="teacher_name"
        )

    def get(self, teacher_id: int) -> Teacher:
        teacher = self._query().filter(Teacher.id == teacher_id).first()
        if teacher is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Servant {teacher_id} not found.",
            )
        return teacher

    def list(self, class_id: int | None = None):
        query = self._query()
        if class_id is not None:
            self.scope.ensure_class(class_id)
            query = query.filter(Teacher.class_id == class_id)
        return query.order_by(Teacher.teacher_name).all()

    def update(self, teacher_id: int, data: TeacherUpdate) -> Teacher:
        teacher = self.get(teacher_id)
        self._ensure_write()
        updates = data.model_dump(exclude_unset=True)
        if "class_id" in updates:
            self.scope.ensure_class(updates["class_id"])
        if "teacher_name" in updates:
            updates["teacher_name"] = updates["teacher_name"].strip()
            self._ensure_name_free(
                updates["teacher_name"],
                updates.get("class_id", teacher.class_id),
                exclude_id=teacher_id,
            )
        for field, value in updates.items():
            setattr(teacher, field, value)
        self._commit(f"Teacher update id={teacher_id}")
        return teacher

    def delete(self, teacher_id: int) -> None:
        teacher = self.get(teacher_id)
        self._ensure_write()
        self.db.delete(teacher)
        # refuses with 409 while follow-ups / checks still reference him
        self._commit(f"Teacher delete id={teacher_id}")
