"""Service layer: every route calls into here, never straight into the ORM.

Each service is built from three pieces:

    Scope        (app.core.data.base) - *who is asking* and what they may see
    BaseService  - the session, the login and the commit helper
    the service  - one module per table, it only asks ``Scope`` questions

Permission rules live in the ``Scope`` docstring / matrix at the top of
``app.core.data.base``. Nothing in a route makes a decision.
"""

from app.core.data.attendance import AttendanceService
from app.core.data.base import (
    AdminService,
    BaseService,
    ClassScopedService,
    PersonCheckService,
    Scope,
    MANAGER_ROLES,
)
from app.core.data.boys import BoyService
from app.core.data.classes import ClassService
from app.core.data.common import (
    bulk_create,
    commit,
    ensure_unique_field,
    get_or_404,
    is_past_friday,
    now_utc,
    to_date,
    touch,
)
from app.core.data.follow_ups import FollowUpService
from app.core.data.groups import GroupsService
from app.core.data.teacher_checks import TeacherCheckService
from app.core.data.teachers import TeacherService
from app.core.data.users import (
    UserService,
    complete_signup,
    get_user_by_phone,
    signup_check,
)

__all__ = [
    # base
    "Scope",
    "BaseService",
    "AdminService",
    "ClassScopedService",
    "PersonCheckService",
    "MANAGER_ROLES",
    # services
    "AttendanceService",
    "BoyService",
    "ClassService",
    "FollowUpService",
    "GroupsService",
    "TeacherCheckService",
    "TeacherService",
    "UserService",
    "complete_signup",
    "get_user_by_phone",
    "signup_check",
    # helpers
    "bulk_create",
    "commit",
    "ensure_unique_field",
    "get_or_404",
    "is_past_friday",
    "now_utc",
    "to_date",
    "touch",
]
