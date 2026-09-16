"""core/data package - one service module per domain."""

from app.core.data.attendance import AttendanceService
from app.core.data.base import AdminService, BaseService, ClassScopedService
from app.core.data.boys import BoyService
from app.core.data.follow_ups import FollowUpService
from app.core.data.teacher_checks import TeacherCheckService
from app.core.data.teachers import TeacherService
from app.core.data.users import UserService, get_user_by_mail

__all__ = [
    "BaseService",
    "AdminService",
    "ClassScopedService",
    "UserService",
    "get_user_by_mail",
    "BoyService",
    "TeacherService",
    "AttendanceService",
    "FollowUpService",
    "TeacherCheckService",
]
