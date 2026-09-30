"""Login accounts - email + password + role only."""

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth.security import get_password_hash
from app.core.data.base import BaseService
from app.core.data.common import ensure_unique_field, get_or_404
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, check_owner


def get_user_by_email(db: Session, email: str) -> User | None:
    """Login lookup - the email is normalised by the schema first."""
    return db.query(User).filter(User.email == email.strip().lower()).first()


class UserService(BaseService):
    """Account lifecycle.

    read : super_admin all | admin accounts of his class | teacher/user only their own
    write: super_admin all | admin accounts of his class (never to super_admin)
    """

    def _query(self):
        role = self.scope.role
        if role == RoleEnum.SUPER_ADMIN:
            return self.db.query(User)
        if role in (RoleEnum.TEACHER, RoleEnum.USER):
            return self.db.query(User).filter(User.id == self.current_user.id)

        # admin: every account bound to a servant or a boy of his class
        class_id = self.scope.require_class()
        teacher_ids = [
            row[0]
            for row in self.db.query(Teacher.id).filter(Teacher.class_id == class_id)
        ]
        boy_ids = [
            row[0] for row in self.db.query(Boy.id).filter(Boy.class_id == class_id)
        ]
        return self.db.query(User).filter(
            or_(
                User.teacher_id.in_(teacher_ids),
                User.boy_id.in_(boy_ids),
            )
        )

    def _ensure_owner_in_scope(self, teacher_id: int | None, boy_id: int | None) -> None:
        if teacher_id is not None:
            teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
            self.scope.ensure_class(teacher.class_id)
        if boy_id is not None:
            boy = get_or_404(self.db, Boy, boy_id, "Boy")
            self.scope.ensure_class(boy.class_id)

    def _ensure_owner_free(
        self,
        teacher_id: int | None,
        boy_id: int | None,
        exclude_id: int | None = None,
    ) -> None:
        """One login per servant and one per boy - ``users.teacher_id`` /
        ``users.boy_id`` are UNIQUE, and a clearer message than a raw 409."""
        for column, value, label in (
            ("teacher_id", teacher_id, "servant"),
            ("boy_id", boy_id, "boy"),
        ):
            if value is None:
                continue
            query = self.db.query(User).filter(getattr(User, column) == value)
            if exclude_id is not None:
                query = query.filter(User.id != exclude_id)
            if query.first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"That {label} already has a login.",
                )

    # ----------------------------------------------------------------- write
    def create_user(self, data: UserCreate) -> User:
        self.scope.require_manager()
        if data.role == RoleEnum.SUPER_ADMIN and not self.scope.is_super_admin:
            self.scope.deny("Only the super admin can create a super admin account.")
        self._ensure_owner_in_scope(data.teacher_id, data.boy_id)
        ensure_unique_field(
            self.db, User, "email", data.email, label="Account"
        )
        self._ensure_owner_free(data.teacher_id, data.boy_id)

        user = User(
            email=data.email,
            password_hash=get_password_hash(data.password),
            role=data.role,
            teacher_id=data.teacher_id,
            boy_id=data.boy_id,
        )
        self.db.add(user)
        self._commit(f"User create email={data.email} role={data.role.value}")
        return user

    def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        self.scope.require_manager()

        updates = data.model_dump(exclude_unset=True)
        password = updates.pop("password", None)

        # the schema validated the payload on its own; re-check the *merged*
        # row so a partial PATCH can never leave role/owner out of sync.
        if updates:
            role = updates.get("role", user.role)
            teacher_id = updates.get("teacher_id", user.teacher_id)
            boy_id = updates.get("boy_id", user.boy_id)
            if role == RoleEnum.SUPER_ADMIN and not self.scope.is_super_admin:
                self.scope.deny("Only the super admin can grant that role.")
            try:
                check_owner(role, teacher_id, boy_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            self._ensure_owner_in_scope(
                updates["teacher_id"] if "teacher_id" in updates else None,
                updates["boy_id"] if "boy_id" in updates else None,
            )
            self._ensure_owner_free(
                updates["teacher_id"]
                if "teacher_id" in updates and updates["teacher_id"] != user.teacher_id
                else None,
                updates["boy_id"]
                if "boy_id" in updates and updates["boy_id"] != user.boy_id
                else None,
                exclude_id=user_id,
            )

        if "email" in updates:
            ensure_unique_field(
                self.db,
                User,
                "email",
                updates["email"],
                exclude_id=user_id,
                label="Account",
            )
            user.email = updates["email"]
        if "role" in updates:
            user.role = updates["role"]
        if "teacher_id" in updates:
            user.teacher_id = updates["teacher_id"]
        if "boy_id" in updates:
            user.boy_id = updates["boy_id"]
        if password:
            user.password_hash = get_password_hash(password)

        self._commit(f"User update id={user_id}")
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        self.scope.require_manager()
        if user.id == self.current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account.",
            )
        self.db.delete(user)
        self._commit(f"User delete id={user_id}")

    # ------------------------------------------------------------------ read
    def get_user(self, user_id: int) -> User:
        user = self._query().filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found.",
            )
        return user

    def list_users(self):
        return self._query().order_by(User.email).all()
