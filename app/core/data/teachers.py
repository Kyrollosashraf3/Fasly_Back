"""Servants (الخدام) master data - not login accounts."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    bulk_create,
    commit,
    ensure_name_free,
    normalise_phone,
    scope_teachers,
)
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
        from app.core.auth.security import get_password_hash
        from app.models.enums import RoleEnum
        from app.models.user import User

        self.ensure_manager()
        self.ensure_class(data.class_id)
        teacher_name = data.teacher_name.strip()
        self._ensure_name_free(teacher_name, data.class_id)

        # normalise phones
        norm_phone = normalise_phone(data.phone) if data.phone else None
        norm_phone2 = normalise_phone(data.phone_2) if data.phone_2 else None

        # prevent duplicate phones
        from app.core.data.common import ensure_phone_free

        ensure_phone_free(
            self.db,
            Teacher,
            phone=norm_phone,
            phone2=norm_phone2,
            label="Servant",
        )

        teacher = Teacher(
            teacher_name=teacher_name,
            birth_date=data.birth_date,
            phone=norm_phone,
            phone_2=norm_phone2,
            zone=data.zone,
            address=data.address,
            latitude=data.latitude,
            longitude=data.longitude,
            class_id=data.class_id,
            father_name=data.father_name,
            skills=data.skills,
            last_visit_date=data.last_visit_date,
            note=data.note,
        )
        self.db.add(teacher)
        commit(self.db, f"Servant create name={teacher_name}")

        # create user account if teacher has any phone
        target_phone = norm_phone or norm_phone2
        if target_phone:
            from app.core.data.common import ensure_unique

            ensure_unique(self.db, User, "phone", target_phone, label="Account")
            # also ensure no other teacher/user has this phone? keep simple
            user = User(
                phone=target_phone,
                password_hash=None,
                role=RoleEnum.TEACHER,
                teacher_id=teacher.id,
                boy_id=None,
            )
            self.db.add(user)
            commit(self.db, f"User created for teacher {teacher.id} phone={target_phone}")

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
        # Track phone changes to sync to user
        old_phone = teacher.phone
        old_phone2 = teacher.phone_2
        apply_update(teacher, data, strip=("teacher_name",))
        self.ensure_class(teacher.class_id)
        if data.model_fields_set & {"teacher_name", "class_id"}:
            self._ensure_name_free(
                teacher.teacher_name, teacher.class_id, exclude_id=teacher_id
            )
        commit(self.db, f"Servant update id={teacher_id}")
        # sync phone to linked user if changed
        try:
            from app.core.data.common import ensure_unique
            from app.models.user import User

            new_target = teacher.phone or teacher.phone_2
            if new_target:
                # update linked user if exists
                user = self.db.query(User).filter(User.teacher_id == teacher_id).first()
                if user:
                    old_user_phone = user.phone
                    if user.phone != new_target:
                        ensure_unique(self.db, User, "phone", new_target, exclude_id=user.id, label="Account")
                        user.phone = new_target
                        commit(self.db, f"User phone sync teacher={teacher_id}")
        except Exception:
            pass
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
        """Names only need to be unique *inside* a class - case/space-insensitive."""
        ensure_name_free(
            self.db,
            Teacher,
            "teacher_name",
            teacher_name,
            class_id,
            label="Teacher",
            exclude_id=exclude_id,
        )
