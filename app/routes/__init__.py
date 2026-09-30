"""routes package - each file groups related endpoints."""

from app.routes.attendance import router as attendance_router
from app.routes.auth import router as auth_router
from app.routes.boys import router as boys_router
from app.routes.dashboard import router as dashboard_router
from app.routes.follow_ups import router as follow_ups_router
from app.routes.frontend import STATIC_DIR, router as frontend_router
from app.routes.groups import router as groups_router
from app.routes.teacher_checks import router as teacher_checks_router
from app.routes.teachers import router as teachers_router

__all__ = [
    "STATIC_DIR",
    "auth_router",
    "boys_router",
    "teachers_router",
    "attendance_router",
    "follow_ups_router",
    "frontend_router",
    "groups_router",
    "teacher_checks_router",
    "dashboard_router",
]
