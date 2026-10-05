"""Login accounts - phone + password + role only."""

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth.security import get_password_hash
from app.core.data.base import MANAGER_ROLES, BaseService
from app.core.data.common import bulk_create, commit, ensure_unique_field, get_or_404
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserImportRow,
    UserUpdate,
    check_owner,
    normalise_phone,
)

_OWNER_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN)


def _norm(value: str) -> str:
    """Case/whitespace-insensitive form of a person's name."""
    return " ".join(str(value).split()).lower()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    """Login lookup by mobile number - the only handle there is."""
    return db.query(User).filter(User.phone == normalise_phone(phone)).first()


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
        ensure_unique_field(self.db, User, "phone", data.phone, label="Account")
        self._ensure_owner_free(data.teacher_id, data.boy_id)

        user = User(
            phone=data.phone,
            # no password yet = the owner sets it himself from /signup
            password_hash=(
                get_password_hash(data.password) if data.password else None
            ),
            role=data.role,
            teacher_id=data.teacher_id,
            boy_id=data.boy_id,
        )
        self.db.add(user)
        self._commit(f"User create phone={data.phone} role={data.role.value}")
        return user

    def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = self.get_user(user_id)

        updates = data.model_dump(exclude_unset=True)
        password = updates.pop("password", None)

        if self.scope.role not in MANAGER_ROLES:
            # Self-service: a servant or a boy may reset his own password and
            # nothing else - role, owner links and the address are privileged.
            if user.id != self.current_user.id:
                self.scope.deny(
                    "You do not have permission to perform this operation."
                )
            if updates:
                self.scope.deny("Only an administrator can change that.")
            if not password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nothing to update.",
                )
            user.password_hash = get_password_hash(password)
            self._commit(f"User password reset id={user_id} (self)")
            return user

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

        if "phone" in updates:
            ensure_unique_field(
                self.db,
                User,
                "phone",
                updates["phone"],
                exclude_id=user_id,
                label="Account",
            )
            user.phone = updates["phone"]
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
        return self._query().order_by(User.phone).all()

    # ---------------------------------------------------------------- import
    def add_list(self, items: list[UserImportRow]) -> dict:
        """Excel / CSV import of login accounts.

        Checked once up front so a non-manager gets a single 403 instead of
        one failure per row. Each sheet row is ``phone | class_name | name |
        role`` - the servant named in the row is looked up in that class and
        created when he is not there yet, so one file is enough to stand up
        the accounts.
        """
        self.scope.require_manager()
        return bulk_create(
            self._create_from_row, items, label="users", name_attr="phone"
        )

    def _create_from_row(self, row: UserImportRow) -> User:
        # phone first: never leave a freshly created servant behind when the
        # account itself cannot be written.
        if get_user_by_phone(self.db, row.phone) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"phone: '{row.phone}' already has an account.",
            )

        teacher_id = boy_id = None
        if row.role in _OWNER_ROLES:
            teacher_id = self._servant_for(row).id
        elif row.role == RoleEnum.USER:
            boy_id = self._boy_for(row).id

        return self.create_user(
            UserCreate(
                phone=row.phone,
                role=row.role,
                teacher_id=teacher_id,
                boy_id=boy_id,
            )
        )

    def _servant_for(self, row: UserImportRow) -> Teacher:
        """The servant named in the row, filed into his class if new."""
        key = _norm(row.name)
        for teacher in (
            self.db.query(Teacher).filter(Teacher.class_id == row.class_id).all()
        ):
            if _norm(teacher.teacher_name) == key:
                self.scope.ensure_class(teacher.class_id)
                return teacher

        teacher = Teacher(teacher_name=row.name, class_id=row.class_id)
        self.db.add(teacher)
        self._commit(f"Servant created during users import: {row.name}")
        return teacher

    def _boy_for(self, row: UserImportRow) -> Boy:
        """The boy named in the row - never invented, only looked up."""
        for boy in self.db.query(Boy).filter(Boy.class_id == row.class_id).all():
            if _norm(boy.boy_name) == _norm(row.name):
                self.scope.ensure_class(boy.class_id)
                return boy
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"boy '{row.name}' is not in class '{row.class_name}' - "
                "add him first, then re-upload this row."
            ),
        )


# ----------------------------------------------------------- self-service


def signup_check(db: Session, phone: str) -> dict:
    """Does this number belong to an account, and does it still need a password?"""
    user = get_user_by_phone(db, phone)
    if user is None:
        return {
            "exists": False,
            "needs_signup": False,
            "display_name": None,
            "role": None,
        }
    return {
        "exists": True,
        "needs_signup": user.pending_signup,
        "display_name": user.display_name,
        "role": user.role,
    }


def complete_signup(db: Session, phone: str, password: str) -> User:
    """Set the password of a phone-registered account - the one step an
    administrator cannot do for him.

    404 unknown number, 409 the password is already set (signup happens once).
    """
    user = get_user_by_phone(db, phone)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account is registered with that phone number.",
        )
    if not user.pending_signup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This number already has a password. Use login instead.",
        )
    user.password_hash = get_password_hash(password)
    commit(db, f"Signup phone={phone} user_id={user.id}")
    return user
