"""Every router the app mounts - one module per domain."""

from app.features.attendance.routes import router as attendance_router
from app.features.user.routes import router as auth_router
from app.routes.base import router as base_router
from app.features.boy.routes import router as boys_router
from app.features.church.routes import router as churches_router
from app.features.school_class.routes import router as classes_router
from app.features.dashboard.routes import router as dashboard_router
from app.features.follow_up.routes import router as follow_ups_router
from app.features.group.routes import router as groups_router
from app.features.location.routes import router as locations_router
from app.features.notification.routes import router as notifications_router
from app.features.subscription.routes import router as subscriptions_router
from app.features.servant_trip.routes import (
    subscriptions_router as servant_trip_subscriptions_router,
    trips_router as servant_trips_router,
)
from app.features.team.routes.team import router as teams_router
from app.features.team.routes.team_member import router as team_members_router
from app.features.team.routes.team_teacher import router as team_teachers_router
from app.features.task_value.routes import router as task_values_router
from app.features.task.routes import router as tasks_router
from app.features.teacher_check.routes import router as teacher_checks_router
from app.features.teacher_follow_up.routes import router as teacher_follow_ups_router
from app.features.teacher.routes import router as teachers_router
from app.features.trip_attendance.routes import router as trip_attendance_router
from app.features.trip.routes import router as trips_router

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
    "servant_trips_router",
    "servant_trip_subscriptions_router",
    "teams_router",
    "team_members_router",
    "team_teachers_router",
    "notifications_router",
    "teacher_checks_router",
    "teacher_follow_ups_router",
    "trips_router",
    "trip_attendance_router",
    "tasks_router",
    "task_values_router",
    "dashboard_router",
]