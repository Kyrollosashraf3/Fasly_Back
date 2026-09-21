"""routes package - each file groups related endpoints."""

from .attendance import router as attendance_router
from .auth import router as auth_router
from .boys import router as boys_router
from .dashboard import router as dashboard_router
from .follow_ups import router as follow_ups_router
from .frontend import STATIC_DIR, router as frontend_router
from .teacher_checks import router as teacher_checks_router
from .teachers import router as teachers_router

__all__ = [
    "STATIC_DIR",
    "auth_router",
    "boys_router",
    "teachers_router",
    "attendance_router",
    "follow_ups_router",
    "frontend_router",
    "teacher_checks_router",
    "dashboard_router",
]
