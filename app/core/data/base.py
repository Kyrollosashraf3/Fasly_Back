from app.core.data.common import ensure_admin, ensure_class_access
from app.models.user import UserResponse


class BaseService:
    """Base service that binds the Firestore client and the acting user.

    `user_id` is always available from the authenticated user
    (resolved from the JWT by `get_current_user`).
    """

    def __init__(self, db, current_user: UserResponse):
        self.db = db
        self.current_user = current_user
        self.user_id = current_user.id


class AdminService(BaseService):
    """Base service restricted to admins.

    Used for user accounts management.
    """

    def __init__(self, db, current_user: UserResponse):
        super().__init__(db, current_user)
        ensure_admin(current_user)


class ClassScopedService(BaseService):
    """Base service for records tied to a class (boys, teachers, ...).

    Admin bypasses scoping; amin is locked to his own class.
    """

    def resolve_class(self, class_name):
        """Return the effective class: admin uses the requested one, amin his own."""
        ensure_class_access(class_name, self.current_user)
        from app.models.enums import RoleEnum

        if self.current_user.role == RoleEnum.ADMIN:
            return class_name
        return self.current_user.class_name
