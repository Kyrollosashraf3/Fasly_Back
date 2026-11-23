"""Every router the app mounts - one module per domain."""

from app.routes.attendance import router as attendance_router
from app.routes.auth import router as auth_router
from app.routes.base import router as base_router
from app.routes.boys import router as boys_router
from app.routes.churches import router as churches_router
from app.routes.classes import router as classes_router
from app.routes.dashboard import router as dashboard_router
from app.routes.follow_ups import router as follow_ups_router
from app.routes.groups import router as groups_router
from app.routes.locations import router as locations_router
from app.routes.notifications import router as notifications_router
from app.routes.subscriptions import router as subscriptions_router
from app.routes.task_values import router as task_values_router
from app.routes.tasks import router as tasks_router
from app.routes.teacher_checks import router as teacher_checks_router
from app.routes.teacher_follow_ups import router as teacher_follow_ups_router
from app.routes.teachers import router as teachers_router
from app.routes.trip_attendance import router as trip_attendance_router
from app.routes.trips import router as trips_router

__all__ = [
    "base_router",
    "auth_router",
    "boys_router",
    "teachers_router",
    "classes_router",
    "churches_router",
    "attendance_router",
    "follow_ups_router",
    "groups_router",
    "locations_router",
    "subscriptions_router",
    "notifications_router",
    "teacher_checks_router",
    "teacher_follow_ups_router",
    "trips_router",
    "trip_attendance_router",
    "tasks_router",
    "task_values_router",
    "dashboard_router",
]