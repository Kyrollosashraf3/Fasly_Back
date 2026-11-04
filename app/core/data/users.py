"""Login accounts - phone + password + role, nothing else.

A number is registered by an administrator (or imported from a sheet) with
``password_hash = NULL``; the owner then picks his password from ``/auth/signup``.
That single rule is what ``pending_signup`` means everywhere in the app.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.auth.security import get_password_hash
from app.core.data.base import BaseService
from app.core.data.common import (
    MANAGERS,
    bulk_create,
    commit,
    ensure_manager,
    ensure_unique,
    get_or_404,
    normalise_name,
    normalise_phone,
    scope_users,
)
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.general_admin_class import GeneralAdminClass
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserImportRow,
    UserUpdate,
    check_owner,
)

#: Roles that live on a servant row (and therefore inherit his class).
OWNER_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN)

from sqlalchemy import or_

def get_user_by_phone(db, phone: str):
    normalized = normalise_phone(phone)
    return db.query(User).filter(User.phone == normalized).first()



class UserService(BaseService):
    """read : super_admin all | admin accounts of his class | teacher/user own
    write: super_admin all | admin accounts of his class
    """

    def query(self) -> Query:
        return scope_users(self.db, self.db.query(User), self.user)

    def list_users(self) -> list[User]:
        return self.query().order_by(User.phone).all()

    def get_user(self, user_id: int) -> User:
        user = self.query().filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found.",
            )
        return user

    # ----------------------------------------------------------------- write
    def create_user(self, data: UserCreate) -> User:
        ensure_manager(self.user)
        if data.role == RoleEnum.SUPER_ADMIN and self.user.role != RoleEnum.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can create a super admin account.",
            )
        if data.role == RoleEnum.GENERAL_ADMIN and self.user.role != RoleEnum.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can create a stage amin account.",
            )
        if data.role == RoleEnum.GENERAL_ADMIN and not data.teacher_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A stage amin must link a servant - his classes hang off that row.",
            )
        self._ensure_owner_in_scope(data.teacher_id, data.boy_id)
        ensure_unique(self.db, User, "phone", data.phone, label="Account")
        self._ensure_owner_free(data.teacher_id, data.boy_id)

        user = User(
            phone=data.phone,
            # no password yet = the owner sets it himself from /auth/signup
            password_hash=get_password_hash(data.password) if data.password else None,
            role=data.role,
            teacher_id=data.teacher_id,
            boy_id=data.boy_id,
        )
        self.db.add(user)
        if data.role == RoleEnum.GENERAL_ADMIN:
            self.assign_classes(user, data.class_ids)
        commit(self.db, f"User create phone={data.phone} role={data.role.value}")
        return user

    def assign_classes(self, user: User, class_ids: list[int]) -> None:
        """Replace the classes this stage amin's servant row answers for.

        Only the church-wide amin may hand out a group of classes - otherwise a
        stage amin could widen his own scope. The rows are written through the
        session, not committed here, so an account and its classes land together.
        """
        if self.user.role != RoleEnum.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can choose a stage amin's classes.",
            )
        if user.teacher_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Link the stage amin to a servant before choosing his classes.",
            )
        wanted = list(dict.fromkeys(int(class_id) for class_id in class_ids))
        for class_id in wanted:
            get_or_404(self.db, SchoolClass, class_id, "Class")
        teacher = self.db.get(Teacher, user.teacher_id)
        # Reconciled, not replaced: writing the whole list again would insert a
        # class the servant already owns and hit the unique (teacher, class) index.
        owned = {link.class_id for link in teacher.managed_classes}
        for link in [row for row in teacher.managed_classes if row.class_id not in wanted]:
            teacher.managed_classes.remove(link)
        for class_id in [row for row in wanted if row not in owned]:
            teacher.managed_classes.append(GeneralAdminClass(class_id=class_id))

    def set_managed_classes(self, user_id: int, class_ids: list[int]) -> User:
        """``PUT /auth/users/{id}/classes`` - the stage amin's whole class list."""
        user = self.get_user(user_id)
        if user.role != RoleEnum.GENERAL_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account {user_id} is not a stage amin.",
            )
        self.assign_classes(user, class_ids)
        commit(self.db, f"Stage amin id={user_id} classes={len(class_ids)}")
        return user

    def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        fields = data.model_dump(exclude_unset=True)
        password = fields.pop("password", None)

        if self.user.role not in MANAGERS:
            return self._reset_own_password(user, fields, password)

        # The schema already validated the payload; re-check the *merged* row
        # so a partial PATCH can never leave role and owner out of sync.
        if fields:
            self._ensure_merged_row_valid(user, fields)

        if "phone" in fields:
            ensure_unique(
                self.db, User, "phone", fields["phone"], exclude_id=user_id,
                label="Account",
            )
            user.phone = fields["phone"]
        if "role" in fields:
            user.role = fields["role"]
            if user.role != RoleEnum.GENERAL_ADMIN and user.teacher is not None:
                # Nobody owns a group of classes outside the stage-amin role.
                user.teacher.managed_classes = []
        if "teacher_id" in fields and fields["teacher_id"] != user.teacher_id:
            old_teacher = user.teacher
            user.teacher_id = fields["teacher_id"]
            if old_teacher is not None:
                # The group follows the servant, so relinking leaves the row he
                # gave up with no scope waiting behind it.
                old_teacher.managed_classes = []
        if "boy_id" in fields:
            user.boy_id = fields["boy_id"]
        if password:
            user.password_hash = get_password_hash(password)

        commit(self.db, f"User update id={user_id}")
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        ensure_manager(self.user)
        if user.id == self.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account.",
            )
        self.db.delete(user)
        commit(self.db, f"User delete id={user_id}")

    # ---------------------------------------------------------------- import
    def add_list(self, items: list[UserImportRow]) -> dict:
        """Excel / CSV import of accounts.

        Each row is ``phone | class_name | name | role``: the servant named in
        the row is looked up in that class and created when missing, so one
        sheet is enough to stand the accounts up. Checked once up front so a
        non-manager gets a single 403 instead of one failure per row.
        """
        ensure_manager(self.user)
        return bulk_create(
            self._create_from_row, items, label="users", name_attr="phone"
        )

    # ------------------------------------------------------- self-service
    def _reset_own_password(
        self, user: User, fields: dict, password: str | None
    ) -> User:
        """A servant or a boy may reset *his own* password - and nothing else.
        Role, owner links and the phone are privileged fields."""
        if user.id != self.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this operation.",
            )
        if fields:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can change that.",
            )
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update."
            )
        user.password_hash = get_password_hash(password)
        commit(self.db, f"User password reset id={user.id} (self)")
        return user

    # -------------------------------------------------------------- internals
    def _ensure_merged_row_valid(self, user: User, fields: dict) -> None:
        role = fields.get("role", user.role)
        teacher_id = fields.get("teacher_id", user.teacher_id)
        boy_id = fields.get("boy_id", user.boy_id)

        if role == RoleEnum.SUPER_ADMIN and self.user.role != RoleEnum.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can grant that role.",
            )
        if (
            role == RoleEnum.GENERAL_ADMIN
            and role != user.role
            and self.user.role != RoleEnum.SUPER_ADMIN
        ):
            # A stage amin must not be granted - or widened - by a class amin,
            # and he must not hand the role to anybody himself.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can grant that role.",
            )
        try:
            check_owner(role, teacher_id, boy_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

        self._ensure_owner_in_scope(
            fields.get("teacher_id"), fields.get("boy_id")
        )
        self._ensure_owner_free(
            fields["teacher_id"]
            if "teacher_id" in fields and fields["teacher_id"] != user.teacher_id
            else None,
            fields["boy_id"]
            if "boy_id" in fields and fields["boy_id"] != user.boy_id
            else None,
            exclude_id=user.id,
        )

    def _ensure_owner_in_scope(
        self, teacher_id: int | None, boy_id: int | None
    ) -> None:
        if teacher_id is not None:
            self.ensure_class(get_or_404(self.db, Teacher, teacher_id, "Servant").class_id)
        if boy_id is not None:
            self.ensure_class(get_or_404(self.db, Boy, boy_id, "Boy").class_id)

    def _ensure_owner_free(
        self,
        teacher_id: int | None,
        boy_id: int | None,
        exclude_id: int | None = None,
    ) -> None:
        """One login per servant and one per boy - both owner columns are
        UNIQUE, and this says so in plain words instead of a raw 409."""
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

    def _create_from_row(self, row: UserImportRow) -> User:
        # Phone first: never leave a freshly created servant behind when the
        # account itself cannot be written.
        if get_user_by_phone(self.db, row.phone) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"phone: '{row.phone}' already has an account.",
            )
        teacher_id = self._servant_for(row).id if row.role in OWNER_ROLES else None
        boy_id = self._boy_for(row).id if row.role == RoleEnum.USER else None
        return self.create_user(
            UserCreate(
                phone=row.phone,
                role=row.role,
                teacher_id=teacher_id,
                boy_id=boy_id,
            )
        )

    def _servant_for(self, row: UserImportRow) -> Teacher:
        """The servant named in the row, filed into his class when new."""
        wanted = normalise_name(row.name)
        for servant in (
            self.db.query(Teacher).filter(Teacher.class_id == row.class_id).all()
        ):
            if normalise_name(servant.teacher_name) == wanted:
                self.ensure_class(servant.class_id)
                return servant
        servant = Teacher(teacher_name=row.name, class_id=row.class_id)
        self.db.add(servant)
        commit(self.db, f"Servant created during users import: {row.name}")
        return servant

    def _boy_for(self, row: UserImportRow) -> Boy:
        """The boy named in the row - never invented, only looked up."""
        wanted = normalise_name(row.name)
        for boy in self.db.query(Boy).filter(Boy.class_id == row.class_id).all():
            if normalise_name(boy.boy_name) == wanted:
                self.ensure_class(boy.class_id)
                return boy
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"boy '{row.name}' is not in class '{row.class_name}' - "
                "add him first, then re-upload this row."
            ),
        )


# ================================================================= signup
# Module-level on purpose: these two run before anyone is logged in, so they
# have no service (and no permission check) to hang off.


def signup_check(db, phone: str) -> dict:
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


def complete_signup(db, phone: str, password: str) -> User:
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
