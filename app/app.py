"""main.py - FastAPI entry point that wires all endpoints.

Run:
    uvicorn app.main:app --reload --port 9001
"""

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_logger, settings
from app.core.auth.rate_limit import limiter, rate_limit_exceeded_handler

logger = get_logger(__name__)

# Create FastAPI app (identity comes from settings, not hardcoded)
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS — open "*" for dev, restrict via CORS_ORIGINS in .env for production
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database (Firebase/Firestore singleton + startup collection check)
from app.core.auth.bootstrap import ensure_bootstrap_admin
from app.db.firebase import ensure_collections, init_firebase

init_firebase()
ensure_collections()
ensure_bootstrap_admin()

logger.info("Starting %s ...", settings.APP_NAME)
logger.info("App: %s v%s", settings.APP_NAME, settings.APP_VERSION)


@app.get("/")
def root():
    return {
        "message": f"{settings.APP_NAME} is running",
        "docs": "/docs",
        "endpoints": ["POST /api/attendance", "GET /api/attendance"],
    }


# Wire all endpoints into the app (one include per domain router)
from app.routes import auth_router, router as attendance_router

app.include_router(auth_router)  # login / register / users
app.include_router(attendance_router)  # attendance endpoints

logger.info("All routes registered successfully")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log any unhandled error and return the real message instead of a generic 500."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.app:app", host="0.0.0.0", port=9001, reload=True)
