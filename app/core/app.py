"""Application factory: builds and wires the whole FastAPI app.

Lifespan, middleware, routers and the static React UI are all registered
here so ``app.main`` stays a thin entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.config import get_logger, settings
from app.core.auth import ensure_bootstrap_admin, ensure_default_classes
from app.core.auth.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.middleware import RequestLogMiddleware
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
    teacher_checks_router,
    teachers_router,
)

logger = get_logger(__name__)

# Production build of the React UI - `npm run build` in front_fasly writes
# here (vite outDir). Served under /ui so one process hosts API + UI.
REACT_DIR = Path(__file__).resolve().parent.parent / "static_react"


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
        self._register_frontend()
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
        logger.info("Startup complete - ready to serve")
        yield
        logger.info("Shutting down %s v%s", settings.APP_NAME, settings.APP_VERSION)

    def _register_middleware(self) -> None:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
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
            dashboard_router,
        ):
            self.app.include_router(router)

    def _register_frontend(self) -> None:
        """Mount the built React app under /ui (its hash router owns /ui/*)."""
        if not REACT_DIR.is_dir():
            logger.warning(
                "static_react not built yet - run `npm run build` in front_fasly"
            )
            return
        self.app.mount("/ui", StaticFiles(directory=REACT_DIR, html=True), name="ui")


def create_app() -> FastAPI:
    return FaslyApplication().app