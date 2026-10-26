"""Service layer: every route calls into here, never straight into the ORM.

One module per table. A service only ever asks questions, and every question
has exactly one home:

    who is allowed to see this row   ->  the ``scope_*`` / ``ensure_*``
                                         functions in ``app.core.data.common``
    how is a row found and saved      ->  ``app.core.data.base``
    what does this table mean         ->  the service module itself

Nothing in a route makes a decision, and no permission rule is duplicated.
"""

from __future__ import annotations

from app.core.data.attendance import AttendanceService
from app.core.data.base import BaseService, WeeklySheetService
from app.core.data.boys import BoyService
from app.core.data.classes import ClassService
from app.core.data.common import (
    MANAGERS,
    apply_update,
    bulk_create,
    commit,
    ensure_boy_access,
    ensure_manager,
    ensure_roles,
    ensure_teacher_access,
    get_or_404,
    my_class_id,
    normalise_name,
    normalise_phone,
)
from app.core.data.follow_ups import FollowUpService
from app.core.data.groups import GroupsService
from app.core.data.subscriptions import SubscriptionService
from app.core.data.task_values import TaskValueService
from app.core.data.tasks import TaskService
from app.core.data.teacher_checks import TeacherCheckService
from app.core.data.teachers import TeacherService
from app.core.data.trips import TripService
from app.core.data.users import (
    UserService,
    complete_signup,
    get_user_by_phone,
    signup_check,
)

__all__ = [
    # bases
    "BaseService",
    "WeeklySheetService",
    # services
    "AttendanceService",
    "BoyService",
    "ClassService",
    "FollowUpService",
    "GroupsService",
    "SubscriptionService",
    "TaskService",
    "TaskValueService",
    "TeacherCheckService",
    "TeacherService",
    "TripService",
    "UserService",
    # signup (pre-login, no service)
    "complete_signup",
    "get_user_by_phone",
    "signup_check",
    # the handful of helpers routes need
    "MANAGERS",
    "apply_update",
    "bulk_create",
    "commit",
    "ensure_boy_access",
    "ensure_manager",
    "ensure_roles",
    "ensure_teacher_access",
    "get_or_404",
    "my_class_id",
    "normalise_name",
    "normalise_phone",
]