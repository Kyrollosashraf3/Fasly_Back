"""Application factory: builds and wires the whole FastAPI app.

Lifespan, middleware and routers are all registered here so ``app.main``
stays a thin entry point. The React UI lives separately in ``front_fasly``
and talks to this API over HTTP.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_logger, settings
from app.core.auth import (
    ensure_bootstrap_admin,
    ensure_default_classes,
    ensure_seeded_super_admins,
)
from app.core.auth.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.middleware import RequestLogMiddleware
from app.core.notifications import notification_loop
from app.db.database import create_tables
from app.routes import (
    attendance_router,
    auth_router,
    base_router,
    boys_router,
    classes_router,
    dashboard_router,
    follow_ups_router,
    groups_router,
    notifications_router,
    subscriptions_router,
    task_values_router,
    tasks_router,
    teacher_checks_router,
    teachers_router,
    trips_router,
)

logger = get_logger(__name__)


class FaslyApplication:
    """OOP wrapper that creates and configures the FastAPI application."""

    def __init__(self) -> None:
        self.app = FastAPI(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description=settings.APP_DESCRIPTION,
            lifespan=self.lifespan,
        )
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        self._register_middleware()
        self._register_routers()
        logger.info(
            "%s v%s initialized (%d routes)",
            settings.APP_NAME,
            settings.APP_VERSION,
            len(self.app.routes),
        )

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        logger.info("Starting %s v%s ...", settings.APP_NAME, settings.APP_VERSION)
        create_tables()
        ensure_default_classes()
        ensure_bootstrap_admin()
        ensure_seeded_super_admins()
        # The daily reminders and the fortnight cleanup run in this process:
        # nothing else owns a clock. The clock keeps ticking without a VAPID
        # pair - only the push reminders inside it need one.
        loop_task = asyncio.create_task(notification_loop())
        logger.info("Startup complete - ready to serve")
        yield
        if loop_task is not None:
            loop_task.cancel()
        logger.info("Shutting down %s v%s", settings.APP_NAME, settings.APP_VERSION)

    def _register_middleware(self) -> None:
        origins_raw = settings.CORS_ORIGINS or "*"
        origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

        if "*" in origins:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=False,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        else:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        self.app.add_middleware(RequestLogMiddleware)

    def _register_routers(self) -> None:
        for router in (
            base_router,
            auth_router,
            classes_router,
            teachers_router,
            boys_router,
            groups_router,
            attendance_router,
            follow_ups_router,
            teacher_checks_router,
            trips_router,
            subscriptions_router,
            notifications_router,
            tasks_router,
            task_values_router,
            dashboard_router,
        ):
            self.app.include_router(router)


def create_app() -> FastAPI:
    return FaslyApplication().app